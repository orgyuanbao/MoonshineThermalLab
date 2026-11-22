---
name: latex-research-report
description: 研究轮次已保存后，把该轮经过审核的推导、Python 执行输出和审核记录整理为可追溯的中文 LaTeX 报告。
metadata:
  title: 研究证据转 LaTeX 报告
  category: installed
---

# 研究证据转 LaTeX 报告

## Summary

在项目适配器确认本轮已执行程序、通过局部审核并完成归档后运行。报告的结论限于该轮的审核对象。排版过程不需要新增模型请求。

## Execution Steps

1. 核对会话、轮次和原生结束摘要，查验最后一次审核、成功运行及归档记录。
2. 在同一次审核的蓝图写入回执中提取推导；若本轮没有写入该蓝图，则使用提交给该次审核的证明正文。
3. 逐项列出 Python 工具的实际退出状态和标准输出；标准错误单列。保留审核失败以及后续修改的顺序。
4. 依照以下 Evidence Layout 的顺序生成各节。冒号前为报告栏目，冒号后为本项目读取该证据的方式。每段材料附本轮原始文件或事件行号。
5. 将所有研究文字作为数据安全排版，保存输入、输出和原生技能加载回执；若编译器缺失，交付可编译的源文件并记录原因。

## Evidence Layout

```json
{
  "research_question": "turn_prompt",
  "proofs": "reviewed_blueprint_or_submitted_proof",
  "experiments": "python_tool_results",
  "reviews": "chronological_reviews_and_archive",
  "sources": "turn_file_digests"
}
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
