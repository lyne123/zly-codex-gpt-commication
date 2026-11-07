# 2026-11-07-04 去除辅助判断对照测试

**离线约定范围验收通过**，高电平和相邻低电平均≥2ns。NoAux BIT生成状态：True；原离线交付时未烧录FPGA/Flash，正式RTL与Corrected BIT保留。

**后续上板实测：零配对错误验收 FAIL。** 用户授权后已成功下载NoAux，未写Flash。10MHz/50%下前10000个有效输出同时记录重复上升沿202次、孤立下降沿29次、时间越界0次；样本STD=76.055889ps，MAE相对50ns设定值=384.312500ps，MaxAbs=779ps。全部10011个有效输出、50份原始ILA CSV及之前失败日志保留，见[上板报告](HARDWARE_REPORT.md)。缺少示波器实测参考，不作绝对准确度结论；没有修改RTL或重新构建。

- [详细结果](RESULTS.md)、[范围确认](SCOPE_DECISION.md)、[时序报告](TIMING_REPORT.md)、[机器状态](VALIDATION.json)。
- `rtl/`：完整参数化候选；默认ENABLE_AUX_CONFIRM=1，NoAux编译固定0。`reference/rtl/`及`RTL.diff`保留原版和差异。
- 原阈值上升1～60、下降5～63，8参数不变，确认级保留，相对Corrected新增延迟0。
- 核心Setup/Hold +0.099/+0.054ns；历史14条ILA负端点保留，全部实际NoAux报告在results/timing。
- `results/RTL_GATE.json`保留原完整补充FAIL；`SCOPED_RTL_GATE.json`是用户确认范围的新判定。没有改波形或删异常。
- `results/sdf/noaux/`：最小和完整原始CSV、完整压缩日志、注释证据、原完整与范围两份摘要。
- `results/SDF_COMPARISON.csv`：相同输入ID的AuxOn/NoAux误差比较；旧AuxOn文件通过不可变提交和SHA256引用，不重复打包。
- `implementation/`：本次路由/综合DCP、SDF、网表、有效约束，以及NoAux.bit/NoAux.ltx。大文件使用Git LFS。
- `inputs/`、`sim/`、`scripts/`、`results/rtl/`保存全部必要输入、验证程序和失败记录。完整SDF日志无损压缩，原日志位置及原始SHA见RUN_MANIFEST。
- `FILE_LIST.csv`及`SHA256SUMS.txt`为清单与校验，均不含自身，避免循环。

原完整RTL补充模型的短间隔FAIL仍保留；通过范围门不等于无条件支持<2ns输入。未重新校准或拟合参数，也没有把数字验收结果当作上板修复结论。
