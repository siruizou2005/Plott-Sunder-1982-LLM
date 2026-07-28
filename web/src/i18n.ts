import { useStore } from './store'

export type Lang = 'en' | 'zh'

/**
 * Every key is listed explicitly so that a missing translation is a compile error rather
 * than an English string leaking into the Chinese UI.
 *
 * Scope note: this covers interface chrome only. Agent briefings, reflections and model
 * output are shown verbatim in the language they were generated in (English) — translating
 * them would misrepresent what the model actually saw and said.
 */
export interface Strings {
  /** Carries a `{n}` placeholder for the market number; see Header. */
  title: string
  /** Same placeholder, for a market that is NOT one of Plott & Sunder's — market 6, the
   *  equidistant control of Table 7. Titling it with theirs would misattribute it. */
  titleControl: string
  /** Used until a run's meta has arrived and the market number is known. */
  titleBare: string
  subtitle: string
  // header / transport
  pickRun: string
  noRuns: string
  live: string
  connected: string
  offline: string
  play: string
  pause: string
  stepBack: string
  stepFwd: string
  speed: string
  period: string
  round: string
  of: string
  loading: string
  // tabs
  tabMarket: string
  tabAgent: string
  tabDemand: string
  tabMetrics: string
  // book
  book: string
  standingBid: string
  standingAsk: string
  spread: string
  none: string
  undefinedSpread: string
  mustExceed: string
  mustUndercut: string
  // price chart
  priceChart: string
  tradePrice: string
  closePrice: string
  separatingMark: string
  rePrice: string
  piPrice: string
  noTrades: string
  /** `{s}` is the state letter; filled from the states the run actually uses. */
  statePays: string
  stateX: string
  stateY: string
  // agents
  agents: string
  seat: string
  type: string
  card: string
  blank: string
  certs: string
  cash: string
  profit: string
  cumulative: string
  insiderBadge: string
  hiddenNote: string
  // turn trail
  reservation: string
  basis: string
  noQuote: string
  quote: string
  acceptStanding: string
  bid: string
  ask: string
  outcome: string
  posted: string
  traded: string
  superseded: string
  crossedAuto: string
  broadcastTo: string
  accepted: string
  declined: string
  winner: string
  losers: string
  losersNote: string
  violation: string
  reflection: string
  waiting: string
  // basis values
  basisPrior: string
  basisClue: string
  basisPrice: string
  basisOthers: string
  basisSpread: string
  // violation reasons
  vBudget: string
  vNoInventory: string
  vNoImprovement: string
  vStaleQuote: string
  vMalformed: string
  vEmptyNote: string
  vIllegalAccept: string
  // demand
  demandTitle: string
  demandBlurb: string
  price: string
  willingCount: string
  willingBuyers: string
  willingSellers: string
  acceptRate: string
  quotesAt: string
  // metrics
  metricsTitle: string
  noMetrics: string
  meanPrice: string
  lastPrice: string
  firstPrice: string
  efficiency: string
  tradingEfficiency: string
  wrongHands: string
  insiderRatio: string
  towardRe: string
  posteriorConv: string
  basisDrift: string
  spreadNarrowing: string
  table8: string
  insiderMean: string
  uninformedMean: string
  separating: string
  actionNumber: string
  shareInsider: string
  cumulativeShare: string
  cost: string
  calls: string
  wallClock: string
  tokens: string
  infoNone: string
  infoInsider: string
  infoAll: string
  sequenceLabel: string
  activePassive: string
  violationsTitle: string
  // two-level transport
  turnLabel: string
  substep: string
  jumpPeriod: string
  keysHint: string
  stepTurnBack: string
  stepTurnFwd: string
  // step kinds
  kSessionOpen: string
  kPeriodOpen: string
  kRoundOpen: string
  kPeriodClose: string
  kPeriodReflect: string
  kSessionClose: string
  // now-bar / round strip
  nowActing: string
  nextUp: string
  audienceOnly: string
  roundStrip: string
  endOfRound: string
  noAcceptor: string
  // market panels
  lastProfit: string
  quoteAge: string
  theoryCheck: string
  reHolder: string
  piHolder: string
  actualHolder: string
  holdersMatch: string
  holdersDiffer: string
  clickToJump: string
  // agent trail sections
  secSaw: string
  secThought: string
  secDid: string
  secResponse: string
  secResult: string
  rawRecord: string
  fullBrief: string
  showReasons: string
  modelCalls: string
  purpose: string
  latency: string
  systemPrompt: string
  userPrompt: string
  completionLabel: string
  reasoningLabel: string
  loadingDetail: string
  noBrief: string
  noBroadcast: string
  noAction: string
  couldNotSettle: string
  couldNotSettleNote: string
  tradesThisYear: string
  lastTradeAt: string
  periodReflections: string
  yourRecord: string
}

