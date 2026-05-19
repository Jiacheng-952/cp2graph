from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Set

import networkx as nx
from google.protobuf.json_format import MessageToDict
from google.protobuf.message import Message
from ortools.sat import cp_model_pb2

from cp2graph.hash_utils import semantic_hash


def _variable_domain(domain_values: Iterable[int]) -> Dict[str, Any]:
    values = list(domain_values)
    if values == [0, 1]:
        return {"kind": "bool", "values": None, "lower": 0, "upper": 1}
    if len(values) == 2:
        return {"kind": "int-bounds", "values": None, "lower": values[0], "upper": values[1]}
    return {"kind": "int-set", "values": values, "lower": None, "upper": None}


def _domain_size(domain: Dict[str, Any]) -> float | None:
    if domain["kind"] == "bool":
        return 2.0
    if domain["kind"] == "int-bounds":
        return float(domain["upper"] - domain["lower"] + 1)
    if domain["kind"] == "int-set":
        return float(len(domain["values"]))
    return None


def _literal_to_var_index(value: int) -> int:
    return value if value >= 0 else -value - 1


def _collect_vars_from_message(message: Any) -> Set[int]:
    vars_found: Set[int] = set()
    if isinstance(message, Message):
        for field, value in message.ListFields():
            name = field.name
            if name in {"vars", "literals", "enforcement_literal"}:
                for item in value:
                    vars_found.add(_literal_to_var_index(int(item)))
                continue
            if field.label == field.LABEL_REPEATED:
                for item in value:
                    vars_found.update(_collect_vars_from_message(item))
            else:
                vars_found.update(_collect_vars_from_message(value))
    return vars_found


def _collect_interval_refs(constraint: cp_model_pb2.ConstraintProto) -> Set[int]:
    refs: Set[int] = set()
    ctype = constraint.WhichOneof("constraint")
    if ctype is None:
        return refs
    payload = getattr(constraint, ctype)
    for field, value in payload.ListFields():
        if field.name in {"intervals", "x_intervals", "y_intervals"}:
            refs.update(int(item) for item in value)
    return refs


def proto_to_graph(proto: cp_model_pb2.CpModelProto) -> nx.MultiDiGraph:
    graph = nx.MultiDiGraph()

    for index, var in enumerate(proto.variables):
        node_id = f"v_{index:05d}"
        domain = _variable_domain(var.domain)
        graph.add_node(
            node_id,
            id=node_id,
            type="variable",
            name=var.name or node_id,
            domain=domain,
            size=_domain_size(domain),
            semantic_hash=None,
            is_objective=False,
        )

    direct_vars_by_constraint: List[Set[int]] = []
    interval_refs_by_constraint: List[Set[int]] = []
    for constraint in proto.constraints:
        direct_vars_by_constraint.append(_collect_vars_from_message(constraint))
        interval_refs_by_constraint.append(_collect_interval_refs(constraint))

    for index, constraint in enumerate(proto.constraints):
        node_id = f"c_{index:05d}"
        ctype = constraint.WhichOneof("constraint") or "unknown"
        payload = MessageToDict(
            constraint,
            preserving_proto_field_name=True,
            use_integers_for_enums=True,
        )
        chash = semantic_hash({"type": ctype, "payload": payload})
        graph.add_node(
            node_id,
            id=node_id,
            type="constraint",
            constraint_type=ctype,
            params=payload,
            domain=None,
            size=None,
            semantic_hash=chash,
        )

        var_indices = set(direct_vars_by_constraint[index])
        for interval_index in interval_refs_by_constraint[index]:
            if 0 <= interval_index < len(direct_vars_by_constraint):
                var_indices.update(direct_vars_by_constraint[interval_index])

        for var_index in sorted(var_indices):
            if 0 <= var_index < len(proto.variables):
                var_id = f"v_{var_index:05d}"
                graph.add_edge(var_id, node_id, src=var_id, dst=node_id, role="read")
                graph.add_edge(node_id, var_id, src=node_id, dst=var_id, role="read")
    return graph


