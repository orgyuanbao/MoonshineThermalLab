# 从残差估计整张温度图的误差

同一个网格上，逐格的热量失衡构成残差 `r = b − A T̂`。本目录判断近似场 `T̂` 与离散方程解相差多大。为了了解位置和符号分别有什么用，程序在相同输入上评估五种判据，也让每个判据独立处理同一条散热参数序列。

[数学推导与论文](../thermal/report/Moonshine_Thermal_Report.pdf) · [真实 Moonshine 研究](moonshine/) · [所有数值结果](results/)

## 先复算

从仓库的 `MoonshineThermalLab` 子目录运行。第一项仅需 Python 标准库；其他数值实验使用项目固定的科学计算环境，Windows 首次双击 `安装环境.cmd`。

```powershell
python -B residual_study/exact_audit.py
.\.venv\Scripts\python.exe -B residual_study/run_experiment.py --check-against residual_study/results
.\.venv\Scripts\python.exe -B residual_study/fresh_stream.py
.\.venv\Scripts\python.exe -B residual_study/moonshine/replay.py
```

全量复算使用三个网格、256 个原始工况、三个计时重复，输出新的 `thermal/reproductions/residual-…/` 目录。用 `--grids 24 --queries 32 --repeats 1` 可在同一命令上仅核对前 32 个工况。比对的是每次预测的阈值决定、回退、秩与数值误差；耗时会随机器变化。最后一条重跑 Moonshine 已写出的程序，想要产生新的研究调用可运行 `thermal_agent.py run --stage 5`，需已登录的 Codex CLI。

## 读代码与数据

| 文件 | 用途 |
| --- | --- |
| [bounds.py](bounds.py) | 从强、弱散热端点建立格林响应模板，提供原屏障、最优标量、分块幅度、分块正负和双端点五种上界。 |
| [exact_audit.py](exact_audit.py) | 独立以分数构造四格矩阵，穷举 18 组系数、81 个残差和三种嵌套划分；其中包括同号、棋盘和错误捷径的反例。 |
| [run_experiment.py](run_experiment.py) | 核验冻结输入，读取初始八维基并独立重训检查子空间，在同一预测和独立策略两种设置下比对。 |
| [paired_cases.csv](results/paired_cases.csv) | 1,536 行。每个网格分别记录固定八维和旧自适应轨迹回退前的 256 个预测；每行有相同预测的真实误差及五种上界。 |
| [closed_loop_cases.csv](results/closed_loop_cases.csv) | 3,840 行。每项策略从同一个初始基出发，独立决定回退并更新。重复计时不重复记为精度样本。 |
| [summary.json](results/summary.json) | 各网格预计算成本、证书排序、判据触发、闭环计时、输入文件指纹及合成残差探针。 |
| [fresh_stream.py](fresh_stream.py) · [fresh_stream.json](results/fresh_stream.json) | 在 48 × 48 网格上使用另一个种子的 128 个工况，各策略独立更新；记录每次回退的下标。 |
| [plot_results.py](plot_results.py) | 从两份逐例 CSV 生成论文中的成本与精度对照图。 |

四边参数顺序为**左、右、下、上**。逐例 CSV 的下标从零开始。48 × 48 网格中使“仅位置”与“再保留符号”的决定不同的查询为 `track=old_pre, index=10`。阈值为无量纲温升 `0.001`。独立实验用双精度，并为事后交叉比较定义数值容差；实际决策直接以阈值比较。

## 研究技能与课程材料怎样分工

本机适配器把模型回答交还 Moonshine，上游工具读取已有的证明、构造反例和审核技能。新加入项目的是一份数学题面、一个可选择的研究阶段，以及独立计算与复核程序。Moonshine 原生运行写出了数学草稿、Python 程序、输出和审核记录。11 月 21 日的课程论文和课堂幻灯由 Codex 在这两轮研究结束后整理。11 月 22 日，项目在后续研究轮次中加入了独立的 [LaTeX 报告技能](../project_skills/latex-research-report/SKILL.md)。可以对照查看[新一轮自动报告和证据](../report_example/)。[运行器的工具清单](../run_moonshine.py) · [论文 LaTeX 源码](../thermal/report/main.tex)

## 应该怎样解释结果

- **界本身。** 四格精确计算显示，同一最大残差可产生相差 22 倍的实际最大误差。论文证明每一层新界不劣于上一层，双端点包络还给出逐格上下限。只知道全局幅度时，最优常数由四边最弱散热给出；若只知道各块的幅度，则每块同号取到其最大值即可达到位置界。双端点在部分构造样例严格优于单端符号界，而在 1,536 条真实配对预测中两者数值相同。[四格精确核对](results/exact_audit.json)
- **是否需要重算。** 旧方法走过的预测都保持不动时，原有 47 次报警降为 29 次。各策略真正更新自己的基时，原方法实际回退 47 次，新方法 40 次。这两种比较不能互换。
- **哪些问题仍存在。** 对固定八维基，三个网格分别有 6、6、7 组实际超标；所有判据仍会对全部查询报警。双端点模板也带来预处理和在线读取成本，原始流的三组网格均未测得相对旧判据的总时间收益。

精确算术推导适用于本题正 Robin 边界的离散模型。普通浮点实现未使用区间算术；结果针对离散方程，连续场与真实器件的模型误差另需估计。旧研究的冻结求解器和数据见[原工作区](../thermal/home/projects/thermal-rom/workspace/results/04_final_v1/)。
