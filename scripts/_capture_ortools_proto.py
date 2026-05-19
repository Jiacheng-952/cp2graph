from __future__ import annotations

import argparse
import json
import os
import runpy
import sys
import traceback
from pathlib import Path

from ortools.sat.python import cp_model


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Run one OR-Tools solver and capture CpModel protos.")
    parser.add_argument("--solver", required=True)
    parser.add_argument("--workdir", required=True)
    parser.add_argument("--out-dir", required=True)
    args = parser.parse_args()

    solver_path = Path(args.solver).resolve()
    workdir = Path(args.workdir).resolve()
    out_dir = Path(args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    captured = []
    original_solve = cp_model.CpSolver.Solve
    original_solve_with_callback = getattr(cp_model.CpSolver, "SolveWithSolutionCallback", None)
    original_search = getattr(cp_model.CpSolver, "SearchForAllSolutions", None)

    def _capture(self, model, *solve_args, **solve_kwargs):
        proto_path = out_dir / f"model_{len(captured) + 1:04d}.proto.pb"
        proto_path.write_bytes(model.Proto().SerializeToString())
        captured.append(str(proto_path))
        return cp_model.UNKNOWN

    cp_model.CpSolver.Solve = _capture
    if original_solve_with_callback is not None:
        cp_model.CpSolver.SolveWithSolutionCallback = _capture
    if original_search is not None:
        cp_model.CpSolver.SearchForAllSolutions = _capture

    old_cwd = Path.cwd()
    old_argv = sys.argv[:]
    try:
        os.chdir(workdir)
        if str(workdir) not in sys.path:
            sys.path.insert(0, str(workdir))
        sys.argv = [str(solver_path)]
        runpy.run_path(str(solver_path), run_name="__main__")
        status = "ok" if captured else "no_proto"
        error = None
    except Exception:
        status = "error"
        error = traceback.format_exc()
    finally:
        sys.argv = old_argv
        os.chdir(old_cwd)
        cp_model.CpSolver.Solve = original_solve
        if original_solve_with_callback is not None:
            cp_model.CpSolver.SolveWithSolutionCallback = original_solve_with_callback
        if original_search is not None:
            cp_model.CpSolver.SearchForAllSolutions = original_search

    report = {"status": status, "captured": captured, "error": error}
    print(json.dumps(report, ensure_ascii=True))
    if status != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
