这个项目做的是：**给一个 Lean4 目标/表达式，自动从 Mathlib4 里找最可能有用的定理或引理**。这就是论文标题里的 premise selection，中文可以理解成“前提/引理检索”。

**论文核心**
传统工具多用文本或语义 embedding 检索；这篇论文认为 Lean 表达式本身是树结构，应该直接利用结构信息。流程大概是：

1. 把 Lean 表达式解析成 `Expr Tree`。
2. 用 CSE 消除公共子表达式，把重复结构压缩成变量，降低冗余。
3. 用 WL kernel 给树做结构编码，先从 Mathlib 里粗筛候选定理。
4. 对候选定理再精排，融合：
   - WL 结构相似度
   - Tree Edit Distance 树编辑距离
   - `Const` 节点名字的 Jaccard 相似度
   - Collapse-Match 结构塌缩匹配相似度
5. 返回最相似的一批 theorem。

可以把它理解成：**不是问“这句话语义像不像”，而是问“这两个 Lean 内部表达式树长得像不像，关键常量是否重合，结构能不能对齐”。**

**代码怎么对应论文**
入口在 [README.md](E:/01SHU/01_work/01OPT/tbps/README.md:1)，项目分成后端、前端、Lean 工具和数据：

- `tbps-be/Lean_tool/Mathlib_Construction.lean`：把用户输入的 Lean 表达式解析成 JSON 树。
- [myexpr.py](E:/01SHU/01_work/01OPT/tbps/tbps-be/search_app/myexpr.py:1)：Python 里复刻 Lean 表达式节点类型。
- [cse.py](E:/01SHU/01_work/01OPT/tbps/tbps-be/search_app/cse.py:196)：公共子表达式消除。
- [WL_embedding/wl_kernel.py](E:/01SHU/01_work/01OPT/tbps/tbps-be/search_app/WL_embedding/wl_kernel.py:78)：WL 编码和 WL 相似度。
- [zss_compute.py](E:/01SHU/01_work/01OPT/tbps/tbps-be/search_app/compute/zss_compute.py:132)：树编辑距离、常量名相似度、collapse-match。
- [process_single.py](E:/01SHU/01_work/01OPT/tbps/tbps-be/search_app/process_single.py:345)：实际检索主流程。
- [base_server.py](E:/01SHU/01_work/01OPT/tbps/tbps-be/base_server.py:67)：FastAPI 接口 `/find-similar-theorems`。
- `tbps-fe/`：Next.js 前端网页，用来输入 Lean 表达式并展示结果。

**一次查询的真实流程**
用户输入：

```lean
∀ (a b : Nat), a + b = b + a
```

后端会：

1. 调 Lean，把它转成 Lean 内部表达式树。
2. Python 反序列化成 `YourExpr`。
3. 做 CSE 简化。
4. 算目标树的 WL encoding。
5. 在 PostgreSQL 里的 Mathlib 定理库中，用节点数量范围 + WL 分数筛出约 `top_k = 1500` 个候选。
6. 对候选用树编辑距离等指标重排。
7. 返回类似 `Nat.add_comm` 这样的相关定理。

**数据部分**
[data/README.md](E:/01SHU/01_work/01OPT/tbps/data/README.md:1) 说明这里有：

- `mathlib_filtered`：过滤后的 Mathlib 定理库。
- `wl_encodings_new`：预计算好的 WL/tree 编码。
- `expressions.txt` 和 `Prop_name.txt`：测试集 A。
- `test_set_B_tactic_step.sql.tar.gz`：从 Lean proof trace 里抽出来的测试集 B。

**一句话总结**
这篇论文和项目是在做一个 **Lean4 定理搜索器**：它把目标和库中定理都变成表达式树，通过结构相似度而不是单纯文本/embedding 来找可用引理，目标是提升自动证明或交互式证明时的检索准确率。

## 补充问题与回答

### 1、这个 Lean 转换为 Lean 内部表达式树是如何转化的？转化逻辑是什么？

项目里的转换入口在 `tbps-be/Lean_tool/Mathlib_Construction.lean`。整体逻辑是：先让 Lean 自己把用户输入的字符串解析、elaboration 成 Lean 内核里的 `Expr`，再把这个 `Expr` 递归转换成项目自定义的、可以序列化成 JSON 的 `YourExpr`。

具体过程如下：