const en: Strings = {
  title: 'Plott & Sunder 1982 — Market {n}',
  titleControl: 'Equidistant control — Market {n}',
  titleBare: 'Plott & Sunder 1982',
  subtitle: 'Experimental security market with insider information · LLM agents',
  pickRun: 'Select a run',
  noRuns: 'No runs found. Run: ps1982 run --scenario scenarios/…',
  live: 'LIVE',
  connected: 'connected',
  offline: 'offline',
  play: 'Play',
  pause: 'Pause',
  stepBack: 'Back',
  stepFwd: 'Step',
  speed: 'Speed',
  period: 'Year',
  round: 'Round',
  of: 'of',
  loading: 'Loading…',
  tabMarket: 'Market',
  tabAgent: 'Agent trail',
  tabDemand: 'Latent demand',
  tabMetrics: 'Metrics',
  book: 'Standing quotes',
  standingBid: 'Standing bid',
  standingAsk: 'Standing ask',
  spread: 'Spread',
  none: 'none',
  undefinedSpread: 'not defined',
  mustExceed: 'a new bid must exceed',
  mustUndercut: 'a new ask must undercut',
  priceChart: 'Trade prices',
  tradePrice: 'Trade',
  closePrice: 'Closing price',
  separatingMark: '◆ = separating period: RE and PI predict different prices. Elsewhere the two agree, so the period cannot tell them apart.',
  rePrice: 'RE prediction',
  piPrice: 'PI prediction',
  noTrades: 'No trades yet',
  statePays: '{s}-dividend paid',
  stateX: 'X-dividend paid',
  stateY: 'Y-dividend paid',
  agents: 'Investors',
  seat: 'Seat',
  type: 'Type',
  card: 'Clue card',
  blank: 'blank',
  certs: 'Certs',
  cash: 'Francs',
  profit: 'Profit',
  cumulative: 'Cumulative',
  insiderBadge: 'informed',
  hiddenNote: 'Type, clue cards and the realized dividend are visible here but never to the agents.',
  reservation: 'Reservation prices',
  basis: 'Stated basis',
  noQuote: 'passed',
  quote: 'announced a quote',
  acceptStanding: 'accepted a standing quote',
  bid: 'bid',
  ask: 'ask',
  outcome: 'Outcome',
  posted: 'no one accepted — now standing',
  traded: 'traded',
  superseded: 'replaced',
  crossedAuto: 'crossed — settled automatically',
  broadcastTo: 'pushed to',
  accepted: 'accept',
  declined: 'decline',
  winner: 'chosen',
  losers: 'not drawn',
  losersNote: 'The agents never learn that anyone else accepted. This is the latent demand a human experiment cannot record.',
  violation: 'Rejected',
  reflection: 'Note to self',
  waiting: 'Nothing to show at this step.',
  basisPrior: 'the bingo cage alone',
  basisClue: 'own clue card',
  basisPrice: 'observed prices',
  basisOthers: 'others’ behaviour',
  basisSpread: 'the spread',
  vBudget: 'not enough francs',
  vNoInventory: 'no certificate to sell',
  vNoImprovement: 'did not improve the standing quote',
  vStaleQuote: 'poster could no longer honour it',
  vMalformed: 'unusable reply',
  vEmptyNote: 'note came back empty (reasoning used the whole budget)',
  vIllegalAccept: 'cannot accept that quote',
  demandTitle: 'Latent supply and demand',
  demandBlurb: 'Every broadcast records how many investors WOULD have taken the quote, not just the one who won the random tie-break — in an oral auction the losers never speak. Accepting an ask means buying and accepting a bid means selling, so the two sides are kept apart: pooling them would add willing buyers to willing sellers.',
  price: 'Price',
  willingCount: 'Willing takers',
  willingBuyers: 'Would buy at this price',
  willingSellers: 'Would sell at this price',
  acceptRate: 'Acceptance rate',
  quotesAt: 'quotes at this price',
  metricsTitle: 'Post-hoc metrics',
  noMetrics: 'No metrics file. Run: ps1982 metrics --run <log>',
  meanPrice: 'Mean price',
  lastPrice: 'Closing price',
  firstPrice: 'Opening price',
  efficiency: 'Efficiency E',
  tradingEfficiency: 'Trading efficiency TE',
  wrongHands: 'Certificates in the wrong hands',
  insiderRatio: 'Informed profit ÷ uninformed profit',
  towardRe: 'Price changes toward RE',
  posteriorConv: 'Belief in the true state',
  basisDrift: 'Stated basis by year',
  spreadNarrowing: 'Spread',
  table8: 'Informed involvement by market action',
  insiderMean: 'informed',
  uninformedMean: 'uninformed',
  separating: 'separating years only',
  actionNumber: 'Market action #',
  shareInsider: 'share involving an informed investor',
  cumulativeShare: 'cumulative share',
  cost: 'Cost',
  calls: 'Model calls',
  wallClock: 'Wall clock',
  tokens: 'Tokens',
  infoNone: 'no information',
  infoInsider: '6 informed',
  infoAll: 'all informed',
  sequenceLabel: 'Sequence',
  activePassive: 'Liquidity provided vs consumed',
  violationsTitle: 'Rejected attempts',
  turnLabel: 'turn',
  substep: 'sub-step',
  jumpPeriod: 'Jump to year',
  keysHint: '→ sub-step · shift+→ whole turn · space play',
  stepTurnBack: 'Previous turn',
  stepTurnFwd: 'Next turn',
  kSessionOpen: 'Session opens',
  kPeriodOpen: 'Year opens',
  kRoundOpen: 'Round opens',
  kPeriodClose: 'Year settles',
  kPeriodReflect: 'Year-end notes',
  kSessionClose: 'Session ends',
  nowActing: 'now',
  nextUp: 'next',
  audienceOnly: 'audience only',
  roundStrip: 'Speaking order this round',
  endOfRound: 'last speaker of the round',
  noAcceptor: 'nobody accepted',
  lastProfit: 'Last year',
  quoteAge: 'standing for',
  theoryCheck: 'Theory check',
  reHolder: 'RE predicts',
  piHolder: 'PI predicts',
  actualHolder: 'actually holding',
  holdersMatch: 'matches RE',
  holdersDiffer: 'does not match RE',
  clickToJump: 'click to jump here',
  secSaw: 'What it was shown',
  secThought: 'What it believed',
  secDid: 'What it did',
  secResponse: 'How the market answered',
  secResult: 'Outcome and note to self',
  rawRecord: 'Raw record',
  fullBrief: 'Full briefing',
  showReasons: 'Reason given by each',
  modelCalls: 'model calls',
  purpose: 'purpose',
  latency: 'latency',
  systemPrompt: 'system',
  userPrompt: 'user',
  completionLabel: 'completion',
  reasoningLabel: 'chain of thought',
  loadingDetail: 'loading…',
  noBrief: 'Scripted agent — the engine builds no briefing for it.',
  noBroadcast: 'This action never went to broadcast.',
  noAction: 'This turn produced no market action.',
  couldNotSettle: 'could not settle',
  couldNotSettleNote: 'Said yes, but could no longer pay or deliver, so never entered the draw. The engine cannot currently produce this — the same test is applied before anyone is asked.',
  tradesThisYear: 'trades so far this year',
  lastTradeAt: 'last trade',
  periodReflections: 'Year-end notes from all twelve investors',
  yourRecord: 'Record so far',
}

