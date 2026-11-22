---
name: latex-research-report
description: 从审核记录和可复算的实验数据生成中文 LaTeX 报告，支持单轮自动报告和跨轮课程论文。
metadata:
  title: 研究证据转 LaTeX 报告
  category: installed
---

# 研究证据转 LaTeX 报告

## Summary

在项目适配器确认本轮已执行程序、通过局部审核并完成归档后运行。报告的结论限于该轮的审核对象。排版过程不需要新增模型请求。

收到综合课程论文请求时，从历史研究轮次与独立数值实验中取材。每类证据保留单独的来源标识及范围。一次综合排版登记为一次技能调用，研究轮次和模型调用数维持原计数。

## Execution Steps

1. 核对会话、轮次和原生结束摘要，查验最后一次审核、成功运行及归档记录。
2. 在同一次审核的蓝图写入回执中提取推导；若本轮没有写入该蓝图，则使用提交给该次审核的证明正文。
3. 逐项列出 Python 执行回执、工具错误及反例检验结果。对反例注明候选式、实查用例数和见证；对无反例结果注明实际枚举的范围。保留审核失败以及后续修改的顺序。
4. 依照以下 Evidence Layout 的顺序生成各节。冒号前为报告栏目，冒号后为本项目读取该证据的方式。每段材料附本轮原始文件或事件行号。
5. 将所有研究文字作为数据安全排版，保存输入、输出和原生技能加载回执；若编译器缺失，交付可编译的源文件并记录原因。

## Evidence Layout

```json
{
  "research_question": "turn_prompt",
  "proofs": "reviewed_blueprint_or_submitted_proof",
  "experiments": "research_tool_results",
  "reviews": "chronological_reviews_and_archive",
  "sources": "turn_file_digests"
}
```

## Course Paper Execution

综合课程论文的操作如下。

1. 核对历史导热基准、两轮误差界研究及四格模式研究的真实来源，记录原生执行、审核与归档。保留失败与后续修正的归属。
2. 对照冻结工况的逐行数据，分别汇总旧轨迹上的配对报警、各方法独立运行的回退与返回场误差。用第二条参数流检查适用范围。独立大网格实验单独署明来源。
3. 读取研究工具的原生调用记录，区分由模型发起的调用与离线复放，核对候选式、反例和枚举范围。按 Course Paper Layout 的次序撰写推导、研究过程、智能体改进、数值实验和局限。
4. 保存实用的完整论文源文件、结构化材料、技能加载记录和生成回执；安装了中文 XeLaTeX 环境时编译 PDF。证据核对失败时终止本次出稿。

## Course Paper Layout

```json
[
  "problem",
  "bounds",
  "four_cell",
  "research",
  "agent_extension",
  "experiments",
  "discussion",
  "sources"
]
```

## Tool Calls

- `load_skill_definition` 从已安装技能注册表加载本技能，并在 Moonshine 的技能审计日志登记这次调用。

## File References

- `input.txt` 保存本轮实际任务。
- `moonshine_events.jsonl` 保存逐次工具请求、结果和归档回执。
- `turn_summary.json` 保存本轮结束状态与会话身份。
- `integration.json` 保存项目、研究模式、模型和启动时间。

## Output Contract

报告目录包含 `report_input.json`、`load_skill_definition.json`、`report.tex` 与 `receipt.json`。成功编译时另附 `report.pdf`。生成回执列出技能、触发途径、输入与成品 SHA-256、编译状态和限定范围。证据不足时只给出待补原因。

综合课程论文保存在独立目录中，其中包含 `paper_input.json`、`load_skill_definition.json`、`paper.tex`、`receipt.json` 及成功编译的 `paper.pdf`。使用的数据集、各来源的指纹、排版机制、是否产生新的研究轮次与模型调用都应可核查。
