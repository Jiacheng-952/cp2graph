from pathlib import Path

import pytest

from cp2graph.cli import main


def test_cli_main_invalid_format(monkeypatch, tmp_path: Path) -> None:
    model = Path(__file__).parent / "models" / "m01_arith.fzn"
    out = tmp_path / "graph.abc"
    monkeypatch.setattr(
        "sys.argv",
        ["cp2graph", str(model), "-o", str(out)],
    )
    with pytest.raises(SystemExit):
        main()


def test_cli_main_graphml(monkeypatch, tmp_path: Path) -> None:
    model = Path(__file__).parent / "models" / "m01_arith.fzn"
    out = tmp_path / "graph.graphml"
    monkeypatch.setattr(
        "sys.argv",
        ["cp2graph", str(model), "-o", str(out), "--format", "graphml"],
    )
    main()
    assert out.exists()
