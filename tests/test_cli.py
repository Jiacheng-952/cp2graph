import json
import subprocess
import sys
from pathlib import Path


def test_cli_json_output(tmp_path: Path) -> None:
    root = Path(__file__).resolve().parents[1]
    model = root / "tests" / "models" / "m01_arith.fzn"
    out = tmp_path / "graph.json"
    cmd = [sys.executable, "-m", "cp2graph.cli", str(model), "-o", str(out), "--hash"]
    proc = subprocess.run(cmd, cwd=root, capture_output=True, text=True, check=False)
    assert proc.returncode == 0, proc.stderr
    assert out.exists()
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert "nodes" in payload and "edges" in payload
    assert proc.stdout.strip()
