from pathlib import Path

from cp2graph.incremental import create_state, update_state
from cp2graph.normalize import normalize_model
from cp2graph.parser import FlatZincParser


def _norm(name: str):
    p = Path(__file__).parent / "models" / name
    parser = FlatZincParser()
    return normalize_model(parser.parse_file(p))


def test_incremental_updates_only_changed_constraints() -> None:
    m1 = _norm("m15_diff_hash_1.fzn")
    m2 = _norm("m16_diff_hash_2.fzn")

    s1 = create_state(m1)
    old_constraints = {n for n, d in s1.graph.nodes(data=True) if d.get("type") == "constraint"}

    s2 = update_state(s1, m2)
    new_constraints = {n for n, d in s2.graph.nodes(data=True) if d.get("type") == "constraint"}
    assert old_constraints != new_constraints


def test_incremental_keeps_unchanged_constraints() -> None:
    m1 = _norm("m12_array_reuse.fzn")
    s1 = create_state(m1)
    s2 = update_state(s1, m1)
    assert s1.constraint_hash_to_id == s2.constraint_hash_to_id
