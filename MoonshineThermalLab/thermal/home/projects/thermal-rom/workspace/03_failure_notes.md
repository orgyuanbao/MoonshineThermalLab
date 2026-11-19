# thermal-rom 开发失效分析
本文件由本轮原生实验生成；局部审核pending。读取基线JSON及NPZ，固定先前所选秩，仅使用12个调参点和16个边界角点。调参FOM与ROM复用，新增16次FOM与16次ROM；旧计算成本仍在02_baseline.json中，不能称作本轮再次执行。未生成最终测试，未更新基。
理论来源：屏障构造、经典比较原理方向及文献书目信息由协调者与外部复核提供，不是Moonshine自主发现。此处给出原生推导和实际Fraction小规模检查；外部已有检查不计入本轮次数。未联网独立查阅所给论文，不声称新定理。
For integer n>=1, Delta=1/n, cell centers x_i=(i+1/2)Delta and y_j=(j+1/2)Delta, let A be the integrated FV matrix with unit interior edge conductances and Robin diagonal face coefficients g_s=Delta/(Delta/2+1/h_s), each h_s in [0.2,5]. Set F=5+x(1-x)+y(1-y), z=F/(4Delta^2). The complete four-neighbor polynomial stencil gives 4Delta^2. At a missing exterior neighbor, F_P-F_ghost=Delta, including n=1. On any boundary center the two quadratic terms have sum at least Delta-Delta^2/2, hence F_P>=5+Delta/2>=1/h_s+Delta/2. Thus g_s F_P>=Delta. Each missing neighbor is compensated independently, so Az>=1. In particular n=1 has F=11/2, z=11/8, g_s>=2/11, and Az>=4*(2/11)*(11/8)=1. The energy identity gives SPD. For any nonnegative RHS, a negative minimum of the solution contradicts its boundary equation or propagates along connected interior edges to a boundary contradiction. Therefore A inverse is entrywise nonnegative. For any real approximate vector u and exact discrete solution T=A inverse b, r=b-Au, we have |T-u|<=A inverse |r|<=||r||inf A inverse 1<=||r||inf z, since A inverse(Az-1)>=0. The maximum functional is 1-Lipschitz in the infinity norm, proving hotspot error<=field error<=eta. For n=24 the nearest centers to one half are 23/48 and 25/48, so max z=144*(5+2*575/2304)=6335/8=791.875. For a floating FOM reference with residual r_F, exact arithmetic additionally gives ||u-T_F||inf<=(||r||inf+||r_F||inf)*max z; rounded program evaluations are only consistency checks, not interval-certified bounds.
For every epsilon>0, diag(epsilon,1) is SPD. With b=(epsilon,1/2), the exact solution is (1,1/2); approximation (0,1/2) has field infinity error 1 and maximum-value error 1/2. Its raw infinity residual is epsilon and relative Euclidean residual is epsilon/sqrt(epsilon^2+1/4), both tending to zero. This is an arbitrary algebraic family, not a matrix derived from the thermal PDE.
原生Fraction检查覆盖n=1,2,3,4及各16个角点；它精确核对有限有理数算例，不替代上面的任意网格证明。n=24实际算子Az检查及eta计算使用双精度，未包含区间舍入误差认证。eta无需额外FOM预解；程序为验证误差额外做的16次FOM及全部重组装、检查、向量和范数成本均单列。
误差定义及零分母约定沿用基线：热点为两个离散最大值差的绝对值，场为逐点误差绝对值最大值，相对L2除以FOM欧氏范数；相对残差除以b的欧氏范数。比值分母为零时，零分子记0，否则null。效应比eta/场误差仅描述当前开发样本保守程度。
若出现tau以上误差，只能称当前开发样本失效；若未出现则明确未找到。角点不参与改选秩。阶段1初审inconclusive和补充审核通过均保留；原求解器未改。没有预设失败或加速，硬件计时只是单次观测。下一步提交本轮局部审核，之后才另轮设计并冻结自适应方案及最终未见测试协议。
{
  "summary": {
    "selected_rank": 8,
    "diagnostic_rank": 8,
    "tau": 0.001,
    "zmax": 791.8750000000001,
    "development_points": 28,
    "field_failures": 2,
    "tuning_field_failures": 0,
    "corner_field_failures": 2,
    "eta_trigger_count": 28,
    "eta_trigger_without_observed_failure": 26,
    "worst_field": {
      "dataset": "corner_development",
      "index": 0,
      "h": [
        0.2,
        0.2,
        0.2,
        0.2
      ],
      "selected_rank": 8,
      "diagnostic_rank": 8,
      "hotspot_error": 0.00040335962920895474,
      "field_linf_error": 0.003979762955355237,
      "relative_l2_error": 0.003972587650486338,
      "residual_linf": 0.0017901246284979244,
      "residual_l2": 0.0035011062067545305,
      "relative_residual_l2": 0.20496990042980678,
      "eta_float": 1.4175549401917942,
      "eta_over_observed_field_error": 356.1907973147768,
      "fom_residual_eta_float": 3.516631430500184e-13,
      "fom_relative_residual": 1.184130454210336e-13,
      "min_Az_float": 0.9999999999995453,
      "field_target_exceeded": true,
      "eta_trigger_candidate": true,
      "timing": {
        "fom": {
          "assembly_seconds": 0.0009913999820128083,
          "linear_solve_seconds": 0.0008924000430852175,
          "assembly_and_solve_seconds": 0.0018838000250980258,
          "full_solve_count": 1
        },
        "rom": {
          "assembly_seconds": 0.001122299931012094,
          "projection_seconds": 5.550007335841656e-05,
          "reduced_solve_seconds": 5.0299917347729206e-05,
          "reconstruction_seconds": 3.8000289350748062e-06,
          "residual_evaluation_seconds": 2.220005262643099e-05,
          "online_total_seconds": 0.0012541000032797456,
          "verification_seconds": 2.059992402791977e-05
        },
        "diagnostic_reassembly_seconds": 0.0010469999397173524,
        "residual_norm_eta_seconds": 1.5600002370774746e-05,
        "barrier_float_validation_seconds": 6.00004568696022e-06,
        "reference_error_and_residual_seconds": 1.8300022929906845e-05
      }
    },
    "worst_hotspot": {
      "dataset": "corner_development",
      "index": 0,
      "h": [
        0.2,
        0.2,
        0.2,
        0.2
      ],
      "selected_rank": 8,
      "diagnostic_rank": 8,
      "hotspot_error": 0.00040335962920895474,
      "field_linf_error": 0.003979762955355237,
      "relative_l2_error": 0.003972587650486338,
      "residual_linf": 0.0017901246284979244,
      "residual_l2": 0.0035011062067545305,
      "relative_residual_l2": 0.20496990042980678,
      "eta_float": 1.4175549401917942,
      "eta_over_observed_field_error": 356.1907973147768,
      "fom_residual_eta_float": 3.516631430500184e-13,
      "fom_relative_residual": 1.184130454210336e-13,
      "min_Az_float": 0.9999999999995453,
      "field_target_exceeded": true,
      "eta_trigger_candidate": true,
      "timing": {
        "fom": {
          "assembly_seconds": 0.0009913999820128083,
          "linear_solve_seconds": 0.0008924000430852175,
          "assembly_and_solve_seconds": 0.0018838000250980258,
          "full_solve_count": 1
        },
        "rom": {
          "assembly_seconds": 0.001122299931012094,
          "projection_seconds": 5.550007335841656e-05,
          "reduced_solve_seconds": 5.0299917347729206e-05,
          "reconstruction_seconds": 3.8000289350748062e-06,
          "residual_evaluation_seconds": 2.220005262643099e-05,
          "online_total_seconds": 0.0012541000032797456,
          "verification_seconds": 2.059992402791977e-05
        },
        "diagnostic_reassembly_seconds": 0.0010469999397173524,
        "residual_norm_eta_seconds": 1.5600002370774746e-05,
        "barrier_float_validation_seconds": 6.00004568696022e-06,
        "reference_error_and_residual_seconds": 1.8300022929906845e-05
      }
    },
    "effectivity_min": 330.3285016845934,
    "effectivity_median": 529.8041695067691,
    "effectivity_max": 734.1115117214964,
    "min_Az_float": 0.9999999999995453,
    "max_fom_relative_residual": 1.184130454210336e-13,
    "fraction_cases": 64,
    "fraction_cells": 480,
    "fraction_all_passed": true,
    "no_failure_statement": "Field error above tau found only as documented in development rows"
  },
  "counts": {
    "new_fom_calls": 16,
    "new_rom_calls": 16,
    "reused_tuning_fom": 12,
    "reused_tuning_rom": 12
  },
  "costs": {
    "barrier_vector_construction_seconds": 0.00014309992548078299,
    "fraction_validation_seconds": 0.002405200037173927,
    "new_corner_fom_assembly_solve_seconds": 0.030793899903073907,
    "new_corner_rom_online_seconds": 0.01908019999973476,
    "diagnostic_reassembly_seconds": 0.03244759968947619,
    "residual_norm_eta_seconds": 0.000549000222235918,
    "float_Az_validation_seconds": 0.00017060060054063797,
    "reference_evaluation_seconds": 0.0005812996532768011,
    "basis_update_seconds": 0.0,
    "basis_update_count": 0
  },
  "checks_passed": true
}
