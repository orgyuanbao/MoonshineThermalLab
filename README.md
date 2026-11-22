# Moonshine Thermal Lab

一张快速算出的温度图，误差最大的一格究竟会错多少？Moonshine Thermal Lab 提供一个用反例检验温度误差上界的数学研究智能体。研究者给定候选公式与检验条件，DeepSeek 4.1 Flash 根据实算结果决定下一步。项目实现模型接口、研究控制器与精确检验器，复用 Moonshine 的工具管理器。

[![自动检查](https://github.com/orgyuanbao/MoonshineThermalLab/actions/workflows/tests.yml/badge.svg?branch=main)](https://github.com/orgyuanbao/MoonshineThermalLab/actions/workflows/tests.yml)

[《人工智能与数学》课程论文 PDF](MoonshineThermalLab/course_paper/paper.pdf) · [课堂汇报 PPT](MoonshineThermalLab/classroom/Moonshine热仿真课堂汇报.pptx) · [逐字稿 PDF](MoonshineThermalLab/classroom/Moonshine课堂汇报_逐字稿.pdf) · [可编辑逐字稿 Word](MoonshineThermalLab/classroom/Moonshine课堂汇报_逐字稿.docx)

[自研智能体源码](MoonshineThermalLab/integration/bound_agent.py) · [两轮真实调用记录](MoonshineThermalLab/residual_study/agent_extension/live_trace.json) · [复算指南](START_HERE.md)

## 智能体是怎样开发的

项目先将四格导热问题写成可枚举的精确试验，再把它封装成工具 `check_residual_bound`。工具逐组比较真实误差和候选上界，返回首个反例或完成枚举的组数。我们用 Moonshine 的工具管理器注册和调用这个工具，并编写控制器保存每次调用的候选式、参数和结果。[数学检验工具](MoonshineThermalLab/integration/residual_tool.py) · [研究控制器](MoonshineThermalLab/integration/bound_agent.py)

模型接口通过阿里云百炼调用 DeepSeek 4.1 Flash，请求模型标识为 `deepseek-v4.1-flash`，公开回执简写为 `DeepSeek 4.1`。自研控制器校验模型提出的请求，Moonshine 工具管理器将请求分派给检验器。检验器把搜到的反例或穷举结果交回控制器，模型读到结果后再选择检验或结束。[模型适配器](MoonshineThermalLab/integration/bound_agent_model.py) · [离线复核这两次运算](MoonshineThermalLab/residual_study/agent_extension/verify_live_trace.py)

![研究者给定条件，DeepSeek 4.1 Flash 选择检验或结束，自研控制器经 Moonshine 调用精确检验工具，并把结果送回模型](MoonshineThermalLab/classroom/residual-bound-agent-flow.png)

## 运行残差上界研究智能体

进入 `MoonshineThermalLab` 子目录，首次使用先运行 `安装环境.cmd`。双击 `启动热仿真研究.cmd`，选 **8**，再回车，即可看见智能体依次检验原猜想、修正式和收紧后的倍数。终端逐轮显示精确值，并给出本次研究记录的位置。这一模式可以离线运行。[控制器](MoonshineThermalLab/integration/bound_agent.py) · [三轮实际记录](MoonshineThermalLab/residual_study/agent_extension/trace.json)

选 **8 → 2** 可让模型阅读每次反例并选择下一步。打开子目录里的 `.env`，填写 `LLM_BASE_URL`、`LLM_API_KEY` 和 `LLM_MODEL`。从 GitHub 克隆时可先把 `.env.example` 复制为 `.env`。接口采用支持工具调用的 Chat Completions 协议，模型选择检验，矩阵求解与分数比较在本机执行。[空白配置模板](MoonshineThermalLab/.env.example) · [模型接口和命令行示例](MoonshineThermalLab/README.md#运行自研残差上界研究智能体)

在线实验预先规定先查简化公式，遇到反例再查双端点式。第一轮，DeepSeek 请求检验 `weak_signed`。自研检验器在第 90 组算出真实误差 399/538，大于公式给出的 21/46，控制器将反例送回模型。第二轮，DeepSeek 依约改查 `block_two_endpoint`。Moonshine 分派给同一检验器，边界取值、分块和搜索范围保持一致。检验器查完有限域内 1,296 组，未见反例。DeepSeek 读到回执后结束。[两轮模型运行记录](MoonshineThermalLab/residual_study/agent_extension/live_trace.json) · [离线复核](MoonshineThermalLab/residual_study/agent_extension/verify_live_trace.py)

## 先试一个四格算例

同一块板、同一组散热条件，四个格子的残差都取 +1 时，最大温度误差等于 5.25；将符号按棋盘交错排列，误差降为 21/88，恰好小了 22 倍。两个例子的最大残差均为 1。用 Python 3.12 和标准库可以精确核对这两组数。

```powershell
git clone https://github.com/orgyuanbao/MoonshineThermalLab.git thermal-lab
cd .\thermal-lab\MoonshineThermalLab
python -B .\residual_study\exact_audit.py
```

成功时最后一行包含 `"error_ratio": "22"` 和 `"status": "passed"`。检查程序还会验证 17,496 组单元与分块的有理数区间，以及一个把带符号残差直接传入弱散热逆矩阵会低估误差的反例。[检验代码](MoonshineThermalLab/residual_study/exact_audit.py)

## 怎样用到实际预测

程序把残差按位置分成 4 × 4 块，读取每块的最小值和最大值，调用预计算的响应模板估计整张温度图的误差区间。若上界超过阈值，策略可以重做完整求解并用结果更新降阶模型。在 48 × 48 网格上，旧轨迹的第 11 个预测仅用位置得到的上界是 0.001022，加上正负后是 0.000926；阈值 0.001 刚好位于二者之间，该次实际误差约为 0.00000173。

![不同网格的实际回退次数和误差上界收紧幅度](MoonshineThermalLab/thermal/report/figures/residual_comparison.png)

三个网格各自使用相同的 256 个工况。固定旧预测做配对比较，原方法报警 47 次，分块符号界报警 29 次；独立部署并更新模型时，实际回退从 47 次降为 40 次，各方法的最终输出均达标。双端点界与单端符号界在这些实际预测上数值相同，增加端点模板后总耗时在本机三个网格上均未下降。[五种方法的实现](MoonshineThermalLab/residual_study/bounds.py) · [逐例数据与运行时间](MoonshineThermalLab/residual_study/results/)

## 复算全部数据，或让 Moonshine 做新实验

在上面进入的子目录，Windows 首次安装需要联网及 64 位 Python 3.12。安装后可离线完成以下数值复算。

```powershell
.\安装环境.cmd
.\.venv\Scripts\python.exe -B .\residual_study\run_experiment.py --check-against .\residual_study\results
.\.venv\Scripts\python.exe -B .\residual_study\fresh_stream.py
.\.venv\Scripts\python.exe -B .\residual_study\moonshine\replay.py
```

想让智能体继续研究，在已登录本机 Codex CLI 的环境中双击 `启动热仿真研究.cmd`，在主菜单选 **1**，再选研究阶段 **5**。可以补充自己的问题，例如「找一组同样大小、位置不同的残差，说明为什么某个上界会改变」。新一轮的工具回执和实验文件保存在本机。项目使用上游 Moonshine 的证明、反例搜索、审核和归档流程；本地实现题目入口、模型接入、会话恢复和证据保存。前期运行原版 Moonshine 时，经本机 Codex 适配器调用 `gpt-6-astra`，两轮分别进行了 2,592 和 1,968 组精确检查。11 月 21 日的课程论文和 PPT 由 Codex 依据归档材料整理。同一个 LaTeX 报告技能也可生成最终课程论文，把七轮先期记录、两轮残差研究、四格验证与三网格独立实验放入同一篇文章。[项目技能定义](MoonshineThermalLab/project_skills/latex-research-report/SKILL.md) · [自动报告与本轮证据](MoonshineThermalLab/report_example/)。[使用指南](MoonshineThermalLab/README.md) · [数学研究任务](MoonshineThermalLab/thermal/prompts/05_signed_residual.txt) · [上游源码](https://github.com/DeepMathLLM/Moonshine/tree/bb0e4aa025fdcc5297fff1025ab4876f120ed615)

## 论文与课堂演示

徐楷沅（2352163）的课程论文给出分块误差界的推导、两轮模型决策与精确回执，以及三个大网格的独立数值实验。主菜单选 **7** 可根据归档证据重新生成论文。[课程论文 PDF](MoonshineThermalLab/course_paper/paper.pdf) · [LaTeX 源码](MoonshineThermalLab/course_paper/paper.tex)

课堂演示共 18 张幻灯片，主讲 16 张，约 8 分钟。第 7、8 页展示三个自研模块，第 9、10 页依次展示反例和后续检验。第 16、17 页为隐藏的历史操作演示。现场放映时将 PPT、HTML 与四格实验报告 PDF 保存在同一个文件夹，演示按钮即可找到两个本地文件。[课堂汇报 PPT](MoonshineThermalLab/classroom/Moonshine热仿真课堂汇报.pptx) · [打印逐字稿 PDF](MoonshineThermalLab/classroom/Moonshine课堂汇报_逐字稿.pdf) · [可编辑逐字稿 Word](MoonshineThermalLab/classroom/Moonshine课堂汇报_逐字稿.docx) · [离线演示 HTML](MoonshineThermalLab/classroom/Moonshine现场演示.html) · [四格实验示例报告](MoonshineThermalLab/classroom/moonshine-report.pdf) · [早期备讲稿与研究总结](MoonshineThermalLab/classroom/备讲稿与研究总结.pdf)

论文采用的前期导热求解器、七轮研究记录和冻结输入均可查阅。[原导热实验](MoonshineThermalLab/thermal/home/projects/thermal-rom/workspace/results/04_final_v1/) · [七轮研究记录](MoonshineThermalLab/evidence/iterations.json)