1. 后端把用户输入写入 `tbps-be/Lean_tool/input_expr.txt`。
2. Python 调用 `lake exe Mathlib_Construction`。
3. Lean 程序读取 `input_expr.txt`，调用 `parseStringToExpr`。
4. `parseStringToExpr` 先用 `Lean.Parser.runParserCategory env \`term input` 把字符串解析成语法树，再用 `elabTerm stx none` 把语法树 elaboration 成 Lean 内部核心表达式 `Expr`。
5. `processSingleProp` 对得到的 `Expr` 调用 `instantiateMVars`，尽量把已经确定的 metavariable 实例化。
6. `exprToYourExprIter` 遍历 Lean 的 `Expr` 树，把每个 Lean 原生节点转换成项目自己的 `YourExpr` 节点。
7. 最后写出 `expr_output.json`，里面包含 `input_str`、`expr_dbg`、`your_expr`。

节点映射逻辑主要在 `reconstruct` 函数里：

| Lean 原生 `Expr` | 项目里的 `YourExpr` | 含义 |
|---|---|---|
| `Expr.bvar idx` | `YourExpr.bvar idx` | de Bruijn 绑定变量 |
| `Expr.fvar fvarId` | `YourExpr.fvar ...` | 自由变量 |
| `Expr.mvar mvarId` | `YourExpr.mvar ...` | 元变量 |
| `Expr.sort lvl` | `YourExpr.sort ...` | universe / type level |
| `Expr.const n us` | `YourExpr.const n us` | 常量、定理名、定义名等 |
| `Expr.app f a` | `YourExpr.app f' a'` | 函数应用 |
| `Expr.lam bn t b bi` | `YourExpr.lam ...` | lambda 抽象 |
| `Expr.forallE bn t b bi` | `YourExpr.forallE ...` | forall / 依赖函数类型 |
| `Expr.letE dn t v b nd` | `YourExpr.letE ...` | let 表达式 |
| `Expr.lit lit` | `YourExpr.lit ...` | 字面量 |
| `Expr.mdata data e` | `YourExpr.mdata ...` | metadata 包裹 |
| `Expr.proj tn idx s` | `YourExpr.proj ...` | 结构体投影 |

所以这里不是手写一个 Lean 语法解析器，而是借助 Lean 本身完成“从表层语法到内核表达式”的转换。项目做的是第二步：把 Lean 内核 `Expr` 转成跨语言可处理的 JSON 树。

举例来说，表面输入：

```lean
∀ (a b : Nat), a + b = b + a
```

Lean 不会只把它当成一串文本，而会 elaboration 成一棵由 `forallE`、`app`、`const`、`bvar/fvar` 等节点组成的内部表达式树。其中 `+`、`=`、`Nat` 等都会变成具体的常量节点或应用节点；隐式参数、类型类实例等也可能被 Lean 自动补出来。

### 2、这个转化的过程有语义丢失吗？

需要分两层看。

第一层：从 Lean 表面语法到 Lean 内部 `Expr`，一般不是“语义丢失”，而是“语义展开和规范化”。Lean 的 elaborator 会把记号、隐式参数、类型类实例、重载解析等都转成内核能检查的表达式。因此，表面写法的信息会变化，比如：

- `a + b` 不再只是文本里的 `+`，而会变成对应加法常量、类型类实例和参数应用；
- 简写、notation、语法糖会消失；
- 隐式参数可能会被显式补入；
- 类型类实例可能会展开成很大的子树；
- 源码里的排版、括号风格、用户原始变量命名风格等不再重要。

这意味着：**表层语法信息会丢失，但 Lean 内核用于类型检查和证明检查的核心语义通常被保留下来，甚至被显式化了。**

第二层：从 Lean `Expr` 到项目的 `YourExpr`，会有一些表示层面的简化。项目保留了主要结构节点和关键字段，例如 `const` 的声明名、`app` 的函数和参数、`forallE` 的 binder 类型和 body 等。但也有一些潜在损失：

- 一些 Lean 对象通过 `repr` 转成字符串，后续不一定能无损还原为 Lean 原对象；
- 原始源码位置、注释、具体 notation 信息不会保留；
- metadata 只作为字符串保存；
- 后续 Python 侧会做 CSE 和简化，这一步会主动牺牲部分细节来增强结构匹配。

尤其要注意，项目真正用于检索的不是最原始的 `YourExpr`，而是经过处理后的树：

