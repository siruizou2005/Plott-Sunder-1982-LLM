# Plott & Sunder (1982) — LLM 智能体复现

[English](README.md) · **中文**

用 LLM 智能体复现 Plott & Sunder,*"Efficiency of Experimental Security Markets with
Insider Information"*,JPE 90(4) 的全部**五个市场**。

每个市场里,9 或 12 个智能体在 11–14 个"市场年"中交易单期证书。每年开始时摇奖笼决定
本年支付哪种红利,部分人拿到线索卡。核心问题是:**价格和持仓会落在理性预期(RE)均衡上,
还是先验信息(PI)均衡上**——也就是不知情的人能不能从价格里读出状态。

两部分:

- **Python**(`ps1982/`)跑市场和模型调用,每次运行写一份只追加的 JSONL 事件流
- **Node.js**(`web/`)读这些日志,提供中/英双语的回放查看器和指标面板

支持三个模型端点:DeepSeek 官方 API、阿里云百炼(同权重、约半价)、Google Vertex AI
的 Gemini。切换厂商只需改 scenario 里的一行。

---

## 快速开始

```bash
# 依赖已经装好;若要重建:
python3 -m venv .venv && ./.venv/bin/pip install -e ".[dev]"
cd web && npm install && cd ..

# 1. 不花钱 —— 检查参数和提示词
./.venv/bin/python -m ps1982 validate -s scenarios/m3_paper.yaml

# 2. 不花钱 —— 372 项离线测试
./.venv/bin/pytest

# 3. 不花钱 —— 引擎正确性闸门(见下)
make gate

# 4. 真实 API,约 11 分钟,约 $0.07 —— 连通性与 JSON 稳定性
./.venv/bin/python -m ps1982 run -s scenarios/smoke.yaml

# 5. 正式实验
./.venv/bin/python -m ps1982 run -s scenarios/m3_paper.yaml

# 6. 查看器
cd web && npm start           # http://127.0.0.1:8100
```

`make setup / test / gate / smoke / run / metrics / web` 是同样命令的封装。

**凭据**放在 `.env`(已在 `.gitignore` 里):DeepSeek、百炼(`DASHSCOPE_*`)、
Vertex(`GOOGLE_CLOUD_PROJECT` + ADC)。

---

## 五个市场

它们是**五个不同的处理,不是五次重复**——人数、先验、状态数、信息精度、期数全都不同。

| 市场 | 期数 | 人数 | 状态 | 先验 | 信息设计 | 特殊之处 |
|---:|---:|---:|---|---|---|---|
| 1 | 11 | **9** | X/Y | 1/3 | 1-4 无 · 5-8 内幕 · 9-11 全知 | **不完美信息**:线索是十位 0/1 抽样,不是字母;每类只有 1 个内幕者 |
| 2 | 11 | 12 | X/Y | 1/3 | 1-4 无 · 5-6 全知 · 7-11 内幕 | 全知期在内幕期**之前**,与市场 3 相反 |
| 3 | 12 | 12 | X/Y | .4 | 1-2 无 · 3-10 内幕 · 11-12 全知 | 论文分析最充分的市场,本项目的起点 |
| 4 | 14 | 12 | X/Y | .4 | 1-4 无 · 5-13 内幕 · **14 无** | 唯一在**结尾**也有无信息期的市场 |
| 5 | 13 | 12 | **X/Y/Z** | .35/.25/.40 | 1-3 无 · 4-13 内幕 | **三状态** |

每个参数的出处见 `docs/markets-1-to-5.md`;`ps1982/markets.py` 是它的可执行形式,
`tests/test_markets.py` 把它逐格核回论文的 Table 1、Table 2、Table 3 和脚注 5。

**理论预测是推导的,不是抄的。**`Market.theory_price()` 从红利和先验算出 RE/PI,
结果在论文印出的市场 2/3/4/5 的每一格上都吻合。市场 1 论文明说省略了
("information given to insiders was probabilistic. Predictions are not given here"),
所以它的预测由我们推导,而其余四个市场的完全吻合就是相信它的依据。

### 两条臂

- **`paper`** —— 用 Table 1 记录的那条实现序列。种子只改变轮转顺序、抽签和席位→姓名映射,
  所以这条臂是**同一条序列的重复**
- **`random`** —— 按该市场**自己的先验**重抽每期状态,信息设计保持不变。种子推导出序列本身,
  所以这条臂检验的是**结论能否超出那一次实现**

市场 1 的线索样本会跟着状态一起重抽——样本是**依条件于实现状态**从对应的箱子里抽的,
状态变了却留着原样本,描述的是一个不可能发生的世界。

---

