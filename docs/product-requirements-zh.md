# Cregis AML 产品需求文档

## 产品定位

Cregis AML 首先是面向加密资产交易合规场景的交易前风险筛查产品。在资金放行
或入账前，系统根据拟发起交易返回处置决策、风险分、风险等级、有来源支撑的
证据和建议动作。

第一阶段产品里程碑是 pre-transaction scanning MVP。深度事后调查、更大范围图谱
展开和交互式 Agent/Copilot 是辅助能力，不是本里程碑的主界面。

本文档描述目标产品方向，是后续产品校准与功能规划的依据。当前 MVP 实现
可能与本文档存在差距。

## 一、交易前筛查 MVP

### 1. 交易上下文

筛查对象是交易上下文，而不是单个地址。输入应包含：

- Chain ID。
- 方向：入金或出金。
- From address 与 to address。
- 资产类型：native 或 ERC-20。
- 适用时提供 token address。
- 资产 symbol。
- 金额。
- 可选 customer ID 与 transaction hash。

### 2. 业务决策输出

每次筛查必须返回：

- 最终风险分与风险等级。
- 处置：`allow`、`review` 或 `hold_for_manual_review`。
- Source hits 与 pattern signals。
- Evidence summary。
- Recommended actions。

### 3. 入金 / 出金决策逻辑

入金主要评估发送方 `from_address`，因为资金进入 Cregis 控制的托管地址。出金
主要评估接收方 `to_address`，因为资金可能被释放给外部交易对手。

主交易对手上的 direct-hit 证据优先于行为分数。非主交易侧的 direct-hit 仍需
作为证据展示，默认进入 review，除非政策明确阻断该地址。

### 4. 默认风险政策

默认 MVP 政策见
[`docs/pre-transaction-risk-policy.md`](pre-transaction-risk-policy.md)。摘要如下：

- `allow`：无 direct hit，无实质 provider 或 pattern 证据，且分数低于 `35`。
- `review`：分数 `35` 至低于 `85`、provider 不可用、PEP review 政策、中等
  provider 证据、行为模式或金额阈值证据。
- `hold_for_manual_review`：OFAC、制裁名单、Circle 黑名单、Tether 黑名单、
  稳定币黑名单、配置为 hold 的 PEP、高置信 provider illicit hit，或分数
  `85` 及以上。

### 5. 金额阈值

默认 review 阈值：

- ETH：`10 ETH` 进入 review，`50 ETH` 作为高金额阈值。
- USDT：`10,000 USDT` 进入 review，`100,000 USDT` 作为高金额阈值。
- USDC：`10,000 USDC` 进入 review，`100,000 USDC` 作为高金额阈值。
- 其他 ERC-20：有 token metadata 与价格时，以 `10,000 USD` 等值进入 review，
  `100,000 USD` 等值作为高金额阈值。

接近阈值的金额只能作为 review 支持证据，不得单独作为非法活动结论。

### 6. Demo 与合规边界

Demo 数据必须始终标注为 demonstration data，不能描述成真实情报。所有风险结论
必须引用 source hit、pattern signal 或 evidence row。产品可以建议 allow、
review、hold 或升级处理，但不得在没有来源证据时断言犯罪事实。

## 二、风控模式分析 (Pattern Analysis)

### 1. 洗钱模式识别

识别资金流是否符合特定的洗钱特征，包括层递（Layering）、聚合（先拆分再
集中）以及剥离链（Peel Chain）等模式。

### 2. 地址行为画像

分析账户生命周期特征、交易频率、金额特征及一次性地址的使用情况，包括：

- 新地址或长期沉睡地址的大额转账。
- 异常高频交易。
- 高频小额交易。
- 连续接近阈值的拆分交易。
- 一次性地址的使用情况。

### 3. 网络关系模式

通过地址聚类（Clustering）和中心度分析（Centrality Analysis）识别网络中
的核心节点及潜在的风险传播路径。

### 4. Dusting 攻击监控

监测针对最近交易地址的 Dusting 攻击行为。当用户尝试向相关风险地址出金时，
系统需自动触发高危提示。

### 5. 实时黑名单库

维护并实时同步国际反洗钱标准数据库，包括：

- OFAC。
- PEP。
- 受制裁名单。
- Circle 黑名单 API。
- Tether 黑名单 API。

系统需主动核查每一笔流入与流出交易。

## 三、风控智能助手 (Agent/Copilot)

### 1. 概念科普

为所有用户提供 Cregis AML 基础知识及风控核心概念的说明。

### 2. 引导与配置

协助新用户了解产品功能边界与应用场景，提供操作指导并辅助完成初始风控设置。

### 3. 结果解读与深挖

以直观语言解释风险筛查结果，解答关于风险来源、评分准则（例如：8/10 分的
评分依据）及等级机制的疑问，并支持结合模式分析进行深层调查。

### 4. 处置建议

在合理范围内提供人工审核、冻结资金并上报、处理优先级排序等决策参考。

### 5. 强效标签预警

对于涉及 PEP（政治敏感人物）或受制裁实体（人、公司、国家）的查询，无论
最终风险评分高低，助手必须直接标注风险标签并做出主动预警。

## 四、当前 MVP 对齐说明

当前 MVP 已部分覆盖本文档目标：

- 已具备 Layering、Aggregation、Peel Chain、Dusting-like 行为、阈值拆分、
  中心节点和风险传播等初步模式分析能力。
- 已具备本地 watchlist 和 OFAC、PEP、受制裁名单、Circle 黑名单、Tether
  黑名单、稳定币黑名单等 direct-hit 风险类别。
- 已能基于交易图谱、风险命中、模式信号和评分结果生成调查报告。

当前 MVP 尚未完全满足本文档目标：

- 尚未自动同步官方 OFAC、PEP、受制裁名单、Circle 或 Tether 黑名单数据源。
- 尚未形成真正的交互式风控 Agent/Copilot。
- 尚未完整支持 USDT、USDC 等 ERC-20 token transfer 的图谱追踪。
- 当前存储仍为内存存储，尚未具备持久化实时黑名单数据库。
- 当前 Raindrop 层是辅助性的确定性评分器，并非已训练的生产级 AML 模型。