1. `cse` 会把重复出现的子表达式替换成新的自由变量 `FVar(v0)`、`FVar(v1)` 等，常量除外；
2. `simplify_forall_expr_iter` 会简化一些 `forall` 结构；
3. WL 编码时，`BVar`、`FVar`、`MVar`、`Sort`、`Const` 这类节点会被进一步按前缀归一化，很多具体名字不参与 WL 标签；
4. 树编辑距离里，变量、类型、常量类节点的替换成本被设置得较低，甚至某些情况下近似忽略具体名字。

所以结论是：

**Lean 转成内部 `Expr` 本身主要是语义显式化，不是语义丢失；但项目为了做结构检索，会在 CSE、forall 简化、WL 标签归一化、树编辑距离成本设计中主动丢掉或弱化一部分细节。**

这样做的目的不是完整还原 Lean 表达式，而是让“结构相似”更稳定、更便宜。例如两个定理变量名不同，但结构相同，检索时应该认为它们相似；如果完全保留变量名，反而会影响匹配。

不过这种方法也有代价。论文里也指出，Lean 的定义展开和类型类实例会导致结构差异。例如 `n.succ` 和 `n + 1` 在数学上很接近，但在 Lean 内部树上可能差很多；某些隐式实例也会膨胀成很大的子树。这类情况会影响树结构检索的准确性。

### 3、详细解释后面筛选的逻辑过程

后面的筛选主要在 `tbps-be/search_app/process_single.py` 和 `tbps-be/search_app/WL/db_utils.py` 里完成。它不是一次性拿输入和 Mathlib 里所有定理做昂贵比较，而是分成“粗筛 + 精排”两阶段。

#### 3.1 查询入口

网页或 API 调用 `/find-similar-theorems` 后，后端进入 `ProductionHandler.find_similar_theorems`：

1. 调 Lean，把输入表达式转成 JSON；
2. Python 用 `deserialize_expr` 把 JSON 变成 `YourExpr`；
3. 对表达式做 `cse`；
4. 调用 `process_single_prop_new(cse_expr, k)` 检索相似定理。

#### 3.2 目标表达式预处理

`process_single_prop_new` 会先把目标表达式变成树：

```python
target_tree = your_expr_to_treenode(target_expr)
target_node_count = count_nodes(target_tree)
```

这里的 `TreeNode` 是检索用的通用树节点，只保留：

- `label`：节点标签，比如 `App`、`Const(Nat.add, ...)`；
- `children`：子节点列表。

然后设置候选规模和节点数量过滤参数：

```python
top_k = 1500
node_ratio = 1.2
if target_node_count >= 600:
    node_ratio = 1.8
```

也就是说，系统会先从数据库里取出最多约 1500 个候选定理做精排。目标树特别大时，节点数量范围放宽。

#### 3.3 第一阶段：节点数量过滤

进入 `load_filtered_theorems` 后，系统会先对目标表达式再做一次 forall 简化：

```python
simptree = simplify_forall_expr_iter(target_expr)
target_tree = your_expr_to_treenode(simptree)
target_simp_node_count = count_nodes(target_tree)
```

然后计算节点数量范围：

```python
min_nodes = min(target_node_count / node_ratio, target_node_count - node_diff)
max_nodes = max(target_node_count * node_ratio, target_node_count + node_diff)
```

默认 `node_ratio = 1.2`，`node_diff = 25`。这一步的直觉是：如果两个表达式树大小差太多，它们很可能不是同类定理。例如一个 20 个节点的目标，不太可能和一个 2000 个节点的定理高度相似。

数据库查询时只保留：

- `expr_cse_json != 'null'`；
- `simp_node_count` 落在节点范围内；
- 如果开启 clustering，还会限制在相近聚类里。

当前 `process_single_prop_new` 调用里设置的是：

```python
use_clustering=False
wl_iterations=3
```

所以当前在线检索主要使用节点数量过滤 + WL 粗排，没有启用聚类过滤。

#### 3.4 第二阶段：WL 编码粗排

系统会给目标树计算 WL encoding：

```python
target_encoding, _ = compute_wl_encoding(target_tree, max_h=wl_iterations)
```

WL encoding 可以理解为“树结构指纹”。它会迭代地把一个节点及其子节点标签合并、哈希，并统计各种结构标签出现次数。这样得到的不是单个字符串，而是一个类似词袋的结构直方图：

```text
{
  "0_xxxhash": 3,
  "1_yyyhash": 1,
  ...
}
```

数据库里的 Mathlib 定理已经预计算过 WL encoding，存在 `wl_encodings_new` 表中，例如 `simp_wl_encode_3`。

