# 最终评价局部复审补记

项目：thermal-rom。此次仅补齐热源假设使用链并复审既有冻结有限实验，不修改算法、源码、参数、阈值、种子或测试结果，不重跑九次数值评价。

上轮审核记录rec-5c435e701cd3956f整体未通过：假设维度inconclusive，原因是提交材料未展开两个矩形如何进入载荷b；计算和逻辑维度通过。原失败保留，不追溯改写，也不解释为已发现数值算法错误。原提交保存在workspace/prior_final_review_submission.json。

本轮已读取原求解器、内核、评测驱动及协调者提供的补证脚本。令ell_i(a,b)=max(0,min((i+1)/n,b)-max(i/n,a))，则b[j*n+i]=ell_i(.2,.4)*ell_j(.2,.4)+2*ell_i(.6,.8)*ell_j(.6,.8)。source_integrals按两个矩形累加strength*outer(overlap,overlap)并ravel，理论总积分为0.12。assemble在ambient=0时直接使用该积分载荷；Geometry.b调用同一函数，快速FOM使用g.b，原POD投影assemble返回的b，快速POD使用V.T@g.b，自适应残差使用g.b-g.action(h,pre)，回退及增广重投影继续使用同一载荷。内部面系数为1，Robin系数为delta/(delta/2+1/h)，四边顺序left/right/bottom/top，角单元逐面累加，所有方程保持单元积分尺度。

本轮原生run_python_script实际执行workspace/experiments/final_heat_source_review.py，timeout_seconds=120，returncode=0，stderr为空。脚本由协调者提供，执行由Moonshine完成，不能互换来源。报告为workspace/review/final_heat_source_20261025T085903960554Z.json。n=24、48、96的显式交叠积分与源函数最大差全部为0，Geometry.b逐项相同；总量分别0.12000000000000005、0.12000000000000005、0.12000000000000008，满足绝对容差1e-14。冻结配置、当前源码、参数、训练来源及汇总引用结果的既定哈希检查通过，九个既有有效重复得到核对。本轮新增FOM=0、ROM=0，未生成测试。该检查属于公式与实现一致性及完整性检查，不是独立求解、全部统计重算或区间认证。

2026-10-25T09:05:44Z，verify_overall(project_slug=thermal-rom,scope=intermediate,review_count=1)实际返回passed=true、overall_verdict=correct；assumption_correct、calculation_correct、logic_correct均通过，各维度error_count=0，repair_targets为空。审核补齐热源使用链，支持提交的冻结有限实验记录、算法与计算一致性；审核模型没有独立重算全部浮点数组或硬件计时。

既有实证结论未改变：按n=24、48、96排序，快速FOM部署总成本除以自适应部署总成本的逐重复中位数，前24查询为0.6025988、0.5997925、0.5883201，全256查询为4.455223、5.294642、5.392289。短批量自适应成本较高，较长批量在本记录中较低。全流固定POD场误差超1e-3的案例数为6、6、7，自适应均0；每重复触发及增广15、15、17次，最终秩23、23、25，全部触发符合基于当前基回退前场误差的预定误触发定义。回退答案来自实际付费FOM，不能称免费降阶精度。历史总求解计数FOM=4965、ROM=6912，不计作本轮新增执行。原结果仍位于workspace/results/04_final_v1/summary.json及各网格重复目录。

限制：同一256点流的三次计时重复不是768个独立精度样本；普通双精度离散比较不保证连续PDE精度、全参数表现、区间认证或工业指标。部署成本包含必要训练与服务，排除历史研发调参、启动导入、日志保存及事后评价；固定方法顺序和硬件缓存会影响计时。误触发不能证明增广对未来无益，缺少无增广回退消融，不能分离两者的因果收益。外部独立复算仅是用户提供的信息，不计作本轮原生动作。

状态：补证执行与局部复审已完成；写本补记时尚未获得本轮原生归档成功回执，不能宣布局部闭环已完成。归档由原版流程处理，不手动改写memory或其他系统管理文件。
