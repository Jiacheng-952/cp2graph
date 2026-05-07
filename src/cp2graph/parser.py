from __future__ import annotations

import re
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Tuple

from lark import Lark, Transformer

from .models import CPModelIR, Constraint, Domain, Objective, Variable


FZN_GRAMMAR = r"""
start: statement*

?statement: var_decl
          | array_var_decl
          | const_decl
          | array_const_decl
          | constraint_stmt
          | solve_stmt

var_decl: "var" domain ":" ident ("=" value)? ";"
array_var_decl: "array" "[" range "]" "of" "var" domain ":" CNAME ";"
const_decl: BASICTYPE ":" CNAME "=" value ";"
array_const_decl: "array" "[" range "]" "of" BASICTYPE ":" CNAME "=" array_literal ";"

constraint_stmt: "constraint" ident "(" [value_list] ")" annotation* ";"
solve_stmt: "solve" annotation* solve_goal ";"
solve_goal: "satisfy"           -> goal_satisfy
          | "minimize" value    -> goal_minimize
          | "maximize" value    -> goal_maximize

annotation: "::" (call | ident)

?value_list: value ("," value)*
?value: call
      | array_literal
      | set_literal
      | range
      | ident
      | number
      | BOOL                    -> bool
      | STRING                  -> string
      | "(" value ")"

array_literal: "[" [value_list] "]"
set_literal: "{" [num_list] "}"
num_list: number ("," number)*
call: ident "(" [value_list] ")"
ident: CNAME ("[" INT "]")?
domain: "bool"                 -> bool_domain
      | "{" [num_list] "}"     -> set_domain
      | range                  -> range_domain

number: FLOAT | INT
range: number ".." number
BOOL: "true" | "false"
BASICTYPE: "int" | "bool" | "float"

%import common.CNAME
FLOAT: /-?\d+\.\d+/
INT: /-?\d+/
%import common.ESCAPED_STRING -> STRING
%import common.WS
%ignore WS
"""


class _TreeToPy(Transformer):
    def number(self, items: List[Any]) -> Any:
        txt = str(items[0])
        if "." in txt:
            return float(txt)
        return int(txt)

    def bool(self, items: List[Any]) -> bool:
        return str(items[0]) == "true"

    def string(self, items: List[Any]) -> str:
        s = str(items[0])
        return s[1:-1]

    def ident(self, items: List[Any]) -> str:
        if len(items) == 1:
            return str(items[0])
        return f"{items[0]}[{int(str(items[1]))}]"

    def range(self, items: List[Any]) -> Tuple[Any, Any]:
        lo = self.number([items[0]])
        hi = self.number([items[1]])
        return (lo, hi)

    def num_list(self, items: List[Any]) -> List[Any]:
        return [self.number([x]) for x in items]

    def array_literal(self, items: List[Any]) -> List[Any]:
        if not items:
            return []
        return list(items[0]) if isinstance(items[0], list) else list(items)

    def set_literal(self, items: List[Any]) -> Any:
        if len(items) == 1:
            return items[0]
        return tuple(items)

    def value_list(self, items: List[Any]) -> List[Any]:
        return list(items)

    def call(self, items: List[Any]) -> Dict[str, Any]:
        name = items[0]
        args = items[1] if len(items) > 1 else []
        return {"call": name, "args": args}

    def annotation(self, items: List[Any]) -> Dict[str, Any]:
        item = items[0]
        if isinstance(item, str):
            return {"call": item, "args": []}
        return item

    def bool_domain(self, _items: List[Any]) -> Dict[str, Any]:
        return {"kind": "bool"}

    def set_domain(self, items: List[Any]) -> Dict[str, Any]:
        values = items[0] if items else []
        return {"kind": "int-set", "values": values}

    def range_domain(self, items: List[Any]) -> Dict[str, Any]:
        lo, hi = items[0]
        kind = "float-bounds" if isinstance(lo, float) or isinstance(hi, float) else "int-bounds"
        return {"kind": kind, "lower": lo, "upper": hi}

    def domain(self, items: List[Any]) -> Dict[str, Any]:
        return items[0]

    def var_decl(self, items: List[Any]) -> Dict[str, Any]:
        domain = items[0]
        name = items[1]
        init = items[2] if len(items) > 2 else None
        return {"type": "var_decl", "name": name, "domain": domain, "init": init}

    def array_var_decl(self, items: List[Any]) -> Dict[str, Any]:
        return {"type": "array_var_decl", "range": items[0], "domain": items[1], "name": str(items[2])}

    def const_decl(self, items: List[Any]) -> Dict[str, Any]:
        ctype = str(items[0])
        name = str(items[1])
        value = items[2]
        return {"type": "const_decl", "ctype": ctype, "name": name, "value": value}

    def array_const_decl(self, items: List[Any]) -> Dict[str, Any]:
        return {"type": "array_const_decl", "range": items[0], "ctype": str(items[1]), "name": str(items[2]), "value": items[3]}

    def constraint_stmt(self, items: List[Any]) -> Dict[str, Any]:
        name = items[0]
        args = []
        anns: List[Any] = []
        for item in items[1:]:
            if isinstance(item, list) and (not item or not isinstance(item[0], dict) or "call" not in item[0]):
                args = item
            elif isinstance(item, dict) and "call" in item:
                anns.append(item)
        return {"type": "constraint", "name": name, "args": args, "annotations": anns}

    def solve_stmt(self, items: List[Any]) -> Dict[str, Any]:
        anns = [item for item in items if isinstance(item, dict) and "call" in item]
        goals = [item for item in items if isinstance(item, tuple)]
        sense, expr = goals[0] if goals else ("satisfy", None)
        return {"type": "solve", "sense": sense, "expr": expr, "annotations": anns}

    def goal_satisfy(self, _items: List[Any]) -> Tuple[str, Any]:
        return ("satisfy", None)

    def goal_minimize(self, items: List[Any]) -> Tuple[str, Any]:
        return ("minimize", items[0])

    def goal_maximize(self, items: List[Any]) -> Tuple[str, Any]:
        return ("maximize", items[0])

    def start(self, items: List[Any]) -> List[Any]:
        return items


