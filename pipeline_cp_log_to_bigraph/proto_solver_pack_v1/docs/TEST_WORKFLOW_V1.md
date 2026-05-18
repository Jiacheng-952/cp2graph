# proto_solver_pack_v1 测试流程

## 1. 一次测试做什么

完整顺序：

1. 刷新本地 solver 包
2. 生成每类 proto
3. 生成二分图
4. 写 manifest / failure / index

## 2. 一键命令

```bash
python pipeline_cp_log_to_bigraph/proto_solver_pack_v1/flow/run_v1_pipeline.py
```

可选：指定解释器

```bash
python pipeline_cp_log_to_bigraph/proto_solver_pack_v1/flow/run_v1_pipeline.py --python-bin D:\ProgramAnaconda\envs\optagent_fixed\python.exe
```

## 3. 逐步命令（调试用）

```bash
python pipeline_cp_log_to_bigraph/proto_solver_pack_v1/flow/create_solver_proto_pack.py --src-root "14类cp问题数据" --dst-root "pipeline_cp_log_to_bigraph/proto_solver_pack_v1"
python pipeline_cp_log_to_bigraph/proto_solver_pack_v1/flow/generate_category_protos.py --solver-pack "pipeline_cp_log_to_bigraph/proto_solver_pack_v1" --out-dir "pipeline_cp_log_to_bigraph/proto_solver_pack_v1"
python pipeline_cp_log_to_bigraph/proto_solver_pack_v1/flow/build_graphs_from_category_protos.py --proto-manifest "pipeline_cp_log_to_bigraph/proto_solver_pack_v1/proto_manifest.json" --graphs-dir "pipeline_cp_log_to_bigraph/proto_solver_pack_v1/bipartite_graphs" --index-json "pipeline_cp_log_to_bigraph/proto_solver_pack_v1/graph_index.json" --fail-log "pipeline_cp_log_to_bigraph/proto_solver_pack_v1/conversion_failures.json" --manifest-json "pipeline_cp_log_to_bigraph/proto_solver_pack_v1/graph_manifest.json"
```

## 4. 每一步输出什么

- `PACK_INDEX.json`：solver+data 同步索引
- `proto_manifest.json`：每类 proto 成功/失败统计
- `bipartite_graphs/graph_*.json`：二分图结果
- `graph_manifest.json`：图生成统计
- `graph_index.json`：图文件与类别映射
- `conversion_failures.json`：失败明细

## 5. 覆盖规则

会覆盖：

- `model.proto.pb`
- `proto_manifest.json`
- `graph_manifest.json`
- `graph_index.json`
- `conversion_failures.json`
- `bipartite_graphs/*.json`

会保留：

- `docs/`
- 类别原始 `data/`

## 6. 链路通畅判定

本轮成功条件：

1. `proto_manifest.json` 中 `ok >= 13`
2. `graph_manifest.json` 中 `ok == proto_manifest.ok`
3. `conversion_failures.json` 只剩已知依赖问题（当前是 `gortek/docplex`）

## 7. 常见问题定位

1. `No module named ...`：环境依赖缺失
2. `No CpModel captured`：该类别 solver 入口未被捕获
3. `invalid json instance`：该类别实例字段契约不匹配
