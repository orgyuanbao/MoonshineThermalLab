# thermal-rom 固定POD基线

本文件由原生实验脚本按实际运行记录生成，局部审核状态pending。协议来自协调者事先给定的用户消息；若stage2_protocol.txt被找到，其原文及哈希保存在config中，否则不声称已读取该文件。使用阶段1原始算子，执行前json.load解析01_model.json并核对34项通过及源码哈希，读取阶段1说明与审核补记，不重跑旧实验。

训练24点、调参12点，独立种子20261025、20261026，对数均匀采样；没有最终测试集。未中心化训练快照SVD，数值秩阈值max(S.shape)*eps*s[0]，合法候选1、2、4、8、12、24。只用调参最大场Linf误差和预设tau=1e-3选择最小达标秩；若不达标selected_rank为空，最大合法秩仅用于诊断。

精确算术：A为阶段1已论证的SPD矩阵，V满列秩则c.T@(V.T@A@V)@c=(V@c).T@A@(V@c)>0，因此约化系统唯一可解。实际核心为Ar=V.T@(A@V), br=V.T@b, a=np.linalg.solve(Ar,br), u=V@a。正交性采用||V.T@V-I||inf；检查投影尺寸、投影残差、Galerkin残差、有限值和存盘一致性。

误差均相对同一浮点FOM：热点abs(max(u)-max(ref))；场误差max(abs(u-ref))；相对L2为欧氏误差范数除以参照范数，均匀面积权重抵消；相对残差||b-Au||2/||b||2。零分母且零分子记0，否则null表示未定义。

训练与调参FOM只各求解一次并跨秩复用；每个ROM重新装配，同步记录装配、投影、小矩阵求解、重构、残差与开发检查耗时。没有基更新。离线快照、SVD及调参参照代价均保留；在线比值不包含离线成本，另列离线加指定线上总成本。全部记录见02_baseline.json，参数、全部候选ROM/FOM解、奇异值与基见独立运行目录。计时仅单次观测，不支持稳定加速结论。最终报告写盘时间不在wall_seconds_before_final_reports内，工具进程耗时另见原版返回。

本轮未修改原求解器；旧结果自动备份。阶段1初审证据不足及后续通过记录保持不变。下一步依赖本存档开展16角点与调参数据的开发失效分析，之后提交自包含局部审核。

实际运行摘要：

