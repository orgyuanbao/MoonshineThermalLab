# Moonshine 的残差误差界研究记录

本目录保存本课题使用原版 [DeepMathLLM/Moonshine](https://github.com/DeepMathLLM/Moonshine/tree/bb0e4aa025fdcc5297fff1025ab4876f120ed615) 进行的新研究。Moonshine 通过项目的本机 Codex 适配器调用 `gpt-6-astra`。Python 执行、审核和归档由 Moonshine 自身的工具完成。

## 第一轮：从研究问题到小网格的精确检验

项目方给出 Robin 离散算子、逆非负假设、参数范围、现有残差最大值基线，并建议调查位置分块和正负分离。首轮提示没有给出候选界的公式或检查程序。[题面](research_prompt.md)

Moonshine 推导了基于最弱散热端点的单端分块界，写出并实际运行 `moonshine_bound.py`。程序在 1×1 至 4×4 网格上使用 Python 有理数，覆盖 81 组边界条件和每格 8 种命名的残差构造；不同构造在小网格上可以重合。2,592 组检查都满足误差覆盖和三个界的次序，1,053 组的单端分块界严格小于统一最大残差界。2×2 半幅异号的示例中，真实误差约为 0.45652，位置与正负结合后的上界为 2.85326，忽略符号的界为 5.25。4×4 的棋盘示例则显示，每块内部有相同的正负极值时，粗分块可能没有收益。[原生推导](workspace/residual_proof.md) · [原生检查器](workspace/experiments/moonshine_bound.py)

首轮的计算审核员手算确认小网格例，因给它的材料不足以复核 1,053 的计数，返回 `inconclusive`。Moonshine 补上程序与逐例定义等证据；第二次审核的上下文字数从 942 扩为 11,277，三项审核通过，随后记录 8 条归档。相同模型按不同审核职责作出的判断与另外运行的独立复算分别记账。

## 第二轮：用同一会话检验双端点区间

项目方在这一轮明确给出强、弱散热两个端点和正负残差块上下界的区间公式，要求尝试推翻它。Moonshine 用新的程序检查推导，考察严格改进与取等的情形，并找到了一个能推翻“直接把带符号残差乘最弱端点逆矩阵”做法的反例。[第二轮提示](followup_02.md) · [原生推导与反例](workspace/residual_interval_proof.md) · [原生检查器](workspace/experiments/moonshine_interval.py)

2×2 网格上，四边换热系数取 `(1/5,5,1/5,1/5)`，按行排列的残差为 `(46,-46,46,-46)/21`。错误做法算出的界为 1，真实最大误差为 `437/269 ≈ 1.62454`。实际执行的另外 1,968 组参数、分块和残差组合全部覆盖真实误差，328 组的双端界严格小于单端界。反例单列，不计入该 1,968 组。两份原生程序把四条边标为左、右、上、下；它们自行装配测试矩阵，没有借用历史热仿真参数流中的上下边标签。

第二轮提交了完整的计算检查说明，首次整体审核通过。两轮使用同一会话，分别获 15、10 个模型响应，各成功运行 1 次原生 Python 工具，分别留下 8、5 条归档。[第二轮审核记录](workspace/residual_interval_verification.md)

## 查阅与重跑

在本目录使用 Python 3.12 执行以下命令。

```shell
python -B replay.py
```

程序读取公开回执中列出的文件校验值，把各原生检查器复制到临时目录重跑，再逐字段核对实际打印的 JSON。两组分数算例使用 Python 标准库，复算无需模型登录。每个算例的覆盖证明依赖文中列出的离散模型与逆非负等假设。归档的有理数样例与原始浮点温度实验分别统计。

[两轮回执摘要与文件校验值](run_receipts.json)按时间保留工具名称、Python 返回码、模型响应状态、审核维度和归档结果。摘要中的原始事件摘要值可与本机保留的完整事件核对；公开材料按研究内容选取字段。第一轮及第二轮的成功 Python 标准输出分别保存在 [execution-01.stdout.txt](execution-01.stdout.txt) 和 [execution-02.stdout.txt](execution-02.stdout.txt)。

## 研究技能和成品制作

第一轮实际加载了 `query-memory`、`quality-assessor`、`direct-proving`、`verify-overall` 和 `proof-corrector`。第二轮实际加载了 `query-memory`、`lemma-prover`、`construct-counterexamples` 和 `verify-overall`。这些名字来自两轮成功的 `load_skill_definition` 回执。本项目沿用固定版本 Moonshine 自带的技能，没有新增或调用报告生成技能。两份英文推导 Markdown 是上游文件工具按模型指令写入的研究产物。中文 LaTeX 论文、PPT 和大网格独立评测由项目侧另外整理。