对于每个候选定理，系统计算：

```python
wl_score = compute_wl_kernel(target_encoding, theorem_encoding)
```

这里的 WL kernel 实际是两个结构直方图的余弦相似度：

```text
score = dot(wl1, wl2) / (norm(wl1) * norm(wl2))
```

分数越高，说明两棵树的局部结构模式越相似。

所有候选按 `wl_score` 降序排序，只取前 `top_k = 1500` 个进入下一阶段。

#### 3.5 第三阶段：加载候选定理并构造树

粗筛得到的是定理名和 WL 分数。接下来 `precompute_candidates` 会根据这些定理名从 `mathlib_filtered` 表里取出：

```sql
SELECT name, expr_cse_json
FROM mathlib_filtered
WHERE name IN (...)
```

然后对每个候选：

1. `deserialize_expr(expr_json)`：反序列化候选定理表达式；
2. `simplify_forall_expr_iter`：简化 forall；
3. `your_expr_to_treenode`：转成 `TreeNode`；
4. `can_t1_collapse_match_t2_soft`：先算一个 collapse-match 相似度；
5. `count_nodes`：记录候选树节点数。

这一步是并行做的，用了 `ProcessPoolExecutor`。

#### 3.6 第四阶段：精排相似度计算

精排逻辑在 `process_theorem` 中。它把多个分数融合成最终相似度。

对于普通大小的目标树，会计算树编辑距离：

```python
distance = zss_edit_distance_TreeNode(target_tree, theorem_tree)
similarity = 1 - distance / max(target_size, theorem_size)
```

树编辑距离表示：把一棵树变成另一棵树，最少需要多少插入、删除、替换操作。距离越小，结构越相似。

项目对编辑成本做了 Lean 特化：

- `BVar`、`FVar`、`MVar`、`Sort`、`Const` 这类节点插入/删除成本较低；
- 如果两个节点完全相同，替换成本为 0；
- 如果任一节点属于上述前缀，替换成本也较低或接近 0；
- 其他结构节点不一样时成本更高。

这表示系统更重视整体表达式骨架，比如 `App`、`ForallE`、`Lam` 的结构；对变量名、类型层级、部分常量细节相对宽容。

最终普通目标树使用这个融合公式：

```python
alpha, beta, gamma, delta = 0.15, 0.40, 0.30, 0.15
final =
    alpha * wl_score
  + beta  * edit_similarity
  + gamma * collapse_match_similarity
  + delta * const_decl_name_similarity
```

四个指标的含义：

- `wl_score`：全局/局部结构模式是否相似；
- `edit_similarity`：两棵树通过编辑操作能否低成本互相变换；
- `collapse_match_similarity`：候选结构能否通过“塌缩”方式和目标局部对齐；
- `const_decl_name_similarity`：两棵树里出现的 Lean 常量名集合重合程度。

如果目标树太大，代码中会跳过昂贵的树编辑距离：

```python
if target_size > 50:
    alpha, gamma, delta = 0.15, 0.30, 0.15
    similarity =
        alpha * wl_score
      + gamma * syntactic_similarity
      + delta * const_decl_name_similarity
```

这里没有 `beta * edit_similarity`，因为大树上 TED 计算太慢。注意这三个权重加起来不是 1，所以这个分支下的分数更像排序用的综合打分，不一定是严格归一化概率。

#### 3.7 第五阶段：排序、补充定理信息、返回

所有候选算完最终分数后：

```python
results.sort(key=lambda x: x[1], reverse=True)
```

然后取前 `k` 个结果。对每个结果，再从数据库取：

```sql
SELECT statement_str, node_count
FROM mathlib_filtered
WHERE name = ...
```

最终返回给前端：

- 定理名 `name`；
- 综合相似度 `similarity_score`；
- 定理陈述 `statement`；
- 节点数 `node_count`。

#### 3.8 总结成一句流程

完整检索链路可以压缩成：

```text
Lean 输入
  -> Lean elaboration 成 Expr
  -> Expr JSON
  -> Python YourExpr
  -> CSE 简化
  -> TreeNode
  -> 节点数量过滤
  -> WL encoding 粗排，取 top 1500
  -> 候选定理反序列化并转树
  -> TED / Collapse-Match / Const Jaccard / WL 融合精排
  -> 返回 top k 相似定理
```

所以这个系统的核心思想是：**先用便宜的结构指纹快速缩小范围，再用更贵但更精细的树相似度指标对候选重新排序。**