## 引擎正确性闸门

花钱调模型之前,先跑一场**脚本化**智能体的市场。每种应该产出它自己那个模型的结果;
如果没有,问题在引擎而不在智能体。

```bash
make gate
```

| 智能体 | Y 内幕期 | X 内幕期 | E%(内幕期) | 读法 |
|---|---|---|---|---|
| `re` | 收在 **175** = RE | 收在 **354–400** = RE | 95–100 | 价格与持仓到达 RE 均衡 |
| `pi` | 停在 **220** = PI | 367–400 | **65–69** | 从不从价格学习,证书落在错误的手里 |
| `zi` | 400 附近噪声 | 400 附近噪声 | 60–90 | 约 48% 的价格变动朝向 RE,即随机 |

重点不是 `re` 会收敛,而是 `pi` **不会**。引擎能同时表达两个模型,所以一次真实运行落在
其中一个上,才说明了智能体的某种性质。

> **一处已知限制**:脚本化 `re` 读不懂市场 1 的十位线索串(它检查 `card in states`,
> 样本永远不满足),会退回价格推断。LLM 智能体不受影响(机制写在提示词里),
> 但 `re` 基线在市场 1 上不是有效参照。

---

## 目录结构

```
ps1982/
  markets.py     五个市场的全部参数、线索模型、RE/PI 推导、重抽
  params.py      市场 3 的模块级常量,现在从 markets.py 派生
  config.py      pydantic scenario 配置 —— 每个处理变量都是一个开关
  book.py        挂单簿:校验、价格改进、交叉成交
  engine.py      Session → Period → Round → Turn;广播、撮合、结算
  events.py      JSONL 事件模型与 sink
  metrics.py     事后指标,从日志反读
  agents/        llm_agent.py · scripted.py(zi/pi/re 基线)
  prompts/       instructions.py(改编自 Instruction Set 2)· brief.py · schemas.py
  llm/           openai_compat.py(DeepSeek/百炼)· gemini.py(Vertex)· base.py
scenarios/       每个实验臂一个 YAML,共 30 个
runs/            见下
web/server/      Express + WebSocket;读 runs/,控制回放节奏,跟随实时运行
  timeline.js    回放"一步"的唯一定义:一步 = 一个智能体的一个**回合**
web/src/         React + ECharts + zustand;i18n.ts 存放全部中/英词条
docs/            markets-1-to-5.md · paper-verification.md · design-deltas.md
tests/           372 项离线测试,没有一项碰网络
archive/         四个被取代的旧目录,原样保留(见文末)
```

### runs/ 按用途分组

| 组 | 内容 |
|---|---|
| `m3/` | **主结果。**6 场完整的市场 3:5 场 DeepSeek(经百炼)+ 1 场 Gemini(与 `m3_paper_0` 同种子配对) |
| `m3_local/` | 更早的 2 场完整市场 3(`paper`、`random`),走 DeepSeek 官方 API |
| `baselines/` | 脚本化智能体与 smoke,零 API 开销 |
| `probes/` | 各厂商的一两期连通性验证,不是实验 |

查看器会递归扫描并按组分层显示。`runs/README.md` 里有一处陷阱的说明。

### 获取数据

运行日志是产出而非源码,而且很大——光是 8 场完整的市场 3 就有 473 MB——所以不在本仓库里。
两种获取方式:

- **重新跑。**`./run_batch.sh` 能复现整批;每次运行在种子上完全确定,连轮转顺序、抽签和
  席位→姓名映射都一样,所以重跑 `m3_paper_0` 面对的市场和报告里那次逐位相同。
  26 场实测约 $50,单场约 $2、约一小时。
- **来信索取。**上文报告的那些运行的日志可应要求提供 —— siruizou2005@gmail.com。

---

## 已有结果(市场 3,8 场完整实验)

**市场确实聚合了信息。**25 个可分离期观测(RE=175 / PI=220 / 中点 197.5):

| | 五场 DeepSeek 合并 |
|---|---:|
| 可分离期均价 | **173.1** |
| 朝 RE 的价格变动(全部) | 62% |
| 效率 E | 88–94% |

价格不只是"朝 RE 移动",而是**落在 RE 上**(差 1.9 francs)。

DeepSeek 与 Gemini 在所有主要指标上落在一起。

### 一个论文看不到的模式

标准分析只统计 RE≠PI 的"可分离期",于是**两个模型预测相同的那些期被整个排除**——
而那正是聚合完全失败的地方。

`metrics.price_discovery_by_informed_side()` 补上了这一块:

```
discovery = (实际均价 − 不知情者水平) / (RE − 不知情者水平)
```

