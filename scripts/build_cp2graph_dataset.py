from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List


EXCLUDED_CATEGORIES = {"gortek"}


def _safe_name(name: str) -> str:
    cleaned = []
    for ch in name.lower():
        if ch.isalnum():
            cleaned.append(ch)
        else:
            cleaned.append("_")
    value = "".join(cleaned).strip("_")
    while "__" in value:
        value = value.replace("__", "_")
    return value or "category"


def _find_solver(category_dir: Path) -> Path:
    for name in ("solver.py", "solve.py"):
        candidate = category_dir / name
        if candidate.exists():
            return candidate
    raise FileNotFoundError(f"no solver.py/solve.py in {category_dir}")


def _valid_data_files(data_dir: Path) -> List[Path]:
    blocked_tokens = {"solution", "result", "summary", "stats"}
    valid: List[Path] = []
    for path in sorted(data_dir.glob("*.json"), key=lambda p: p.name):
        lower_name = path.name.lower()
        if any(token in lower_name for token in blocked_tokens):
            continue
        try:
            json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        valid.append(path)
    return valid


def build_dataset(src_root: Path, dst_root: Path, instances_per_category: int = 2) -> Dict[str, Any]:
    if dst_root.exists():
        shutil.rmtree(dst_root)
    dst_root.mkdir(parents=True, exist_ok=True)

    records: List[Dict[str, Any]] = []
    categories = [
        path for path in sorted(src_root.iterdir(), key=lambda p: p.name.lower())
        if path.is_dir() and path.name not in EXCLUDED_CATEGORIES
    ]

    for category_index, category_dir in enumerate(categories, start=1):
        solver_path = _find_solver(category_dir)
        data_dir = category_dir / "data"
        data_files = _valid_data_files(data_dir)[:instances_per_category]
        if len(data_files) < instances_per_category:
            raise ValueError(f"{category_dir.name} has only {len(data_files)} json data files")

        category_slug = _safe_name(category_dir.name)
        for instance_index, data_path in enumerate(data_files, start=1):
            model_id = f"{category_index:02d}_{category_slug}_{instance_index:02d}"
            instance_dir = dst_root / model_id
            instance_data_dir = instance_dir / "data"
            instance_data_dir.mkdir(parents=True, exist_ok=True)

            copied_solver = instance_dir / solver_path.name
            copied_data = instance_data_dir / data_path.name
            shutil.copy2(solver_path, copied_solver)
            shutil.copy2(data_path, copied_data)

            record = {
                "model_id": model_id,
                "category": category_dir.name,
                "category_slug": category_slug,
                "instance_index": instance_index,
                "solver_file": str(copied_solver.relative_to(dst_root)),
                "data_file": str(copied_data.relative_to(dst_root)),
                "source_solver": str(solver_path),
                "source_data": str(data_path),
            }
            records.append(record)

    manifest = {
        "source_root": str(src_root),
        "dataset_root": str(dst_root),
        "excluded_categories": sorted(EXCLUDED_CATEGORIES),
        "instances_per_category": instances_per_category,
        "category_count": len(categories),
        "model_count": len(records),
        "records": records,
    }
    (dst_root / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return manifest


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the 13-category cp2graph dataset.")
    parser.add_argument("--src-root", default="14类cp问题数据")
    parser.add_argument("--dst-root", default="cp2graph_dataset")
    parser.add_argument("--instances-per-category", type=int, default=2)
    args = parser.parse_args()

    manifest = build_dataset(Path(args.src_root), Path(args.dst_root), args.instances_per_category)
    print(f"built {manifest['model_count']} model workspaces under {manifest['dataset_root']}")


if __name__ == "__main__":
    main()
