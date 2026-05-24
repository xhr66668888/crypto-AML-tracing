# 三天可用版交付计划（角色分工版）

计划周期：原 2026-05-15 至 2026-05-17 的三天分段计划已折叠为一次性并行交付；本文件中的"Day 1 / Day 2 / Day 3"现在只作为依赖顺序参考。
目标：交付一个可被真实风控人员使用的 V1，由 10 个 ownership 角色协同完成。分工细节见 [team-assignments.md](team-assignments.md)，必读 skill 索引见 [agent-skills.md](agent-skills.md)。

## 1. 可用版定义

三天内必须交付的"可用版"是：

- 能部署并稳定运行前后端；
- 能对 ETH/USDT/USDC 的出入金地址做实时筛查；
- 能输入地址或交易哈希做深度调查；
- 能展示交易图谱、风险分、风险等级、处置建议、Pattern Analysis、Source Hits、证据列表；
- 能导入本地黑名单/watchlist，并让 OFAC/PEP/制裁/稳定币黑名单类标签触发强制人工 HOLD；
- 能生成可读的风险解释报告；
- 有基础测试、运行文档、验收脚本和失败排查路径。

三天内不承诺完整商业级能力的是：

- 真实 PEP 商业库接入；
- Circle/Tether 官方或链上黑名单全量同步；
- 多链扩展到 Tron/BSC/Polygon；
- 真实 ML/Raindrop 训练；
- 企业级权限、审批流、审计后台。

预留接口可以，不能假装已经生产可用。

## 2. 角色分工总览

### 评审角色

- **`aml-architect`**：API 契约、`docs/database/schema.sql`、`.env.example`、模块边界、direct-hit 政策、release checklist。
- **`risk-logic-reviewer`**（read-only）：Pattern 正确性、scoring 校准、direct-hit 语义、报告幻觉风险、证据链完整性。

### 执行角色

- **`connector-engineer`**：`services/api/app/connectors/` 与 DeepSeek HTTP 层。
- **`graph-pattern-engineer`**：`graph_builder.py` 与 `patterns.py`。
- **`risk-intel-engineer`**：`risk_intel.py`、规则评分、watchlist 导入与 direct-hit 类目。
- **`raindrop-ml-engineer`**：`services/api/app/ml/` 与未来 `services/ml/raindrop_aml/`。
- **`report-engineer`**：`services/api/app/services/reporting.py`。
- **`web-workbench-engineer`**：`apps/web/`。
- **`qa-devops-engineer`**：`infra/scripts/`、`.github/workflows/`、`docker-compose.yml`、`pytest.ini`、smoke、`.env.example` 实施。
- **`db-storage-engineer`**：`docs/database/schema.sql` 与 `services/api/app/storage/` 适配器。

### 调度边界

- `aml-architect` 是唯一的 contract owner。任何动 API/schema/env/模块边界的改动，必须先由它写或更新契约，执行角色才能落地。
- `risk-logic-reviewer` 不写产品代码。所有动 scoring/patterns/direct-hit/report 的改动合并前必须拿到它的 verdict。
- 执行角色只改自己 OWNED 的文件。跨界路由经 `aml-architect`。

## 3. 三天日程

### Day 1：2026-05-15，打通真实可用闭环

并行执行：

- `aml-architect`：固化 API 契约与错误模型；梳理 `.env.example`（`DEMO_MODE`、`ETHERSCAN_API_KEY`、`GOPLUS_TOKEN`、`DEEPSEEK_API_KEY`、节点上限、CORS）；批准 watchlist 导入端点的 DTO。
- `connector-engineer`：加强 `EtherscanClient` 与 `GoPlusClient`：超时、HTTP 错误、空数据、限流、provider 异常返回；所有异常以结构化错误返回，不让 API 直接 500；demo 与真实模式行为分明。
- `risk-intel-engineer`：完成 watchlist CSV/JSON 导入与 direct-hit 实现；`category` ∈ {ofac, pep, sanctions, circle_blacklist, tether_blacklist, stablecoin_blacklist} 时强制 `hold_for_manual_review`。
- `web-workbench-engineer`：按现有 Wise 风格做第一轮可用性整理：筛查区放在最显眼位置；风险等级与处置建议第一眼可见；Pattern Signals 与 Source Hits 不埋底；错误提示能被风控人员看懂；FastAPI `detail` 翻成人话；loading/disabled 状态完整。
- `qa-devops-engineer`：固定后端启动方式 `PYTHONPATH=.python-deps:services/api python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000`；检查 `pytest`、`npm run build` 可跑。

