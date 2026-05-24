# Cregis ETH AML Tracing 开发文档

## 1. 项目定位

本项目是给香港公司 Cregis 定制的本地优先 Ethereum 风控与反洗钱工作台。第一版有两个入口：出金/入金前实时筛查 ETH、USDT、USDC 转账；以及对 Ethereum address 或 transaction hash 做深度调查，系统自动展开交易关系图，聚合风险情报，计算规则风险分、Pattern Analysis 信号和 Raindrop 风险分，并生成英文 AML 调查报告。

当前实现是 MVP 工程骨架，按角色划分 ownership：架构、风险评审、连接器、图谱模式、风险情报、Raindrop、报告、前端、QA/DevOps 和存储各有明确边界。

- 后端提供稳定 API、demo 数据、外部 API 接入边界、实时筛查接口、Pattern Analysis 和评分接口。
- 前端提供可运行的筛查/调查工作台、图谱、证据、模式信号、来源命中和报告视图。
- Raindrop 模型先以稳定接口接入，真实神经网络迁移作为独立 ML 任务继续推进。

角色分工见 [`docs/team-assignments.md`](team-assignments.md)，必读 skill 索引见 [`docs/agent-skills.md`](agent-skills.md)。

## 2. 目录结构

```text
apps/web/                  React + Vite 前端工作台（web-workbench-engineer）
services/api/              FastAPI 后端服务
services/api/app/connectors 第三方 API 接入：Etherscan、GoPlus（connector-engineer）
services/api/app/domain     调查、图谱、Pattern Analysis、风险情报、评分核心逻辑
                            （graph-pattern-engineer、risk-intel-engineer）
services/api/app/ml         Raindrop AML 风险层接口（raindrop-ml-engineer）
services/api/app/services   筛查、调查编排与报告生成（report-engineer）
services/api/app/storage    存储适配层，当前为内存实现（db-storage-engineer）
services/ml/raindrop_aml    后续真实 Raindrop 模型迁移工作区（raindrop-ml-engineer）
docs/                      架构、数据库、角色分工和开发文档
infra/scripts/             本地运行脚本（qa-devops-engineer）
.github/workflows/         CI 配置（qa-devops-engineer）
opencode.json              可选的 OpenCode 模型 / 推理强度配置
```

已删除并忽略的目录：

- `Raindrop/`：研究源码已阅读，后续只保留迁移说明，不把完整研究仓库作为业务源码提交。
- `TraeSkill/`、`awesome-skills/`、`industrial-dev-skillpack`：原始本地技能包已清理。

复活并保留的目录（2026-05-16 项目总监验收后新增）：

- `docs/agent-skills.md`：项目内 agent / 人类贡献者的 skill 索引，替代旧的根目录发现文件。
- `skills/`：三条项目专属可调用 skill，包括
  [`cregis-code-quality`](../skills/cregis-code-quality/SKILL.md)（项目化 Karpathy 守则与验收闸口）、
  [`cregis-pre-merge-review`](../skills/cregis-pre-merge-review/SKILL.md)（可执行的合并前评审流程与裁决模板）、
  [`cregis-evidence-integrity`](../skills/cregis-evidence-integrity/SKILL.md)（合规取向的 Karpathy 适配，仅作用于评分/模式/直接命中/报告内容）。

## 3. 本地运行

### 3.0 运行前提（2026-05-16 验收后新增）

- **Python 3.11 或更高**。代码使用 `from datetime import UTC`，Python 3.9/3.10 启动即失败。
- **Node 18 或更高**，由 Vite 5 决定。
- 安装 Python 依赖前请知道：`services/api/requirements.txt` 当前钉死了 PyPI 上**不存在**的 `python-dotenv==1.2.2`（验收发现 R1），原样 `pip install` 会失败。临时绕过办法：先把这一行改成 `python-dotenv==1.1.1` 或 `python-dotenv==1.2.1`。彻底修复属于 `qa-devops-engineer` 的本轮 blocker，详见
  [`docs/acceptance-review.md`](acceptance-review.md)。

