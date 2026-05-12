from __future__ import annotations

from typing import Any, Dict, Iterable, List, Set

import networkx as nx

from .hash_utils import semantic_hash
from .models import CPModelIR


def _iter_vars(value: Any, shared_subexpressions: Dict[str, Any] | None = None, seen_refs: Set[str] | None = None) -> Iterable[str]:
    if seen_refs is None:
        seen_refs = set()
    if isinstance(value, list):
        for item in value:
            yield from _iter_vars(item, shared_subexpressions, seen_refs)
    elif isinstance(value, dict):
        if "var" in value:
            yield value["var"]
        if "shared_ref" in value and shared_subexpressions is not None:
            ref = value["shared_ref"]
            if ref in shared_subexpressions and ref not in seen_refs:
                seen_refs.add(ref)
                yield from _iter_vars(shared_subexpressions[ref], shared_subexpressions, seen_refs)
        for inner in value.values():
            if isinstance(inner, (list, dict)):
                yield from _iter_vars(inner, shared_subexpressions, seen_refs)


def _variable_roles_for_constraint(ctype: str, params: Any, shared_subexpressions: Dict[str, Any] | None = None) -> Dict[str, str]:
    vars_in_order: List[str] = []
    seen: Set[str] = set()
    for name in _iter_vars(params, shared_subexpressions):
        if name not in seen:
            seen.add(name)
            vars_in_order.append(name)

    roles = {name: "read" for name in vars_in_order}
    if "element" in ctype and vars_in_order:
        roles[vars_in_order[-1]] = "write"
    return roles


def build_constraint_graph(model: CPModelIR) -> nx.MultiDiGraph:
    g = nx.MultiDiGraph()
    if model.shared_subexpressions:
        g.graph["shared_subexpressions"] = dict(model.shared_subexpressions)
    for var in model.variables.values():
        g.add_node(
            var.id,
            id=var.id,
            type="variable",
            name=var.name,
            domain=var.domain.to_json(),
            size=var.domain.size,
            semantic_hash=None,
            is_objective=var.is_objective,
        )

    for constraint in model.constraints:
        node_id = constraint.id
        c_hash = constraint.semantic_hash or semantic_hash({"type": constraint.ctype, "params": constraint.params})
        g.add_node(
            node_id,
            id=node_id,
            type="constraint",
            constraint_type=constraint.ctype,
            params=constraint.params,
            domain=None,
            size=None,
            semantic_hash=c_hash,
        )
        roles = _variable_roles_for_constraint(constraint.ctype, constraint.params, model.shared_subexpressions)
        for var_name, role in roles.items():
            if var_name in model.variables:
                g.add_edge(var_name, node_id, src=var_name, dst=node_id, role=role)
                g.add_edge(node_id, var_name, src=node_id, dst=var_name, role=role)
    return g
