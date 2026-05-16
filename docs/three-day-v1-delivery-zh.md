# 三天可用版交付计划

计划周期：2026-05-15 至 2026-05-17。  
目标：交付一个可被真实风控人员使用的 V1，不按 beta/MVP 标准验收。

## 1. 可用版定义

三天内必须交付的“可用版”是：

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

这些能力可以预留接口，但不能假装已经生产可用。

## 2. 总体分工

### 程序员 A：后端与数据可靠性

负责范围：

- `services/api`
- `docs/database/schema.sql`
- `.env.example`
- 后端测试、接口验收脚本、运行文档

核心目标：

- 把现有内存版筛查/调查服务做成稳定可运行后端；
- 完成真实 Provider 的基础接入可靠性；
- 完成本地 watchlist 导入和 direct-hit 规则；
- 让 API 对前端、业务系统、风控人员都能解释清楚。

### 程序员 B：前端与风控工作台

负责范围：

- `apps/web`
- 前端视觉、交互、状态、错误提示
- 前端验收和可用性检查

核心目标：

- 把现在的 Wise 风格 UI 打磨成可用操作台；
- 让筛查、调查、图谱、证据、处置建议都清楚；
- 确保风控人员在无培训情况下能完成一次筛查和一次调查。

## 3. Codex 与 Mimo 使用边界

### Codex 负责

Codex 用于复杂、容易出事故、需要架构判断的任务：

- API 契约设计和 review；
- 风险评分、direct-hit、disposition 规则 review；
- Pattern Analysis 规则正确性 review；
- 数据库 schema 和迁移边界 review；
- 真实 provider 接入的失败模式设计；
- 安全、合规、证据链、误报风险检查；
- 最终代码审查和上线前验收清单。

Codex 不应该大量做重复 UI 样式、字段搬运、机械测试补齐。

### Mimo 负责

Mimo 用于脏活累活、机械执行、局部实现：

- 根据已定接口补表单字段、状态、列表、空状态；
- 写重复的 API 调用封装；
- 补前端样式细节；
- 补单元测试、fixture、接口 smoke test；
- 按 schema 写 repository 基础 CRUD；
- 修 TypeScript 类型、lint、构建错误；
- 更新文档里的命令和截图说明。

Mimo 每次任务必须给窄范围，不要让它自由决定产品逻辑。

## 4. 三天日程

### Day 1：2026-05-15，打通真实可用闭环

程序员 A：

- 检查并固定后端启动方式：`PYTHONPATH=.python-deps:services/api python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000`。
- 完成 `.env.example` 梳理：`DEMO_MODE`、`ETHERSCAN_API_KEY`、`GOPLUS_TOKEN`、`DEEPSEEK_API_KEY`、节点数量限制、CORS。
- 加强 Etherscan/GoPlus connector：
  - 明确超时、HTTP 错误、空数据、限流、provider 异常返回；
  - 所有异常返回结构化错误，不让 API 直接 500；
  - demo mode 和真实 mode 行为清楚区分。
- 完成本地 watchlist 导入接口：
  - 支持 CSV 或 JSON 导入；
  - 字段至少包括 `address,label,category,severity,notes`；
  - `category` 为 `ofac/pep/sanctions/circle_blacklist/tether_blacklist/stablecoin_blacklist` 时必须 direct-hit。
- 给 `/api/v1/screening/transactions` 补充请求/响应样例文档。

程序员 B：

- 前端按现有 Wise 风格做第一轮可用性整理：
  - 筛查区必须优先显示；
  - 风险等级和处置建议必须第一眼可见；
  - Pattern Signals 和 Source Hits 不要埋在页面底部；
  - 错误提示要能看懂，例如地址格式错、后端未启动、provider 失败。
- 补前端 API 错误解析：
  - FastAPI `detail` 错误要显示为人话；
  - 网络错误要提示检查后端服务；
  - loading/disabled 状态完整。
- 用 Mimo 做 UI 细节脏活：
  - 响应式布局；
  - 长地址换行；
  - badge、卡片、空状态；
  - 表单输入视觉一致。

