# 从这里开始

《人工智能与数学》课程项目，徐楷沅（2352163）。给定一张近似温度图，如何根据每个格子的热量收支差判断它是否足够准确？论文给出误差上界的推导，课堂汇报用两轮真实模型调用演示自研智能体怎样检验这个上界。[课程论文 PDF](MoonshineThermalLab/course_paper/paper.pdf) · [可编辑汇报 PPT](MoonshineThermalLab/classroom/Moonshine热仿真课堂汇报.pptx)

| 我想做什么 | 从哪里开始 |
| --- | --- |
| 看智能体是怎么开发的 | [自研研究控制器](MoonshineThermalLab/integration/bound_agent.py)保存状态并调度试验，[反例工具](MoonshineThermalLab/integration/residual_tool.py)通过 Moonshine 工具接口执行精确枚举，[模型接口](MoonshineThermalLab/integration/bound_agent_model.py)把真实结果交回 DeepSeek 4.1。 |
| 跑一次本地研究 | 在项目子目录双击[安装环境.cmd](MoonshineThermalLab/安装环境.cmd)，完成后双击[启动热仿真研究.cmd](MoonshineThermalLab/启动热仿真研究.cmd)。选择 **8**，再按回车，查看三轮本地策略如何推进。 |
| 让模型选择下一步 | 按[模型配置说明](MoonshineThermalLab/README.md#运行自研残差上界研究智能体)在本机填写接口信息。启动后选 **8 → 2**，输入自己的四格残差研究问题。 |
| 核对课堂里的两轮实测 | 阅读[真实模型运行记录](MoonshineThermalLab/residual_study/agent_extension/live_trace.json)。在项目子目录运行下面的命令，可离线重算两轮数学结果。 |
| 重新生成课程论文 | 启动后选 **7**。报告技能依照[研究证据](MoonshineThermalLab/course_paper/)生成 LaTeX 和 PDF。 |
| 复算大网格实验 | 按[数学实验指南](MoonshineThermalLab/residual_study/README.md)比较相同预测上的报警次数，以及各策略分别部署后的回退次数。 |

```powershell
.\.venv\Scripts\python.exe -B -X utf8 residual_study/agent_extension/verify_live_trace.py
```