def graph_to_json_obj(graph: nx.MultiDiGraph) -> Dict[str, Any]:
    nodes = []
    for _node_id, data in graph.nodes(data=True):
        nodes.append(
            {
                "id": data.get("id"),
                "type": data.get("type"),
                "name": data.get("name"),
                "domain": data.get("domain"),
                "size": data.get("size"),
                "semantic_hash": data.get("semantic_hash"),
                "constraint_type": data.get("constraint_type"),
                "params": data.get("params"),
                "is_objective": data.get("is_objective", False),
            }
        )
    edges = [
        {"src": src, "dst": dst, "role": data.get("role", "read")}
        for src, dst, _key, data in graph.edges(keys=True, data=True)
    ]
    nodes.sort(key=lambda item: (item.get("type") or "", item.get("id") or ""))
    edges.sort(key=lambda item: (item["src"], item["dst"], item["role"]))
    return {"nodes": nodes, "edges": edges}


def _run_capture(script_path: Path, solver_path: Path, workdir: Path, proto_dir: Path, python_bin: str) -> Dict[str, Any]:
    cmd = [
        python_bin,
        str(script_path),
        "--solver",
        str(solver_path),
        "--workdir",
        str(workdir),
        "--out-dir",
        str(proto_dir),
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True, check=False, encoding="utf-8", errors="replace")
    report_line = proc.stdout.strip().splitlines()[-1] if proc.stdout.strip() else "{}"
    try:
        report = json.loads(report_line)
    except json.JSONDecodeError:
        report = {"status": "error", "captured": [], "error": proc.stdout + proc.stderr}
    report["returncode"] = proc.returncode
    report["stdout"] = proc.stdout
    report["stderr"] = proc.stderr
    return report


def convert_dataset(dataset_root: Path, graphs_dir: Path, python_bin: str) -> Dict[str, Any]:
    manifest = json.loads((dataset_root / "manifest.json").read_text(encoding="utf-8"))
    graphs_dir.mkdir(parents=True, exist_ok=True)
    proto_capture = Path(__file__).with_name("_capture_ortools_proto.py")

    records = []
    failures = []
    for record in manifest["records"]:
        model_id = record["model_id"]
        instance_dir = dataset_root / model_id
        solver_path = dataset_root / record["solver_file"]
        proto_dir = instance_dir / "proto"
        proto_dir.mkdir(parents=True, exist_ok=True)

        capture_report = _run_capture(proto_capture, solver_path, instance_dir, proto_dir, python_bin)
        captured = [Path(path) for path in capture_report.get("captured", [])]
        if not captured:
            failures.append({"model_id": model_id, "stage": "proto", "report": capture_report})
            continue

        proto_path = captured[0]
        proto = cp_model_pb2.CpModelProto()
        proto.ParseFromString(proto_path.read_bytes())
        graph = proto_to_graph(proto)

        graph_path = graphs_dir / f"{model_id}.graph.json"
        graph_path.write_text(
            json.dumps(graph_to_json_obj(graph), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        records.append(
            {
                **record,
                "proto_file": str(proto_path),
                "graph_file": str(graph_path),
                "node_count": graph.number_of_nodes(),
                "edge_count": graph.number_of_edges(),
                "variable_count": sum(1 for _n, d in graph.nodes(data=True) if d.get("type") == "variable"),
                "constraint_count": sum(1 for _n, d in graph.nodes(data=True) if d.get("type") == "constraint"),
                "capture_returncode": capture_report["returncode"],
                "capture_warning": capture_report.get("error") if capture_report["returncode"] != 0 else None,
            }
        )

    result = {
        "dataset_root": str(dataset_root),
        "graphs_dir": str(graphs_dir),
        "ok": len(records),
        "failed": len(failures),
        "records": records,
        "failures": failures,
    }
    (dataset_root / "conversion_manifest.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Capture OR-Tools protos and build bipartite graphs.")
    parser.add_argument("--dataset-root", default="cp2graph_dataset")
    parser.add_argument("--graphs-dir", default="cp2graph_dataset/graphs")
    parser.add_argument("--python-bin", default=sys.executable)
    args = parser.parse_args()

    result = convert_dataset(Path(args.dataset_root), Path(args.graphs_dir), args.python_bin)
    print(f"converted {result['ok']} graphs; failed {result['failed']}")


if __name__ == "__main__":
    main()