Codex 检查点：

- review A 的 API 错误模型；
- review watchlist direct-hit 逻辑；
- review 前端是否误导用户，例如把 demo provider 当成真实情报。

Day 1 验收：

- 后端能启动；
- 前端能打开；
- 筛查接口能返回风险分和处置建议；
- watchlist 导入一个 OFAC demo 地址后，出金到该地址必须返回 `hold_for_manual_review`；
- `pytest` 通过；
- `npm run build` 通过。

### Day 2：2026-05-16，补齐调查与解释能力

程序员 A：

- 强化 Pattern Analysis：
  - Layering；
  - Aggregation；
  - Peel Chain；
  - 阈值拆分；
  - 高频小额；
  - Dusting；
  - 一次性地址；
  - 中心节点；
  - 风险传播。
- 每个 Pattern Signal 必须有：
  - `name`；
  - `severity`；
  - `score`；
  - `subject`；
  - `evidence`；
  - `confidence`；
  - `metadata`。
- 补报告生成：
  - 报告必须包含风险分解释、source hit、pattern signal、处置建议；
  - 没有证据时必须写“未发现证据”，不能编造；
  - ML/Raindrop 只能作为辅助信号。
- 增加测试 fixture：
  - OFAC direct-hit；
  - PEP direct-hit；
  - Dusting；
  - Aggregation；
  - Peel Chain；
  - 阈值拆分。

程序员 B：

- 调查工作台打磨：
  - 图谱区加载前、加载中、加载失败、加载成功状态完整；
  - 点击节点后展示标签、风险分、hop、source；
  - 风险摘要区展示 `Rule / Raindrop / Final / Disposition`；
  - Evidence、Pattern Signals、Source Hits 有排序和数量限制；
  - 报告区显示生成状态、失败状态、报告来源。
- 用 Mimo 做前端机械任务：
  - 把重复卡片抽小组件；
  - 补空状态；
  - 补字段格式化；
  - 补金额和分数展示；
  - 移动端排版修正。

Codex 检查点：

- review Pattern Analysis 是否过度误报；
- review 报告是否有幻觉风险；
- review 页面是否把 direct-hit 和普通 pattern risk 区分清楚。

Day 2 验收：

- 地址调查能完整展示图谱、风险摘要、证据、模式信号；
- 报告能解释风险原因；
- 至少 6 类风控场景有测试；
- 前端移动端不溢出、不重叠。

### Day 3：2026-05-17，稳定性、部署、交付验收

程序员 A：

- 做部署和运行固化：
  - 后端启动脚本；
  - 前端构建和 preview；
  - `.env` 配置说明；
  - provider key 缺失时的行为；
  - demo mode 与 production mode 切换说明。
- 补 smoke test 脚本：
  - `/health`；
  - `/api/v1/screening/transactions`；
  - `/api/v1/investigations`；
  - `/graph`；
  - `/risk`；
  - `/reports`。
- 检查 schema 与当前内存 store 差异，写清楚下一阶段 PostgreSQL 替换路径。
- 整理 known limitations，不允许用模糊语言。

程序员 B：

- 完成最终 UI 检查：
  - 1440px 桌面；
  - 1180px 窄屏；
  - 390px 手机；
  - 字体加载；
  - 长地址；
  - 大量证据；
  - 后端错误；
  - 报告内容很长。
- 准备操作手册：
  - 如何做一次出金筛查；
  - 如何导入 watchlist；
  - 如何做一次地址调查；
  - 如何解释 8/10 或 80/100 风险分；
  - 什么情况人工 HOLD。
- 用 Mimo 补页面小问题，但不改业务逻辑。

Codex 最终检查：

- 全量 review API 输出是否一致；
- 检查 direct-hit 是否优先于评分；
- 检查没有把 demo 数据说成真实情报；
- 检查测试和运行文档；
- 给出最终 release checklist。

Day 3 验收：

