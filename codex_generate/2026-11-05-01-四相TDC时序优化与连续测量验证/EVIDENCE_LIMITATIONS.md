# 证据保留限制

上一轮2026-11-04-02原实验、RTL、原始CSV、BIT/DCP/SDF和日志均保持，原Baseline本轮完整复放的7份关键CSV已与冻结结果逐字节一致。

本轮首个优化实现的Vivado原生run目录在执行reset_run并切换到新运行目录时被工具清理，部分原生中间报告和中间检查点未能保留；相关控制台日志仍在。该轮最终物理DCP、BIT、SDF、网表、完整Timing Summary、Setup/Hold Top50、约束/CDC/时钟/路由报告及前端指纹等61份导出证据已复制冻结于results/trials/baseline_initial，并逐文件记录SHA256（inputs/BASELINE_INITIAL_SNAPSHOT.json）。原生中间报告不冒充已保存，也不以重生成报告冒充原文件。

后续实现直接从冻结DCP创建新分支，输出到独立trial目录，不再reset已有成功运行。所有主仿真原始CSV、已保存的失败日志和对应SDF继续完整保留。
