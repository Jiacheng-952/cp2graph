# proto_solver_pack_v1 流程总览

## 1. 这条链路在做什么

这条链路不再从 log 里“重建模型代码”，而是直接使用 `14类cp问题数据/` 里每一类原生 solver：

`类别 solver.py/solve.py + 类别 data/*.json -> CpModel -> CpModelProto -> 二分图`

## 2. 原料从哪里来

每个类别都有自己的输入数据：

- `14类cp问题数据/<类别>/data/*.json`

每个类别都有自己的求解器：

- `14类cp问题数据/<类别>/solver.py`
- 或 `14类cp问题数据/<类别>/solve.py`

例如：

- `Batch Scheduling Problem`
- `Job Shop Scheduling Problem (JSSP)`
- `Open Shop Scheduling Problem`

## 3. 关键脚本

### `create_solver_proto_pack.py`

作用：

- 复制 14 类 solver 文件到 `pipeline_cp_log_to_bigraph/proto_solver_pack_v1/`
- 同时复制每一类的 `data/`
- 在 solver 末尾注入统一的 `build_model()` / `build_proto()` 适配器

产物：

- `proto_solver_pack_v1/<类别>/solver.py` 或 `solve.py`
- `proto_solver_pack_v1/<类别>/data/`
- `proto_solver_pack_v1/PACK_INDEX.json`

### `generate_category_protos.py`

作用：

- 为每一类选择一个实例数据
- 先尝试按脚本方式运行 solver
- 再尝试函数式调用 solver
- 捕获 `CpModel`
- 调用 `model.Proto()`
- 保存 `model.proto.pb`

实例数据来源优先级：

1. `artifacts/extracted_records.json` 里该类别对应的 `context.data_file`
2. 类别目录下第一个 `data/*.json`

输出：

- `proto_solver_pack_v1/<类别>/model.proto.pb`
- `proto_solver_pack_v1/proto_manifest.json`

### `build_graphs_from_category_protos.py`

作用：

- 读取 `model.proto.pb`
- 用 `CpModelProto` 构造变量-约束二分图
- 写出图 JSON

输出：

- `proto_solver_pack_v1/bipartite_graphs/graph_*.json`
- `proto_solver_pack_v1/graph_index.json`
- `proto_solver_pack_v1/graph_manifest.json`
- `proto_solver_pack_v1/conversion_failures.json`

## 4. Proto 是怎么返回出来的

核心逻辑在 `generate_category_protos.py`：

1. 调用 solver
2. 用 `CpModel` 构造器拦截器记录模型实例
3. 如果脚本式入口创建了模型，就直接抓住
4. 如果函数式入口返回模型，就直接拿返回值
5. 最后统一执行：

```python
proto = model.Proto()
```

`proto` 不是求解结果，而是模型的结构化表示。

## 5. 一个例子

### 成功例子

`Batch Scheduling Problem`

- 实例：`generated_instance_01.json`
- Proto：`proto_solver_pack_v1/Batch Scheduling Problem/model.proto.pb`
- 图：`proto_solver_pack_v1/bipartite_graphs/graph_0001.json`

### 失败例子

`Flexible Job Shop Problem (FJSP)`

- 当前失败原因：`No CpModel captured`
- 含义：solver 运行了，但没有稳定暴露出可捕获的 `CpModel`

`gortek`

- 当前失败原因：`No module named 'docplex'`
- 含义：环境缺少依赖，不是 Proto 本身的问题

## 6. 当前状态

当前这条链路成功率是 `11/14`。

