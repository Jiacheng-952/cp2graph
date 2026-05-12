from __future__ import annotations

from collections import Counter
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


def _is_atomic_subexpr(value: Any) -> bool:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return True
    if isinstance(value, dict) and set(value.keys()) <= {"var"}:
        return True
    return False


def _count_subexpressions(value: Any, counts: Counter[str]) -> None:
    if isinstance(value, list):
        for item in value:
            _count_subexpressions(item, counts)
        counts[semantic_hash({"kind": "list", "items": value})] += 1
        return
    if isinstance(value, tuple):
        for item in value:
            _count_subexpressions(item, counts)
        counts[semantic_hash({"kind": "tuple", "items": list(value)})] += 1
        return
    if isinstance(value, dict):
        if "var" in value:
            return
        if "shared_ref" in value:
            return
        for inner in value.values():
            _count_subexpressions(inner, counts)
        counts[semantic_hash(value)] += 1


def _fold_repeated_subexpressions(
    value: Any,
    repeated_hashes: set[str],
    shared_subexpressions: Dict[str, Any],
) -> Any:
    if isinstance(value, list):
        items = [_fold_repeated_subexpressions(v, repeated_hashes, shared_subexpressions) for v in value]
        payload = {"kind": "list", "items": items}
        digest = semantic_hash(payload)
        if digest in repeated_hashes and not _is_atomic_subexpr(items):
            shared_subexpressions.setdefault(digest, items)
            return {"shared_ref": digest}
        return items
    if isinstance(value, tuple):
        items = tuple(_fold_repeated_subexpressions(v, repeated_hashes, shared_subexpressions) for v in value)
        payload = {"kind": "tuple", "items": list(items)}
        digest = semantic_hash(payload)
        if digest in repeated_hashes and not _is_atomic_subexpr(items):
            shared_subexpressions.setdefault(digest, list(items))
            return {"shared_ref": digest}
        return items
    if isinstance(value, dict):
        if "var" in value or "shared_ref" in value:
            return value
        folded = {k: _fold_repeated_subexpressions(v, repeated_hashes, shared_subexpressions) for k, v in value.items()}
        digest = semantic_hash(folded)
        if digest in repeated_hashes and not _is_atomic_subexpr(folded):
            shared_subexpressions.setdefault(digest, folded)
            return {"shared_ref": digest}
        return folded
    return value


def _constraint_payload(constraint: Constraint) -> Dict[str, Any]:
    return {"type": constraint.ctype, "params": constraint.params}


def normalize_model(model: CPModelIR) -> CPModelIR:
    normalized_vars, mapping = _normalize_variable_order(model.variables)
    normalized_constraints: List[Constraint] = []
    seen_hashes = set()
    shared_subexpressions: Dict[str, Any] = {}
    normalized_payloads: List[Tuple[Constraint, Any]] = []

    for constraint in model.constraints:
        folded = _fold_constants(constraint.params, model.constants)
        renamed = _rename_vars(folded, mapping)
        normalized_payloads.append((constraint, renamed))

    objective_expr = None
    if model.objective:
        objective_expr = _rename_vars(_fold_constants(model.objective.expr, model.constants), mapping)

    counts: Counter[str] = Counter()
    for _constraint, payload in normalized_payloads:
        _count_subexpressions(payload, counts)
    if objective_expr is not None:
        _count_subexpressions(objective_expr, counts)

    repeated_hashes = {digest for digest, count in counts.items() if count > 1}

    folded_payloads: List[Tuple[Constraint, Any]] = []
    for constraint, payload in normalized_payloads:
        folded_payload = _fold_repeated_subexpressions(payload, repeated_hashes, shared_subexpressions)
        folded_payloads.append((constraint, folded_payload))

    if objective_expr is not None:
        objective_expr = _fold_repeated_subexpressions(objective_expr, repeated_hashes, shared_subexpressions)

    for constraint, renamed in folded_payloads:
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
    if model.objective and objective_expr is not None:
        objective = Objective(sense=model.objective.sense, expr=objective_expr)
        if isinstance(objective_expr, dict) and "var" in objective_expr and objective_expr["var"] in normalized_vars:
            normalized_vars[objective_expr["var"]] = replace(normalized_vars[objective_expr["var"]], is_objective=True)

    return CPModelIR(
        variables=normalized_vars,
        constraints=sorted(normalized_constraints, key=lambda x: x.semantic_hash),
        objective=objective,
        constants={},
        shared_subexpressions=shared_subexpressions,
    )
