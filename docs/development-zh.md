# Cregis ETH AML Tracing 开发文档

## 1. 项目定位

本项目是给香港公司 Cregis 定制的本地优先 Ethereum 反洗钱调查工具。第一版聚焦单笔调查：用户输入 Ethereum address 或 transaction hash，系统自动展开交易关系图，聚合风险情报，计算规则风险分和 Raindrop 风险分，并生成英文 AML 调查报告。

当前实现是 MVP 工程骨架，目标是让不同程序员或 AI model 可以并行开发：

- 后端提供稳定 API、demo 数据、外部 API 接入边界和评分接口。
- 前端提供可运行的调查工作台、图谱、证据和报告视图。
- Raindrop 模型先以稳定接口接入，真实神经网络迁移作为独立 ML 任务继续推进。

## 2. 目录结构

```text
apps/web/                  React + Vite 前端工作台
services/api/              FastAPI 后端服务
services/api/app/connectors 第三方 API 接入：Etherscan、GoPlus
services/api/app/domain     调查、图谱、风险情报、评分核心逻辑
services/api/app/ml         Raindrop AML 风险层接口
services/api/app/services   应用编排与报告生成
services/api/app/storage    存储适配层，当前为内存实现
services/ml/raindrop_aml    后续真实 Raindrop 模型迁移工作区
docs/                      架构、数据库、团队分工和开发文档
infra/scripts/             本地运行脚本
.github/workflows/         CI 配置
```

已删除并忽略的目录：

- `Raindrop/`：研究源码已阅读，后续只保留迁移说明，不把完整研究仓库作为业务源码提交。
- `TraeSkill/`、`awesome-skills/`、`industrial-dev-skillpack`：本地已安装技能包，不属于产品代码。

## 3. 本地运行

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

## 4. 环境变量

主要配置在 `.env.example`：

```text
DEMO_MODE=true
CHAIN_ID=1
ETHERSCAN_API_KEY=
GOPLUS_TOKEN=
DEEPSEEK_API_KEY=
DEEPSEEK_MODEL=deepseek-v4-pro
DEEPSEEK_BASE_URL=https://api.deepseek.com
CORS_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
MAX_STABLE_NODES=75
MAX_EXPERIMENTAL_NODES=160
VITE_API_BASE=http://localhost:8000
```

切换真实 API 时：

1. 设置 `DEMO_MODE=false`。
2. 填写 `ETHERSCAN_API_KEY`、`GOPLUS_TOKEN`、`DEEPSEEK_API_KEY`。
3. 重启后端服务。

`.env` 不得提交到 git。

## 5. 后端设计

核心 API：

- `POST /api/v1/investigations`：创建并运行调查。
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
- `RiskIntelAggregator`：统一 GoPlus、本地 watchlist 和后续公开标签。
- `RiskScoringEngine`：生成 `rule_score`、`raindrop_score`、`final_risk_score`。
- `DeepSeekReporter`：有 key 时调用 DeepSeek；无 key 时返回本地模板报告。

当前存储是 `InMemoryStore`，方便本地快速运行。PostgreSQL 目标 schema 已放在 `docs/database/schema.sql`，下一阶段可替换 storage adapter。

## 6. 前端设计

前端是实际工作台，不是 landing page。主要区域：

- 顶部输入区：address/hash、depth、mode、Run。
- 左侧风险区：最终风险分、规则分、Raindrop 分、主要证据。
- 中间图谱区：Cytoscape 交易关系图，节点颜色对应风险等级。
- 右侧详情区：节点详情、Raindrop 特征、报告生成和预览。

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

## 9. 团队协作规则

分工见 `docs/team-assignments.md`。协作原则：

- 每个程序员只改自己负责的模块。
- 跨模块改动必须先更新 API/schema 文档。
- 提交前必须跑对应测试。
- 不提交 `.env`、依赖目录、构建产物、技能包或研究源码目录。
- DeepSeek 报告必须保留原始风险分和证据来源，不允许让 AI 重写最终风险事实。

## 10. 下一阶段任务

优先级建议：

1. 把 `InMemoryStore` 替换为 PostgreSQL adapter。
2. 接入真实 Etherscan 和 GoPlus 错误处理、缓存和限流。
3. 增加公开风险名单和本地 watchlist 导入导出。
4. 把真实 Raindrop AML 模型迁移到 `services/ml/raindrop_aml`。
5. 增加 Playwright 前端端到端测试。
6. 增加 PDF/HTML 报告导出。
