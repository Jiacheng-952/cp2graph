from __future__ import annotations

from pathlib import Path
from typing import Optional

import networkx as nx

from .graph_builder import build_constraint_graph
from .normalize import normalize_model
from .parser import FlatZincParser, compile_minizinc_to_fzn


def parse_and_build_graph(model_path: str | Path, normalize: bool = True) -> nx.MultiDiGraph:
    parser = FlatZincParser()
    path = Path(model_path)
    if path.suffix.lower() == ".mzn":
        fzn = compile_minizinc_to_fzn(path)
        model = parser.parse_text(fzn)
    else:
        model = parser.parse_file(path)
    if normalize:
        model = normalize_model(model)
    return build_constraint_graph(model)


def parse_model_text_to_graph(text: str, normalize: bool = True) -> nx.MultiDiGraph:
    parser = FlatZincParser()
    model = parser.parse_text(text)
    if normalize:
        model = normalize_model(model)
    return build_constraint_graph(model)


def graph_fingerprint(graph: nx.MultiDiGraph) -> str:
    from .serialize import graph_to_json_obj
    from .hash_utils import semantic_hash

    return semantic_hash(graph_to_json_obj(graph))