- 新机器按文档能跑起来；
- 真实 key 缺失时 demo mode 可跑；
- 真实 key 配置后 connector 不崩；
- watchlist direct-hit 可验证；
- 风控人员能完成筛查、调查、报告生成；
- 构建和测试全部通过。

## 5. 具体任务拆分

### 程序员 A 任务清单

1. 后端错误处理
   - 负责人：A
   - 工具：Mimo 实现，Codex review
   - 文件：`services/api/app/connectors`、`services/api/app/main.py`
   - 验收：provider 超时、限流、空结果不会导致不可读 500。

2. Watchlist 导入
   - 负责人：A
   - 工具：Codex 设计接口，Mimo 实现 CSV/JSON 解析
   - 文件：`services/api/app/domain/models.py`、`services/api/app/storage/memory.py`、`services/api/app/main.py`
   - 验收：导入 OFAC demo 地址后，筛查命中 `hold_for_manual_review`。

3. Direct-hit 策略完善
   - 负责人：A
   - 工具：Codex 实现或 review
   - 文件：`risk_intel.py`、`scoring.py`
   - 验收：PEP/OFAC/sanctions/stablecoin blacklist 不受普通评分阈值影响。

4. Pattern Analysis 测试补齐
   - 负责人：A
   - 工具：Mimo 写 fixture，Codex review 规则合理性
   - 文件：`patterns.py`、`test_domain.py`
   - 验收：至少 6 类 pattern 有确定性测试。

5. 报告解释增强
   - 负责人：A
   - 工具：Codex 设计提示词和边界，Mimo 补模板字段
   - 文件：`reporting.py`
   - 验收：报告能解释风险分、证据来源、处置建议，不编造事实。

6. Smoke test
   - 负责人：A
   - 工具：Mimo 实现
   - 文件：`infra/scripts`
   - 验收：一条命令跑完核心 API 检查。

### 程序员 B 任务清单

1. 筛查区完成生产可用交互
   - 负责人：B
   - 工具：Mimo 做 UI 细节，Codex review 风控表达
   - 文件：`apps/web/src/App.tsx`、`styles.css`
   - 验收：用户一眼看到风险分、等级、处置建议、证据摘要。

2. 调查区信息层级优化
   - 负责人：B
   - 工具：Mimo 实现
   - 文件：`App.tsx`
   - 验收：风险摘要、图谱、证据、模式信号、来源命中不混乱。

3. 错误与空状态
   - 负责人：B
   - 工具：Mimo 实现
   - 文件：`App.tsx`、`styles.css`
   - 验收：后端未启动、地址错误、报告失败都有明确提示。

4. 移动端与窄屏修正
   - 负责人：B
   - 工具：Mimo 实现
   - 文件：`styles.css`
   - 验收：390px、760px、1180px 不重叠、不溢出。

5. 操作手册
   - 负责人：B
   - 工具：Mimo 初稿，Codex review
   - 文件：`docs/operator-guide-zh.md`
   - 验收：非程序员能照着完成筛查和调查。

6. UI 最终一致性
   - 负责人：B
   - 工具：Codex review，Mimo 修细节
   - 文件：`apps/web`
   - 验收：符合 `DESIGN.md`，OPPO Sans 全局生效。

## 6. 每天必须跑的命令

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

筛查 smoke test：

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

## 7. 不可妥协验收标准

- Direct-hit 必须强制人工 HOLD；
- 每个风险结论必须有 evidence；
- demo 数据不能被描述成真实命中；
- Provider 错误不能导致页面崩溃；
- 前端长地址不能撑破布局；
- 报告不能编造法律结论；
- `pytest` 和 `npm run build` 必须通过；
- 文档必须能让新机器跑起来；
- 所有未完成能力必须写在 known limitations。

## 8. 3 天后交付物

- 可运行前端工作台；
- 可运行 FastAPI 后端；
- 筛查 API；
- 调查 API；
- 本地 watchlist/direct-hit 能力；
- Pattern Analysis；
- 风险解释报告；
- 中文操作手册；
- smoke test；
- 测试用例；
- 部署/运行文档；
- known limitations。