推荐一键启动：

```bash
bash scripts/boot-demo.sh
```

该脚本自动复制环境变量、安装依赖、启动后端（端口 8000）和前端（端口 5173）。

手动启动：

复制环境变量模板：

```bash
cp .env.example .env
```

后端推荐运行方式：

```bash
python3 -m pip install --target .python-deps -r services/api/requirements.txt
PYTHONPATH=.python-deps:services/api python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

也可以使用脚本：

```bash
infra/scripts/run_api.sh
```

前端运行：

```bash
cd apps/web
npm install
npm run dev
```

访问地址：

- 前端：`http://localhost:5173`
- 后端健康检查：`http://localhost:8000/health`

默认 `DEMO_MODE=true`，没有真实 API key 也能生成演示调查图谱和风险报告。

## 4.1 Smoke 测试

运行 V1 端点 smoke 测试：

```bash
bash scripts/smoke.sh
```

覆盖：`/health`、筛查、调查 CRUD、图谱、风险、报告、watchlist 导入、直接命中 `hold_for_manual_review` 验证。

## 4.2 CI

GitHub Actions (`.github/workflows/ci.yml`) 在 push/PR 到 `main` 时自动运行：
- `PYTHONPATH=services/api pytest -q services/api/app/tests`
- `cd apps/web && npm run build`
- Smoke 测试

## 5. 环境变量

主要配置在 `.env.example`：

```text
DEMO_MODE=true
CHAIN_ID=1
ETHERSCAN_API_KEY=
ETHEREUM_RPC_URL=https://eth-mainnet.g.alchemy.com/public
GOPLUS_TOKEN=
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
MAX_STABLE_NODES=75
MAX_EXPERIMENTAL_NODES=160
WATCHLIST_DATA_PATH=.data/watchlist.json
VITE_API_BASE=http://localhost:8000
```

切换真实 API 时：

1. 设置 `DEMO_MODE=false`。
2. 填写 `ETHERSCAN_API_KEY`、`GOPLUS_TOKEN`、`DEEPSEEK_API_KEY`。
3. 如需稳定的 Circle/Tether 黑名单链上查询，把 `ETHEREUM_RPC_URL` 改成
   Alchemy 免费 tier 的私有 Ethereum mainnet RPC URL。
4. 重启后端服务。

`.env` 不得提交到 git。

## 5. 后端设计

核心 API：

- `POST /api/v1/investigations`：创建并运行调查。
- `POST /api/v1/screening/transactions`：对单笔入金/出金转账做实时筛查，返回风险分、处置建议、证据、模式信号和来源命中。
- `GET /api/v1/screening/events`：读取本地筛查事件。
- `GET /api/v1/investigations/{id}`：读取调查状态。
- `GET /api/v1/investigations/{id}/graph`：读取交易图谱。
- `GET /api/v1/investigations/{id}/risk`：读取规则分、Raindrop 分、最终风险分和证据。
- `POST /api/v1/investigations/{id}/reports`：生成英文调查报告。
- `GET /api/v1/watchlists`：读取本地 watchlist。
- `POST /api/v1/watchlists`：新增或更新 watchlist 地址。

关键模块：

- `EtherscanClient`：负责交易数据获取。demo mode 下生成确定性交易样本。
- `GoPlusClient`：负责地址风险情报。demo mode 下生成确定性风险标签。
- `GraphBuilder`：负责从目标地址或交易哈希展开 bounded graph。
- `PatternAnalyzer`：检测 Layering、Aggregation、Peel Chain、接近阈值拆分、高频小额、Dusting、中心节点、风险传播等确定性信号。
- `RiskIntelAggregator`：统一 GoPlus、本地 watchlist 和后续公开标签，并输出可审计 source hit。
- `RiskScoringEngine`：生成 `rule_score`、`raindrop_score`、`final_risk_score`、`disposition_hint` 和 `recommended_actions`。
- `ScreeningService`：编排出金/入金前筛查，直接命中 OFAC/PEP/稳定币黑名单类标签时返回人工 HOLD。
- `DeepSeekReporter`：有 key 时调用 DeepSeek；无 key 时返回本地模板报告。