const zh: Strings = {
  title: 'Plott & Sunder 1982 —— 市场 {n}',
  titleControl: '等距控制市场 —— 市场 {n}',
  titleBare: 'Plott & Sunder 1982',
  subtitle: '含内幕信息的实验性证券市场 · LLM agent 复现',
  pickRun: '选择一次运行',
  noRuns: '没有找到运行记录。请先执行：ps1982 run --scenario scenarios/…',
  live: '实时',
  connected: '已连接',
  offline: '未连接',
  play: '播放',
  pause: '暂停',
  stepBack: '后退',
  stepFwd: '单步',
  speed: '倍速',
  period: '期',
  round: '轮',
  of: '/',
  loading: '加载中…',
  tabMarket: '市场',
  tabAgent: 'Agent 轨迹',
  tabDemand: '潜在需求',
  tabMetrics: '指标',
  book: '当前挂单',
  standingBid: '当前买价',
  standingAsk: '当前卖价',
  spread: '价差',
  none: '无',
  undefinedSpread: '不适用',
  mustExceed: '新买价须高于',
  mustUndercut: '新卖价须低于',
  priceChart: '成交价',
  tradePrice: '成交',
  closePrice: '收盘价',
  separatingMark: '◆ = 可分离期：RE 与 PI 预测不同价格。其余各期两者一致，无从判别。',
  rePrice: 'RE 预测价',
  piPrice: 'PI 预测价',
  noTrades: '本期尚无成交',
  statePays: '本期付 {s} 红利',
  stateX: '本期付 X 红利',
  stateY: '本期付 Y 红利',
  agents: '投资者',
  seat: '席位',
  type: '类型',
  card: '线索卡',
  blank: '空白',
  certs: '持仓',
  cash: '现金',
  profit: '本期利润',
  cumulative: '累计',
  insiderBadge: '知情',
  hiddenNote: '类型、线索卡与真实红利在此可见，但 agent 全程看不到。',
  reservation: '保留价',
  basis: '自陈依据',
  noQuote: '未报价',
  quote: '发出报价',
  acceptStanding: '接受挂单',
  bid: '买',
  ask: '卖',
  outcome: '结果',
  posted: '无人接受，已挂出',
  traded: '成交',
  superseded: '已被取代',
  crossedAuto: '交叉，自动成交',
  broadcastTo: '推送给',
  accepted: '接受',
  declined: '拒绝',
  winner: '中选',
  losers: '未被抽中',
  losersNote: '落选者的意愿被从市场日志中抹去，agent 无从知晓。这正是真人实验拿不到的潜在需求数据。',
  violation: '被拒绝',
  reflection: '写给自己的笔记',
  waiting: '此步无内容可显示。',
  basisPrior: '仅凭摇奖笼机制',
  basisClue: '自己的线索卡',
  basisPrice: '已发生的成交价',
  basisOthers: '他人的行为',
  basisSpread: '买卖价差',
  vBudget: '现金不足',
  vNoInventory: '没有可卖的证书',
  vNoImprovement: '未改进同侧挂单',
  vStaleQuote: '挂单方已无法履约',
  vMalformed: '回复无法解析',
  vEmptyNote: '笔记返回为空（推理耗尽了输出预算）',
  vIllegalAccept: '不能接受该挂单',
  demandTitle: '潜在供给与需求',
  demandBlurb: '每次广播都记录了有多少人「愿意」接受该报价，而不只是随机中选的那一个 —— 口头拍卖里落选者根本不会出声。接受卖价意味着买入、接受买价意味着卖出，因此两侧必须分开统计：合并会把愿意买的人和愿意卖的人加在一起。',
  price: '价格',
  willingCount: '愿意成交人数',
  willingBuyers: '愿意在此价买入',
  willingSellers: '愿意在此价卖出',
  acceptRate: '接受率',
  quotesAt: '该价位的报价次数',
  metricsTitle: '事后指标',
  noMetrics: '缺少指标文件。请执行：ps1982 metrics --run <log>',
  meanPrice: '期均价',
  lastPrice: '收盘价',
  firstPrice: '首笔成交价',
  efficiency: '效率 E',
  tradingEfficiency: '交易效率 TE',
  wrongHands: '落入「错误之手」的证书',
  insiderRatio: '知情者利润 ÷ 未知情者利润',
  towardRe: '朝向 RE 的价格变动',
  posteriorConv: '对真实状态的信念',
  basisDrift: '自陈依据的逐期分布',
  spreadNarrowing: '价差',
  table8: '各次市场行动涉及知情者的比例',
  insiderMean: '知情者',
  uninformedMean: '未知情者',
  separating: '仅可分离的期',
  actionNumber: '第几次市场行动',
  shareInsider: '涉及知情者的比例',
  cumulativeShare: '累积比例',
  cost: '成本',
  calls: '模型调用',
  wallClock: '运行时长',
  tokens: 'Token',
  infoNone: '无人知情',
  infoInsider: '6 人知情',
  infoAll: '全体知情',
  sequenceLabel: '序列',
  activePassive: '提供流动性 vs 消耗流动性',
  violationsTitle: '被拒绝的尝试',
  turnLabel: '回合',
  substep: '子步',
  jumpPeriod: '跳到第几期',
  keysHint: '→ 走子步 · shift+→ 走整回合 · 空格播放',
  stepTurnBack: '上一回合',
  stepTurnFwd: '下一回合',
  kSessionOpen: '实验开始',
  kPeriodOpen: '开期',
  kRoundOpen: '开轮',
  kPeriodClose: '期末结算',
  kPeriodReflect: '期末反思',
  kSessionClose: '实验结束',
  nowActing: '现在',
  nextUp: '下一个',
  audienceOnly: '观众可见',
  roundStrip: '本轮发言顺序',
  endOfRound: '本轮最后一位',
  noAcceptor: '无人接受',
  lastProfit: '上期利润',
  quoteAge: '已挂',
  theoryCheck: '理论对照',
  reHolder: 'RE 预测持有者',
  piHolder: 'PI 预测持有者',
  actualHolder: '实际持有',
  holdersMatch: '与 RE 一致',
  holdersDiffer: '与 RE 不符',
  clickToJump: '点击跳到这里',
  secSaw: '它看到了什么',
  secThought: '它怎么想',
  secDid: '它做了什么',
  secResponse: '市场如何回应',
  secResult: '结果与反思',
  rawRecord: '原始记录',
  fullBrief: '完整简报',
  showReasons: '逐条理由',
  modelCalls: '次模型调用',
  purpose: '用途',
  latency: '延迟',
  systemPrompt: 'system',
  userPrompt: 'user',
  completionLabel: '模型输出',
  reasoningLabel: '思维链',
  loadingDetail: '加载中…',
  noBrief: '脚本化 agent，引擎不为它生成简报。',
  noBroadcast: '该行动未进入广播。',
  noAction: '本回合没有产生市场行动。',
  couldNotSettle: '接受但无力成交',
  couldNotSettleNote: '表示接受，但已付不起或交不出，因此根本没进入抽签。当前引擎产生不了这种情况——提问前已用同一判据筛过一遍。',
  tradesThisYear: '本期累计成交',
  lastTradeAt: '最近成交',
  periodReflections: '十二位投资者的期末反思',
  yourRecord: '历史成绩',
}

