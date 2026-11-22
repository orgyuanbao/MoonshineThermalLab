# 变散热边界下离散温度场的残差误差上界

《人工智能与数学》课程论文，徐楷沅（2352163）。给定一张近似温度图，哪些残差信息能帮助我们估计最大误差？论文给出分块误差界的证明，展示自研智能体怎样从一个精确反例决定下一轮检验，再用大网格检查实际回退次数。[阅读论文 PDF](paper.pdf) · [可独立编译的 LaTeX 源码](paper.tex)

## 论文采用哪些研究材料

| 材料 | 在论文中的用途 |
| --- | --- |
| [早期七轮的研究记录](../evidence/iterations.json)与[独立解析屏障推导](../thermal/independent_review/theory_oracle.md) | 说明建模、求解器校验和降阶策略怎样形成，保留各轮程序执行及审核状态。 |
| [两轮原生数学研究](../residual_study/moonshine/) | 对照单端符号界、双端点区间及反例，追踪首轮补交证据后的复审。 |
| [四格符号模式](../report_example/) | 从同号、条纹和棋盘三种精确解解释位置与符号的作用。 |
| [自研智能体的本地策略](../residual_study/agent_extension/trace.json) | 三轮精确实验检验原猜想、双端点修正式与统一缩放倍数。 |
| [阿里云百炼两轮真实调用](../residual_study/agent_extension/live_trace.json)与[复核程序](../residual_study/agent_extension/verify_live_trace.py) | 自研智能体保存任务、行动与反馈；DeepSeek 4.1 收到第一轮反例后，按题设条件提交第二次检验并总结有限域结论。 |
| [三网格逐例数据及留出实验](../residual_study/results/) | 区分固定预测上的报警与每种策略独立回退，比较预测精度、代价和适用范围。 |

从同一批旧预测出发，原判据与双端点界分别发出 47 次、29 次报警。每种策略独立更新降阶基时，实际回退分别为 47 次、40 次。三网格计时均未显示双端点策略的总耗时优势。

## 从归档重新生成

在项目子目录 `MoonshineThermalLab` 安装环境后，双击启动器，在主菜单选 **7**，或运行：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 thermal_agent.py paper
```

出稿程序通过 Moonshine 原生接口加载项目的已安装技能，按技能定义的章节读取冻结材料、校验来源和汇总逐例 CSV，按项目论文模板写成单文件 LaTeX。具备中文 TeX 环境时会自动编译 PDF。此前各轮的模型调用和审核都属于原研究；汇编这篇论文无需登录模型。[技能定义](../project_skills/latex-research-report/SKILL.md) · [本次加载记录](load_skill_definition.json) · [使用的证据](paper_input.json) · [生成回执](receipt.json)

仓库收录的是一次真实生成的成品。若要在自己的电脑上核对它，可在同一目录运行：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 integration/verify_course_paper.py
```

用 `thermal_agent.py paper --tex-only --output 新目录` 可生成一份新的 TeX；再运行 `integration/verify_course_paper.py --rebuild 新目录` 可比对两次输出的证据和 LaTeX 是否逐字一致。
