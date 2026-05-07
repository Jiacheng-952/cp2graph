from __future__ import annotations

from dataclasses import replace
from typing import Any, Dict, List, Tuple

from .hash_utils import semantic_hash
from .models import CPModelIR, Constraint, Objective, Variable


def _fold_constants(value: Any, constants: Dict[str, Any]) -> Any:
    if isinstance(value, list):
        return [_fold_constants(v, constants) for v in value]
    if isinstance(value, dict):
        if "symbol" in value and value["symbol"] in constants:
            return _fold_constants(constants[value["symbol"]], constants)
        if "call" in value:
            return {"call": value["call"], "args": _fold_constants(value.get("args", []), constants)}
        return {k: _fold_constants(v, constants) for k, v in value.items()}
    return value


def _normalize_variable_order(variables: Dict[str, Variable]) -> Tuple[Dict[str, Variable], Dict[str, str]]:
    ordered_names = sorted(variables.keys())
    mapping: Dict[str, str] = {}
    normalized: Dict[str, Variable] = {}
    for idx, old_name in enumerate(ordered_names, start=1):
        new_name = f"v{idx}"
        mapping[old_name] = new_name
        var = variables[old_name]
        normalized[new_name] = Variable(
            id=new_name,
            name=var.name,
            domain=var.domain,
            is_objective=var.is_objective,
            metadata=dict(var.metadata),
        )
    return normalized, mapping


def _rename_vars(value: Any, mapping: Dict[str, str]) -> Any:
    if isinstance(value, list):
        return [_rename_vars(v, mapping) for v in value]
    if isinstance(value, dict):
        if "var" in value:
            return {"var": mapping.get(value["var"], value["var"])}
        if "call" in value:
            return {"call": value["call"], "args": _rename_vars(value.get("args", []), mapping)}
        return {k: _rename_vars(v, mapping) for k, v in value.items()}
    return value


def _constraint_payload(constraint: Constraint) -> Dict[str, Any]:
    return {"type": constraint.ctype, "params": constraint.params}


def normalize_model(model: CPModelIR) -> CPModelIR:
    normalized_vars, mapping = _normalize_variable_order(model.variables)
    normalized_constraints: List[Constraint] = []
    seen_hashes = set()

    for constraint in model.constraints:
        folded = _fold_constants(constraint.params, model.constants)
        renamed = _rename_vars(folded, mapping)
        payload = {"type": constraint.ctype, "params": renamed}
        chash = semantic_hash(payload)
        if chash in seen_hashes:
            continue
        seen_hashes.add(chash)
        normalized_constraints.append(
            Constraint(
                id=f"c_{chash[:16]}",
                ctype=constraint.ctype,
                params=renamed,
                semantic_hash=chash,
            )
        )

    objective = None
    if model.objective:
        expr = _rename_vars(_fold_constants(model.objective.expr, model.constants), mapping)
        objective = Objective(sense=model.objective.sense, expr=expr)
        if isinstance(expr, dict) and "var" in expr and expr["var"] in normalized_vars:
            normalized_vars[expr["var"]] = replace(normalized_vars[expr["var"]], is_objective=True)

    return CPModelIR(
        variables=normalized_vars,
        constraints=sorted(normalized_constraints, key=lambda x: x.semantic_hash),
        objective=objective,
        constants={},
    )
