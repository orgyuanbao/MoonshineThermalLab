# MoonshineThermalLab 使用指南

MoonshineThermalLab 用 [Moonshine](https://github.com/DeepMathLLM/Moonshine/tree/bb0e4aa025fdcc5297fff1025ab4876f120ed615) 研究二维稳态导热。给定同一块板、两个固定热源和四条边的散热系数，程序可以求出完整温度场，也可以用少数基向量近似。自适应求解器在误差上界超过阈值时回退到完整求解，并用新解更新基底。[题面与边界条件](thermal/problem.md)

## 研究残差的位置与正负

当前研究从格子内的热量失衡推断温度场的最大误差。先运行 `python -B residual_study/exact_audit.py` 看四格反例，再按[数学实验指南](residual_study/README.md)复算真实预测或独立更新策略。需要继续做新研究时，主菜单选 **1**、研究阶段选 **5**。上游 Moonshine 本次的实际程序与回执见[原生研究记录](residual_study/moonshine/)。

## 运行前期导热基准算例

在 Windows 上安装 **Python 3.12（64 位）**，下载或克隆完整仓库。进入 `MoonshineThermalLab` 目录，双击 `安装环境.cmd`。首次安装需要联网获取固定版本的依赖；安装完成后可离线复算，无需登录模型账号。

在本目录打开 PowerShell，运行：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 .\reproduce_thermal.py
```

默认用已有的 256 组散热参数，重跑 24 × 24 网格的第 1 次实验。结束时终端会打印 `status`、`model_calls`、`runs` 和报告的完整路径。成功时前三项依次为 `passed`、`0`、`1`。打开报告可看到：

| 字段 | 怎么读 |
|---|---|
| `runs[0].checks` | 默认算例逐项核对 5,376 个数值和自适应决策字段。 |
| `runs[0].largest_error_statistic_difference` | 本次与归档误差指标的最大差值，允许绝对差不超过 `1e-9`。 |
| `original_workspace_unchanged` | 值为 `true` 表示复算前后的原始工作区文件校验值一致。 |

新报告和本次生成的温度误差、回退轨迹保存在 `thermal/reproductions/<运行编号>/`。要重跑三个网格、每个网格三次，在同一条命令后加 `--full`。耗时随机器和负载变化，复算只比较误差、执行计数与决策轨迹。[复算脚本](reproduce_thermal.py) · [原始逐次结果](thermal/home/projects/thermal-rom/workspace/results/04_final_v1/)

## 让 Moonshine 推进一轮研究

在同一安装环境中准备好已登录的 Codex CLI，双击 `启动热仿真研究.cmd`。菜单 **4** 会列出当前账号可用且支持本项目推理设置的模型；选定后从下一轮生效。以下是两个常用入口：

- **运行预设实验**：选 **1**，再选 **1**（建模与最小校验）。补充要求处直接回车。后续还有固定 POD 基线、失效分析、改进方法和残差误差界研究，每次选择只推进一轮。
- **提出具体问题**：选 **5**，例如输入「找出 24 × 24 网格上第一个触发回退的样本，报告四条边的系数、预测误差和误差上界，并注明结果文件。」另起一行输入 `END` 并回车提交。这个入口会把补充要求连同热仿真题面一起交给智能体。

研究启动后，终端显示会话编号、工具调用和执行回执。返回菜单后选 **2** 查看最近一轮摘要，选 **3** 打开本机产物目录。首次研究创建本地会话，之后重开菜单继续同一会话。想控制模型调用预算，可以在选好模型后使用命令行：

```powershell
.\.venv\Scripts\python.exe -B -X utf8 .\thermal_agent.py run --stage 1 --max-calls 8
```

### 一轮完成后，怎样拿到 LaTeX 报告？

主菜单选 **1 → 5** 研究残差上界，或在主菜单选 **5** 自拟热仿真题目。试题可以写「四格都有同样大的热量失衡，若把正负号排成交错，最大温度误差是多少？请给出推导并用精确分数复算」。自拟题目输完后另起一行提交 `END`。

一轮研究完成时，启动器会检查原生的程序执行、审核和归档记录。满足条件后，Moonshine 加载项目的已安装技能 `latex-research-report`。技能定义指定各节的次序和证据来源，项目适配器取出同一轮的送审推导、Python 输出和审核记录，排版器写入 LaTeX。排版无需额外的模型调用。[技能定义](project_skills/latex-research-report/SKILL.md) · [研究证据提取](integration/report_skill.py) · [LaTeX 排版](integration/report_latex.py)

报告在 `thermal/evidence/<轮次>/report/`。终端会打印保存位置。返回主菜单选 **6** 可打开最近一轮的报告。首次使用、尚无个人轮次时，这个按钮会注明并打开随仓四格示例。打开 `report.tex` 可以编辑推导，打开 `report.pdf` 可以直接阅读。`load_skill_definition.json` 记录 Moonshine 加载了哪项技能，`report_input.json` 保存进入报告的材料，`receipt.json` 给出触发方式、状态及文件校验值。[查看真实四格报告及复算材料](report_example/)

本项目固定的上游版本还提供最终审核后写入 Markdown 的流程。本技能处理每一轮已归档的局部数学结果，新增可编译的 LaTeX、PDF 和逐项出处。[上游实现](source/agent_runtime/research_workflow.py#L4318)

若本机装有 XeLaTeX 和中文排版支持，会同时生成 PDF。只有 TeX 时，先安装这两项，再在本目录运行以下命令。它从最近一轮证据重新排版。也可以在命令末尾加 `--turn 轮次编号` 指定一次研究。

```powershell
.\.venv\Scripts\python.exe -B -X utf8 .\thermal_agent.py report
```

若研究中断、最后一次审核未通过或缺少归档，先核对本轮记录、补齐研究；终端和生成回执会给出原因。归档齐全但缺少可引用推导时，程序也会明确提示。

### 卡住或报错时

| 看到的现象 | 下一步 |
|---|---|
| 输入要求后停在「续写」 | 输入单独一行 `END` 并回车，程序才会提交。 |
| 启动后持续显示 `[等待]` | 研究循环每 15 秒显示一次等待提示。若请求最终超时，选 **2** 找到最近一轮记录，在 `turn_summary.json` 查看错误，在 `moonshine_events.jsonl` 查看实际执行到哪一步。 |
| 列不出模型 | 在本机确认 Codex CLI 已登录、网络可用，再用菜单 **4** 重选。已安装依赖时仍可运行上面的离线算例。 |
| 退出后显示「部分进展」 | 查看本轮缺少执行、审核或归档中的哪项，用菜单 **5** 提交一项明确的补充要求。历史上曾因请求超时重新进入同一会话，下一轮先运行求解器校验，再继续冻结实验。[历史故障回执](evidence/failed-calls.json) |

## 从哪里改

| 位置 | 作用 |
|---|---|
| [thermal_agent.py](thermal_agent.py) · [thermal/prompts/](thermal/prompts/) | 组装研究题面、阶段任务与用户补充要求。 |
| [run_moonshine.py](run_moonshine.py) · [integration/](integration/) | 连接上游研究循环和本机模型，保存会话与逐轮工具回执。上游源码随项目提供，[版本清单](source_manifest.json)记录固定版本，[MIT 许可](source/LICENSE)随附。 |
| [experiments/](thermal/home/projects/thermal-rom/workspace/experiments/) | `thermal_solver.py` 实现完整导热模型，`pod_baseline.py` 提供固定基线，`stage4_kernels_v1.py` 实现自适应方法。 |
| [冻结配置](thermal/home/projects/thermal-rom/workspace/results/04_final_v1/frozen_configuration.json) · [结果汇总](thermal/home/projects/thermal-rom/workspace/results/04_final_v1/summary.json) | 查阅原始运行所用配置、网格尺寸及误差和耗时。 |

## 前期导热基准数据

原始基准用 24 组散热条件训练、12 组调参，在每种网格上测试相同的 256 组新条件。目标是使全场最大绝对误差不超过 `0.001`（无量纲温升）。

| 网格 | 固定八维模型超标 | 自适应模型超标 | 24 次查询耗时比 | 256 次查询耗时比 |
|---|---:|---:|---:|---:|
| 24 × 24 | 6 / 256 | 0 / 256 | 0.60 | 4.46 |
| 48 × 48 | 6 / 256 | 0 / 256 | 0.60 | 5.29 |
| 96 × 96 | 7 / 256 | 0 / 256 | 0.59 | 5.39 |

耗时比为快速完整求解总耗时除以自适应方法总耗时，取三次配对结果的中位数，包含训练、回退和更新。大于 1 表示自适应方法更快。三个网格分别发生 15、15、17 次回退，回看完整解时，这些样本的预测其实都已达标。改进误差上界和补测固定 24 维基线，是解释速度优势的两个后续方向。

历史研究使用 `gpt-6-astra`。Moonshine 生成并执行了求解器、POD 基线和自适应内核；解析误差界与最终评价驱动由外部提供。七轮研究留下 16 次 Python 执行尝试（15 次成功）、6 次整体审核（4 次通过）和 38 条原生归档。[逐轮记录](evidence/iterations.json) · [独立复核](evidence/independent-checks.json)

## 论文与演示

徐楷沅（2352163） · EDA 热仿真加速专题。[论文 PDF](thermal/report/Moonshine_Thermal_Report.pdf) · [LaTeX 源码](thermal/report/main.tex) · [汇报 PPT](classroom/Moonshine热仿真课堂汇报.pptx) · [备讲稿与操作截图](classroom/备讲稿与研究总结.pdf) · [离线交互演示](classroom/Moonshine现场演示.html)

在本机演示时，将 [classroom](classroom/) 里的 PPT、HTML 和 `moonshine-report.pdf` 下载到同一文件夹。第 3 页可以打开离线四格实验；第 6 页可跳到第 14 页，用本机 PDF 演示我们的报告技能。