`risk-logic-reviewer` 检查点（read-only）：

- review API 错误模型；
- review watchlist direct-hit 逻辑；
- review 前端是否把 demo provider 当作真实情报。

Day 1 验收：

- 后端能启动；
- 前端能打开；
- 筛查接口能返回风险分与处置建议；
- watchlist 导入一个 OFAC demo 地址后，出金到该地址必须返回 `hold_for_manual_review`；
- `pytest` 通过；
- `npm run build` 通过。

### Day 2：2026-05-16，补齐调查与解释能力

并行执行：

- `graph-pattern-engineer`：上线九类 Pattern 检测（Layering、Aggregation、Peel Chain、阈值拆分、高频小额、Dusting、一次性地址、中心节点、风险传播）。每个 `PatternSignal` 必须带 `name / severity / score / subject / evidence / confidence / metadata`。补 Pattern fixtures。
- `risk-intel-engineer`：与 `aml-architect` 对齐后定型 rule 权重；保证 direct-hit 永远盖过普通行为分。
- `report-engineer`：报告必须解释风险分、source hit、pattern signal、处置建议；没有证据时必须写"未发现证据"，不能编造；ML/Raindrop 只能作为辅助信号。补本地 fallback 模板。
- `web-workbench-engineer`：图谱区加载前/中/失败/成功状态完整；点击节点展示标签、风险分、hop、source；风险摘要展示 `Rule / Raindrop / Final / Disposition`；Evidence、Pattern Signals、Source Hits 排序与限量；报告区显示生成状态、失败状态、报告来源。
- `raindrop-ml-engineer`：保持确定性 adapter 不破坏 `predict(graph)` 接口；写好 features 文档。
- `qa-devops-engineer`：添加 OFAC direct-hit、PEP direct-hit、Dusting、Aggregation、Peel Chain、阈值拆分六类测试 fixture。

`risk-logic-reviewer` 检查点：

- review Pattern 是否过度误报；
- review 报告是否有幻觉风险；
- review 页面是否把 direct-hit 与普通 pattern risk 区分清楚。

Day 2 验收：

- 地址调查能完整展示图谱、风险摘要、证据、模式信号；
- 报告能解释风险原因；
- 至少 6 类风控场景有测试；
- 前端移动端不溢出、不重叠。

### Day 3：2026-05-17，稳定性、部署、交付验收

并行执行：

- `qa-devops-engineer`：后端启动脚本、前端构建/preview、`.env` 配置说明、provider key 缺失时的行为、demo↔production 切换说明；smoke 脚本覆盖 `/health`、`/api/v1/screening/transactions`、`/api/v1/investigations`、`/{id}/graph`、`/{id}/risk`、`/{id}/reports`。
- `db-storage-engineer`：检查 schema 与当前 `InMemoryStore` 差异，写清楚下一阶段 PostgreSQL 替换路径，并给出 swap 顺序。
- `web-workbench-engineer`：1440px、1180px、390px 桌面与窄屏验收；字体加载、长地址、大量证据、后端错误、长报告全部不破布局；准备操作手册（如何做出金筛查、如何导入 watchlist、如何调查地址、如何解释 8/10 或 80/100 风险分、什么情况人工 HOLD）。
- `connector-engineer`、`graph-pattern-engineer`、`risk-intel-engineer`、`raindrop-ml-engineer`、`report-engineer`：根据 `risk-logic-reviewer` 的 Day 2 verdicts 收尾。

`aml-architect` 最终检查：

- 全量 review API 输出是否一致；
- 检查 direct-hit 是否优先于评分；
- 检查没有把 demo 数据说成真实情报；
- 检查测试与运行文档；
- 整理 known limitations（不允许模糊语言）；
- 给出最终 release checklist。

Day 3 验收：