const STRINGS: Record<Lang, Strings> = { en, zh }

export function useT(): Strings {
  const lang = useStore((s) => s.lang)
  return STRINGS[lang]
}

export function basisLabel(t: Strings, b?: string | null): string {
  switch (b) {
    case 'prior': return t.basisPrior
    case 'clue': return t.basisClue
    case 'price': return t.basisPrice
    case 'others_behavior': return t.basisOthers
    case 'spread': return t.basisSpread
    default: return b ?? '—'
  }
}

export function reasonLabel(t: Strings, r?: string | null): string {
  switch (r) {
    case 'budget': return t.vBudget
    case 'no_inventory': return t.vNoInventory
    case 'no_improvement': return t.vNoImprovement
    case 'stale_quote': return t.vStaleQuote
    case 'malformed': return t.vMalformed
    case 'empty_note': return t.vEmptyNote
    case 'illegal_accept': return t.vIllegalAccept
    default: return r ?? '—'
  }
}

export function stepKindLabel(t: Strings, kind?: string | null): string {
  switch (kind) {
    case 'session_open': return t.kSessionOpen
    case 'period_open': return t.kPeriodOpen
    case 'round_open': return t.kRoundOpen
    case 'period_close': return t.kPeriodClose
    case 'period_reflect': return t.kPeriodReflect
    case 'session_close': return t.kSessionClose
    default: return kind ?? '—'
  }
}

export function infoLabel(t: Strings, info?: string | null): string {
  switch (info) {
    case 'none': return t.infoNone
    case 'insider': return t.infoInsider
    case 'all': return t.infoAll
    default: return info ?? '—'
  }
}