| | 均值 | n(独立单位=场) |
|---|---:|---:|
| 知情者=**卖方** | **1.02** | 6 |
| 知情者=**买方** | **0.03** | 6 |

**知情者要卖时市场走完了全程,要买时几乎一步没走。**六场同向,符号检验 p=0.016,
场内置换检验 p<0.0001。

提出的解释:知情者持有的资产比别人以为的**便宜**时,卖出就是获利方式,而卖出把价格推向
RE——信息通过获利行为泄露。反过来资产更**贵**时,知情者靠悄悄买入获利,把价格抬到 RE
只会毁掉自己的利润,所以他既有动机也有能力把价格摁在不知情者的水平。

**这仍是假说。**目前只有市场 3 一种设计,而它的 X 态要走的距离(180 francs)是 Y 态
(45 francs)的四倍,所以差距里可能有一部分来自"路程"而非"意愿"。
**市场 2 和 5 的买卖方向与市场 3 相反**,是区分这两种解释的直接机会。

---

## 三条硬约束

写提示词时不可违反,`tests/test_prompts.py` 对全部 (市场, 席位) 组合逐一守卫:

1. **"probability" 这个词永不出现。**论文明确记载被试是用摇奖笼作为**机械装置**训练的,
   概率语言被排除在说明书之外。这条约束逼出了两件事:每个市场的先验必须能用**整数个球**
   表达(所以有 `Market.bingo_total`),市场 1 的不完美线索必须写成**两盒筹码**
   而不是似然函数。
2. **不透露**有几种投资者类型、别人的红利是多少、知情者是否固定、哪种状态更可能。
3. **共同知识按市场给。**论文说"除市场 1 外,各市场的参与者都能推断出红利逐期不变"——
   所以市场 1 **不给**这条。

理论值(`THEORY_*`)只用于事后分析和查看器,**永不进入提示词**。

---

## 一次运行的日志里有什么

一个 JSONL 文件,一行一个事件,`agent_visible` 标记它是否进入了智能体能看到的记录。
智能体可见的市场日志是**过滤出来的**,不是另存一份。

| 事件 | 内容 |
|---|---|
| `session_start` | 配置、种子、市场号、实现序列、线索卡、内幕者名单、**该市场的 RE/PI 理论表**(全部对智能体隐藏) |
| `brief` | 推送给智能体的简报原文,逐字节 |
| `model_turn` | 完整 prompt、完整 completion、思维链、token 用量、重试、延迟 |
| `action` / `broadcast` / `trade` / `violation` | 决策、表态、成交、被市场拒绝的尝试 |
| `reflection` | 期末笔记与成交笔记 |
| `period_end` / `session_end` | 结算与汇总 |

理论表写进日志,是为了让查看器和任何下游读者**从运行本身取值**,而不是各自维护一份——
查看器原来那份是市场 3 的硬编码,对其它市场会静默出错。

---

## 批次运行

```bash
./.venv/bin/python batch_plan.py --show    # 看计划,不执行
./run_batch.sh                             # 全部起
./run_batch.sh m3_paper_0 m3_gem_paper     # 只起指定的
./.venv/bin/python watch_batch.py --loop 60
./resume_batch.sh                          # 断点续跑
```

计划是 **26 场**:五个市场各 5 场 DeepSeek(2 论文序列 + 3 随机重抽)+ 市场 3 的 1 场
Gemini。按实测约 $50、5–6 小时。

**并发是结构性约束,不是统计的。**一个 session 单线程推进各阶段,所以任何时刻最多
`broadcast_workers` 个请求在飞——`场次 × W` 是数学上限。百炼端点容量 50–80,
Vertex 用动态共享配额(没有可调的上限,只能少要)。scenario 里的注释记录了实测依据。

---

## archive/

四个被取代的旧目录,原样保留:

| | 保留的原因 |
|---|---|
| `19-Plott-Sunder-1982-LLM.archived-*` | 最初的项目目录 |
| `…-bailian.archived-*` | 百炼端点验证 |
| `…-gemini.archived-*` | Gemini 验证,**以及已删除的 willingness 分档特性的唯一一份代码** |
| `ps1982-deploy.archived-*` | 批次运行时的部署目录 |

**这 1.1G 全是重复数据**——runs 已复制进 `runs/`,代码已被新版覆盖。删掉它项目从
1.8G 降到 700M,功能不受影响。删之前值得知道:`willingness` 特性只剩这一份。

---

## 引用

被复现的实验:

> Plott, C. R., & Sunder, S. (1982). Efficiency of Experimental Security Markets with
> Insider Information: An Application of Rational-Expectations Models.
> *Journal of Political Economy*, 90(4), 663–698.