- 新机器按文档能跑起来；
- 真实 key 缺失时 demo mode 可跑；
- 真实 key 配置后 connector 不崩；
- watchlist direct-hit 可验证；
- 风控人员能完成筛查、调查、报告生成；
- 构建与测试全部通过。

## 4. 具体任务拆分（按角色）

### `aml-architect`

1. 冻结 V1 API 契约（screening、investigations、watchlist、reports）。验收：所有 endpoint 有请求/响应样例。
2. 批准 `.env.example` 字段集合。验收：与 `services/api/app/core` 配置一致。
3. 输出 release checklist 与 known-limitations。验收：Day 3 末尾签字。

### `risk-logic-reviewer`

1. Day 1：review watchlist direct-hit、API 错误模型、demo→真实情报描述。
2. Day 2：review Pattern 误报、报告幻觉、前端 direct-hit 区分。
3. Day 3：最终签字 + 红线项清单。

### `connector-engineer`

1. Etherscan/GoPlus 错误处理、超时、限流、空数据；DeepSeek HTTP 重试。验收：四类异常都有结构化错误。
2. demo↔真实模式互斥；缓存不污染。

### `graph-pattern-engineer`

1. 9 类 Pattern 检测；每个信号字段完整。
2. 补 fixtures 至少覆盖 6 个场景。
3. 性能不退化。

### `risk-intel-engineer`

1. Watchlist CSV/JSON 导入。验收：导入 OFAC demo 地址后筛查命中 `hold_for_manual_review`。
2. Direct-hit 类目锁定；rule 权重与 `risk-logic-reviewer` 校准。
3. 文档化 source-hit 字段。

### `raindrop-ml-engineer`

1. 确定性 scorer 保持稳定。
2. 写好真实模型迁移的 acceptance（CPU 推理、AUPRC/AUROC/Precision@K/Recall@K、版本化）。

### `report-engineer`

1. DeepSeek 与本地模板路径都跑通。
2. 没有证据时写"未发现证据"。
3. demo-mode 报告头标注 demonstration。

### `web-workbench-engineer`

1. 筛查区生产可用；风险分、等级、处置一眼可见。
2. 调查区图谱、风险摘要、证据、模式信号、来源命中信息分层清晰。
3. 错误与空状态完整。
4. 三种宽度无溢出。
5. 操作手册（中文）。

### `qa-devops-engineer`

1. 启动脚本与 smoke 一条命令跑完。
2. CI 跑 `pytest` 与 `npm run build`。
3. 部署/运行文档。

### `db-storage-engineer`

1. 校对 `docs/database/schema.sql` 与当前 `InMemoryStore`。
2. 写出 swap 路径文档；不在 V1 内强制切换 Postgres。

## 5. 每天必须跑的命令

后端：

```bash
PYTHONPATH=services/api pytest -q
```

前端：

```bash
cd apps/web
npm run build
```

本地运行：

```bash
PYTHONPATH=.python-deps:services/api python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
cd apps/web && npm run dev
```

健康检查：

```bash
curl -s http://localhost:8000/health
```

筛查 smoke：

```bash
curl -s -X POST http://localhost:8000/api/v1/screening/transactions \
  -H 'Content-Type: application/json' \
  -d '{
    "chain_id":"1",
    "asset":"USDC",
    "direction":"outbound",
    "from_address":"0x8a5847fd0e592b058c026c5fdc322aee834b87f5",
    "to_address":"0x1111111111111111111111111111111111111111",
    "amount":9500
  }'
```

## 6. 不可妥协验收标准

- Direct-hit 必须强制人工 HOLD。
- 每个风险结论必须有 evidence。
- Demo 数据不能被描述成真实命中。
- Provider 错误不能导致页面崩溃。
- 前端长地址不能撑破布局。
- 报告不能编造法律结论。
- `pytest` 与 `npm run build` 必须通过。
- 文档必须能让新机器跑起来。
- 所有未完成能力必须写进 known limitations。

## 7. 三天后交付物

- 可运行前端工作台；
- 可运行 FastAPI 后端；
- 筛查 API；
- 调查 API；
- 本地 watchlist / direct-hit 能力；
- Pattern Analysis；
- 风险解释报告；
- 中文操作手册；
- smoke test；
- 测试用例；
- 部署/运行文档；
- known limitations；
- `aml-architect` 签字的 release checklist。