class FlatZincParser:
    def __init__(self) -> None:
        self._parser = Lark(FZN_GRAMMAR, start="start", parser="lalr")
        self._transformer = _TreeToPy()

    @staticmethod
    def _strip_comments(text: str) -> str:
        text = text.lstrip("\ufeff")
        text = re.sub(r"%.*?$", "", text, flags=re.MULTILINE)
        return text

    @staticmethod
    def _domain_from_dict(raw: Dict[str, Any]) -> Domain:
        return Domain(
            kind=raw["kind"],
            values=raw.get("values"),
            lower=raw.get("lower"),
            upper=raw.get("upper"),
        )

    @staticmethod
    def _expand_range(rng: Tuple[int, int]) -> List[int]:
        lo, hi = int(rng[0]), int(rng[1])
        return list(range(lo, hi + 1))

    def _resolve_value(self, value: Any, constants: Dict[str, Any], variables: Dict[str, Variable]) -> Any:
        if isinstance(value, list):
            return [self._resolve_value(v, constants, variables) for v in value]
        if isinstance(value, tuple) and len(value) == 2 and all(isinstance(v, (int, float)) for v in value):
            return {"range": [value[0], value[1]]}
        if isinstance(value, dict) and "call" in value:
            return {"call": value["call"], "args": self._resolve_value(value["args"], constants, variables)}
        if isinstance(value, str):
            if value in variables:
                return {"var": value}
            if value in constants:
                return self._resolve_value(constants[value], constants, variables)
            return {"symbol": value}
        return value

    def parse_text(self, text: str) -> CPModelIR:
        cleaned = self._strip_comments(text)
        tree = self._parser.parse(cleaned)
        statements = self._transformer.transform(tree)
        model = CPModelIR()
        constants: Dict[str, Any] = {}
        arrays: Dict[str, List[Any]] = {}
        constraint_count = 0

        for stmt in statements:
            stype = stmt["type"]
            if stype == "const_decl":
                constants[stmt["name"]] = stmt["value"]
            elif stype == "array_const_decl":
                expected_len = len(self._expand_range(stmt["range"]))
                value = stmt["value"]
                if len(value) != expected_len:
                    raise ValueError(f"Array constant {stmt['name']} length mismatch: expected {expected_len}, got {len(value)}")
                constants[stmt["name"]] = value
                arrays[stmt["name"]] = value
            elif stype == "var_decl":
                name = stmt["name"]
                variable = Variable(id=name, name=name, domain=self._domain_from_dict(stmt["domain"]))
                model.variables[name] = variable
                if stmt["init"] is not None:
                    constants[name] = self._resolve_value(stmt["init"], constants, model.variables)
            elif stype == "array_var_decl":
                name = stmt["name"]
                idx = self._expand_range(stmt["range"])
                array_vars: List[Any] = []
                for i in idx:
                    item_name = f"{name}[{i}]"
                    variable = Variable(id=item_name, name=item_name, domain=self._domain_from_dict(stmt["domain"]))
                    model.variables[item_name] = variable
                    array_vars.append({"var": item_name})
                arrays[name] = array_vars
                constants[name] = array_vars
            elif stype == "constraint":
                constraint_count += 1
                raw_params = self._resolve_value(stmt["args"], constants, model.variables)
                model.constraints.append(
                    Constraint(
                        id=f"c_raw_{constraint_count}",
                        ctype=stmt["name"],
                        params=raw_params,
                        semantic_hash="",
                    )
                )
            elif stype == "solve":
                expr = self._resolve_value(stmt["expr"], constants, model.variables) if stmt["expr"] is not None else None
                model.objective = Objective(sense=stmt["sense"], expr=expr)

        model.constants = constants
        return model

    def parse_file(self, path: str | Path) -> CPModelIR:
        text = Path(path).read_text(encoding="utf-8")
        return self.parse_text(text)


def compile_minizinc_to_fzn(model_path: str | Path) -> str:
    cmd = ["minizinc", "--compile", "--output-fzn-to-stdout", str(model_path)]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    if proc.returncode != 0:
        raise RuntimeError(f"MiniZinc compile failed: {proc.stderr.strip()}")
    return proc.stdout
