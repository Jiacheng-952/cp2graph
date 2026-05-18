# proto_solver_pack_v1

这是 v1 的自洽工作区。

## 目录职责

- `flow/`：v1 本地流程脚本（含一键入口）
- `docs/`：v1 方案与测试文档
- `<类别>/solver.py|solve.py`：每类求解器副本
- `<类别>/data/*.json`：每类实例数据副本
- `<类别>/model.proto.pb`：每类最新 proto
- `bipartite_graphs/`：当前成功生成的二分图
- `proto_manifest.json`：proto 阶段统计
- `graph_manifest.json`：图阶段统计
- `graph_index.json`：图文件索引
- `conversion_failures.json`：失败明细

## 一键运行

```bash
python pipeline_cp_log_to_bigraph/proto_solver_pack_v1/flow/run_v1_pipeline.py
```