{
  "run_timestamp_utc": "20261025T073143523549Z",
  "status": "checks_passed_pending_review",
  "exit_code": 0,
  "basis_path": "workspace/results/02_run_20261025T073143523549Z/basis.npz",
  "numeric_rank": 24,
  "rank_tolerance": 5.56598215080949e-13,
  "selected_rank": 8,
  "diagnostic_rank": 8,
  "counts": {
    "fom_calls": 36,
    "rom_calls": 216
  },
  "costs": {
    "offline_snapshot_wall_seconds": 0.050428800052031875,
    "offline_svd_seconds": 0.0034753000363707542,
    "npz_persistence_seconds": 0.03707279998343438,
    "basis_update_seconds": 0.0,
    "basis_update_count": 0,
    "fom_assembly_seconds": 0.0442399000748992,
    "fom_solve_seconds": 0.028961900155991316,
    "fom_residual_seconds": 0.001402299851179123,
    "all_candidates_online_seconds": 0.2554977993713692,
    "tuning_fom_assembly_solve_seconds": 0.02415350009687245,
    "diagnostic_tuning_online_seconds": 0.01387240004260093,
    "observed_fom_over_rom_online_ratio": 1.741119058180211,
    "offline_plus_diagnostic_tuning_seconds": 0.06777650013100356
  },
  "checks": [
    {
      "name": "train_fom_residual_0",
      "value": 3.977067192158769e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_0",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_1",
      "value": 3.481778619381495e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_1",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_2",
      "value": 2.1655094798851216e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_2",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_3",
      "value": 2.008024876096694e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_3",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_4",
      "value": 1.789127915403807e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_4",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_5",
      "value": 2.5188133537497834e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_5",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_6",
      "value": 2.459084189151444e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_6",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_7",
      "value": 2.0604049912171608e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_7",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_8",
      "value": 2.192440596054959e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_8",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_9",
      "value": 2.091038312557549e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_9",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_10",
      "value": 2.9638805840481925e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_10",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_11",
      "value": 2.2368154337730016e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_11",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_12",
      "value": 2.978486364726951e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_12",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_13",
      "value": 2.6214422867918045e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_13",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_14",
      "value": 1.5910400812944692e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_14",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_15",
      "value": 4.209218609261917e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_15",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_16",
      "value": 1.7693377727404144e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_16",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_17",
      "value": 3.017128981896988e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_17",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_18",
      "value": 2.4178475507115106e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_18",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_19",
      "value": 2.230988553234027e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_19",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_20",
      "value": 3.578550698576892e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_20",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_21",
      "value": 3.438831641204143e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_21",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_22",
      "value": 2.983219143079639e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_22",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "train_fom_residual_23",
      "value": 3.148370753775584e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "train_fom_nonfinite_23",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_0",
      "value": 1.953500625034264e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_0",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_1",
      "value": 1.9128708641079782e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_1",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_2",
      "value": 2.5272983596543784e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_2",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_3",
      "value": 1.8990394152077083e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_3",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_4",
      "value": 1.426388081204481e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_4",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_5",
      "value": 2.5739905940663483e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_5",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_6",
      "value": 4.194795010470746e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_6",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_7",
      "value": 2.274804906225556e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_7",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_8",
      "value": 3.0012799727024987e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_8",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_9",
      "value": 2.038777290527916e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_9",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_10",
      "value": 2.882729254193136e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_10",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "tune_fom_residual_11",
      "value": 2.6520182551892295e-14,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "tune_fom_nonfinite_11",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "snapshot_svd_relative_reconstruction",
      "value": 2.561984020778869e-15,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "training_tuning_overlap_count",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "orthogonality_rank_1",
      "value": 4.440892098500626e-16,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rank_limit_1",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_shape_rank_1",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_residual_rank_1",
      "value": 1.3110437297010507e-16,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "galerkin_residual_rank_1",
      "value": 2.097669967521681e-15,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "projected_symmetry_rank_1",
      "value": 0.0,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rom_nonfinite_rank_1",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "orthogonality_rank_2",
      "value": 5.967448757360216e-16,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rank_limit_2",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_shape_rank_2",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_residual_rank_2",
      "value": 2.2047068329713553e-16,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "galerkin_residual_rank_2",
      "value": 2.302049894269663e-15,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "projected_symmetry_rank_2",
      "value": 9.75781955236954e-18,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rom_nonfinite_rank_2",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "orthogonality_rank_4",
      "value": 1.6688039838896884e-15,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rank_limit_4",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_shape_rank_4",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_residual_rank_4",
      "value": 3.1418393743537793e-16,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "galerkin_residual_rank_4",
      "value": 1.923254222957065e-15,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "projected_symmetry_rank_4",
      "value": 4.5102810375396984e-17,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rom_nonfinite_rank_4",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "orthogonality_rank_8",
      "value": 2.586581122898668e-15,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rank_limit_8",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_shape_rank_8",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_residual_rank_8",
      "value": 3.88980919012533e-16,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "galerkin_residual_rank_8",
      "value": 2.357040205252312e-15,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "projected_symmetry_rank_8",
      "value": 7.979727989493313e-17,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rom_nonfinite_rank_8",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "orthogonality_rank_12",
      "value": 2.921274333544943e-15,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rank_limit_12",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_shape_rank_12",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_residual_rank_12",
      "value": 4.816685455302584e-16,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "galerkin_residual_rank_12",
      "value": 2.934400495630321e-15,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "projected_symmetry_rank_12",
      "value": 9.367506770274758e-17,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rom_nonfinite_rank_12",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "orthogonality_rank_24",
      "value": 4.673805830204825e-15,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rank_limit_24",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_shape_rank_24",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "projected_residual_rank_24",
      "value": 6.042158539633671e-16,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "galerkin_residual_rank_24",
      "value": 4.736969597084648e-15,
      "tolerance": 1e-10,
      "passed": true
    },
    {
      "name": "projected_symmetry_rank_24",
      "value": 3.608224830031759e-16,
      "tolerance": 1e-12,
      "passed": true
    },
    {
      "name": "rom_nonfinite_rank_24",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "saved_training_exact_match",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "saved_basis_exact_match",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "fom_call_count",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    },
    {
      "name": "rom_call_count",
      "value": 0.0,
      "tolerance": 0,
      "passed": true
    }
  ],
  "rank_curves": [
    {
      "dataset": "train",
      "rank": 1,
      "orthogonality_inf": 4.440892098500626e-16,
      "max_hotspot_error": 0.021467554711647553,
      "max_field_linf_error": 0.02548491755031031,
      "max_relative_l2_error": 0.32665326606898193,
      "max_relative_residual_l2": 0.9934554707890352,
      "online_total_seconds": 0.029150599846616387
    },
    {
      "dataset": "tune",
      "rank": 1,
      "orthogonality_inf": 4.440892098500626e-16,
      "max_hotspot_error": 0.011294675160705855,
      "max_field_linf_error": 0.017298742341493985,
      "max_relative_l2_error": 0.1899505116080103,
      "max_relative_residual_l2": 0.9381728817940518,
      "online_total_seconds": 0.014714900054968894
    },
    {
      "dataset": "train",
      "rank": 2,
      "orthogonality_inf": 5.967448757360216e-16,
      "max_hotspot_error": 0.007690550725851071,
      "max_field_linf_error": 0.01867682321206045,
      "max_relative_l2_error": 0.23009634099388127,
      "max_relative_residual_l2": 0.8516116014668595,
      "online_total_seconds": 0.028778399922885
    },
    {
      "dataset": "tune",
      "rank": 2,
      "orthogonality_inf": 5.967448757360216e-16,
      "max_hotspot_error": 0.009250333768611244,
      "max_field_linf_error": 0.012057271418881323,
      "max_relative_l2_error": 0.16895158417319014,
      "max_relative_residual_l2": 0.9264952252876423,
      "online_total_seconds": 0.012680800049565732
    },
    {
      "dataset": "train",
      "rank": 4,
      "orthogonality_inf": 1.6688039838896884e-15,
      "max_hotspot_error": 0.0011599148716525676,
      "max_field_linf_error": 0.005606388901272137,
      "max_relative_l2_error": 0.06341798691784388,
      "max_relative_residual_l2": 0.376068141667395,
      "online_total_seconds": 0.027564399759285152
    },
    {
      "dataset": "tune",
      "rank": 4,
      "orthogonality_inf": 1.6688039838896884e-15,
      "max_hotspot_error": 0.0019875165290034053,
      "max_field_linf_error": 0.008218301213348853,
      "max_relative_l2_error": 0.12118645525121709,
      "max_relative_residual_l2": 0.5100662254483365,
      "online_total_seconds": 0.01591959979850799
    },
    {
      "dataset": "train",
      "rank": 8,
      "orthogonality_inf": 2.586581122898668e-15,
      "max_hotspot_error": 1.1916040511941728e-05,
      "max_field_linf_error": 0.00018659515743277288,
      "max_relative_l2_error": 0.0015845885935410339,
      "max_relative_residual_l2": 0.018439090884743405,
      "online_total_seconds": 0.027227999875321984
    },
    {
      "dataset": "tune",
      "rank": 8,
      "orthogonality_inf": 2.586581122898668e-15,
      "max_hotspot_error": 2.700717595997132e-05,
      "max_field_linf_error": 0.00038407471965163503,
      "max_relative_l2_error": 0.003924151537289797,
      "max_relative_residual_l2": 0.037794888734532295,
      "online_total_seconds": 0.01387240004260093
    },
    {
      "dataset": "train",
      "rank": 12,
      "orthogonality_inf": 2.921274333544943e-15,
      "max_hotspot_error": 8.000297800139777e-07,
      "max_field_linf_error": 1.8691491816495015e-05,
      "max_relative_l2_error": 0.00010433165170593619,
      "max_relative_residual_l2": 0.00186366389498334,
      "online_total_seconds": 0.0282955999718979
    },
    {
      "dataset": "tune",
      "rank": 12,
      "orthogonality_inf": 2.921274333544943e-15,
      "max_hotspot_error": 1.314881999309181e-06,
      "max_field_linf_error": 2.9647789303641377e-05,
      "max_relative_l2_error": 0.00023758576317135056,
      "max_relative_residual_l2": 0.004231295450930908,
      "online_total_seconds": 0.013971299980767071
    },
    {
      "dataset": "train",
      "rank": 24,
      "orthogonality_inf": 4.673805830204825e-15,
      "max_hotspot_error": 1.304512053934559e-15,
      "max_field_linf_error": 1.304512053934559e-15,
      "max_relative_l2_error": 1.9209362042243027e-14,
      "max_relative_residual_l2": 1.2466435253894858e-13,
      "online_total_seconds": 0.02941449999343604
    },
    {
      "dataset": "tune",
      "rank": 24,
      "orthogonality_inf": 4.673805830204825e-15,
      "max_hotspot_error": 1.586747261361765e-10,
      "max_field_linf_error": 5.3269658833315914e-08,
      "max_relative_l2_error": 4.4169106070271035e-07,
      "max_relative_residual_l2": 1.9135496858062657e-05,
      "online_total_seconds": 0.013907300075516105
    }
  ]
}
