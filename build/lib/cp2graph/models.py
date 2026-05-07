from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Domain:
    kind: str
    values: Optional[List[int]] = None
    lower: Optional[float] = None
    upper: Optional[float] = None

    @property
    def size(self) -> Optional[float]:
        if self.kind == "bool":
            return 2
        if self.kind == "int-set" and self.values is not None:
            return float(len(set(self.values)))
        if self.kind in {"int-bounds", "float-bounds"} and self.lower is not None and self.upper is not None:
            return float(self.upper - self.lower + 1) if self.kind == "int-bounds" else None
        return None

    def to_json(self) -> Dict[str, Any]:
        return {
            "kind": self.kind,
            "values": self.values,
            "lower": self.lower,
            "upper": self.upper,
        }


@dataclass
class Variable:
    id: str
    name: str
    domain: Domain
    is_objective: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Constraint:
    id: str
    ctype: str
    params: Any
    semantic_hash: str


@dataclass
class Objective:
    sense: str
    expr: Any


@dataclass
class CPModelIR:
    variables: Dict[str, Variable] = field(default_factory=dict)
    constraints: List[Constraint] = field(default_factory=list)
    objective: Optional[Objective] = None
    constants: Dict[str, Any] = field(default_factory=dict)

    def copy(self) -> "CPModelIR":
        return CPModelIR(
            variables=dict(self.variables),
            constraints=list(self.constraints),
            objective=self.objective,
            constants=dict(self.constants),
        )