当前存储是 `InMemoryStore`，方便本地快速运行。investigation 和 screening
event 仍在内存里；watchlist 会持久化到 `WATCHLIST_DATA_PATH`，默认是
`.data/watchlist.json`。PostgreSQL 目标 schema 已放在
`docs/database/schema.sql`，下一阶段可替换 storage adapter。

## 6. 前端设计

前端是实际工作台，不是 landing page。主要区域：

- 顶部筛查区：from/to address、asset、direction、amount、Screen。
- 调查输入区：address/hash、depth、mode、Run。
- 左侧风险区：最终风险分、规则分、Raindrop 分、主要证据。
- 中间图谱区：Cytoscape 交易关系图，节点颜色对应风险等级。
- 右侧详情区：节点详情、Pattern Signals、Source Hits、Raindrop 特征、报告生成和预览。

前端入口：

- `apps/web/src/App.tsx`
- `apps/web/src/styles.css`

构建命令：

```bash
cd apps/web
npm run build
```

## 7. Raindrop 迁移边界

Raindrop 原始模型适合用于 AML 风险判断层，因为它处理不规则多变量时间序列，并通过图消息传递学习观测通道之间的依赖。

当前实现保留了稳定接口：

```python
score, features = RaindropAmlScorer().predict(graph)
```

MVP 中 `RaindropAmlScorer` 是确定性特征评分器，真实模型迁移时必须保持这个接口不变。真实迁移任务包括：

- 从调查图谱构造不规则多变量时间序列 tensor。
- 把风险观测通道映射为 Raindrop 的 sensor/channel。
- 支持 CPU 推理和可选 GPU 训练。
- 记录模型版本、特征版本、数据版本和指标。
- 输出 AUPRC、AUROC、Precision@K、Recall@K。

注意：`raindrop_score` 只作为风险排序和分析辅助，不覆盖明确的规则证据。

## 8. 测试

后端测试：

```bash
PYTHONPATH=.python-deps:services/api python3 -m pytest services/api/app/tests
```

前端构建测试：

```bash
cd apps/web
npm run build
```

当前已验证：

- 后端 domain 测试通过。
- 前端 TypeScript 和 Vite 构建通过。
- 本地 API `/health` 正常。
- demo mode 下能生成调查图谱、风险结果和本地报告。

## 9. 角色协作规则

10 个 ownership 角色的分工见 [`docs/team-assignments.md`](team-assignments.md)。协作原则：

- 任何动 API/schema/`.env`/模块边界的改动，必须先由 `aml-architect` 更新契约，执行角色才能落地。
- 任何动 `scoring.py`、`patterns.py`、`risk_intel.py`、`reporting.py` 的改动，合并前必须拿到 `risk-logic-reviewer` 的 `approved` verdict。
- 执行角色只改自己 OWNED 的文件；跨界改动经 `aml-architect` 路由。
- 提交前必须跑对应测试：后端 `PYTHONPATH=services/api pytest -q`，前端 `cd apps/web && npm run build`。
- 不提交 `.env`、依赖目录、构建产物或研究源码目录。
- DeepSeek 报告必须保留原始风险分和证据来源，不允许让 AI 重写最终风险事实。
- demo 数据不得在任何文档/UI/报告中被描述成真实命中。

## 10. 下一阶段任务

优先级建议：

1. 把 `InMemoryStore` 替换为 PostgreSQL adapter，并持久化 screening events、source hits、pattern signals、network metrics。
2. 接入真实 Etherscan 和 GoPlus 错误处理、缓存和限流。
3. 增加 OFAC/PEP/制裁/稳定币黑名单数据源同步和本地 watchlist 导入导出。
4. 把真实 Raindrop AML 模型迁移到 `services/ml/raindrop_aml`。
5. 增加 Playwright 前端端到端测试。
6. 增加 PDF/HTML 报告导出。
