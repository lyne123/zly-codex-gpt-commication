# 四相TDC时序优化与连续测量验证

本次整体验收 **FAIL**；Timing=False，Functional=False，Compensation=True。

- [完整结论](FINAL_REPORT.md)、[真实原始根因](TIMING_ROOT_CAUSE.md)、[RTL修改与对齐](RTL_CHANGE_REVIEW.md)。
- [时序/资源对比](TIMING_BEFORE_AFTER.md)、[连续PWM与因果边界](CONTINUOUS_PWM_VALIDATION.md)、[SDF核对](SDF_VALIDATION.md)。
- [独立物理校准](CALIBRATION_REPORT.md)、[8参数前后及自身拟合](OLD_VS_NEW_CALIBRATION.csv)、[全部RMSE/Bias/STD/MaxAbs](RMS_COMPARISON.csv)。
- [测试执行状态](TEST_STATUS.md)、[复现说明](REPRODUCE.md)、[物理试验清单](PHYSICAL_TRIALS.csv)、[已知证据保留缺口](EVIDENCE_LIMITATIONS.md)。
- results/optimized/{baseline,compensated}：两份新BIT、DCP、实际网表/SDF及完整冷重算Setup/Hold报告。
- original/{baseline,compensated}/rtl与rtl：优化前后完整5份RTL；RTL_CHANGES.patch只改两文件。
- results/EVENT_COMPARISON.csv为八组3512事件完整连接，ANOMALY_EVENT_REVIEW.csv为重点事件审查；原始测量不被这些派生表替换。
- 原始激励/真值、CSV、正常/失败日志均保留。大log/jou采用gzip无损压缩，ARCHIVE_MAPPING.csv记录原SHA，SHA256_MANIFEST.json和FILE_LIST.csv给出交付清单。

根目录少量仅含表头的CSV来自最初启动诊断；主实验CSV以results各批次目录为准。scripts/legacy_*为历史参考，主复现入口见REPRODUCE.md，不重新生成或替换冻结激励。
归档保留必要工程配置、XDC/XCI、实际IP产品和失败小型dump；未加入批量编译对象、可再生运行程序、波形缓存及.Xil。完整本地任务目录仍保留。没有用这些可再生缓存替代关键原始CSV、SDF、BIT、DCP或失败日志。
实际请求策略和生效策略可能不同：补偿顶层最终采用独立非工程综合，增量默认RuntimeOptimized覆盖了请求的place/phys/route指令；SOURCE_PROVENANCE.json与日志给出实际情况。TimingClosure试验的瞬态估计不作最终结果。
