import pytest

from cp2graph.parser import FlatZincParser


def test_array_length_mismatch_raises() -> None:
    text = "array [1..3] of int: c = [1,2];\nsolve satisfy;\n"
    parser = FlatZincParser()
    with pytest.raises(ValueError):
        parser.parse_text(text)
