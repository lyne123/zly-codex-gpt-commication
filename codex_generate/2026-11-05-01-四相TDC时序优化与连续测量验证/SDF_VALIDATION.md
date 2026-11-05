# 实现后SDF验证

Vivado2022.2、xc7k325tffg900-2、simprims_ver/7系列器件模型，slow/MAX、1 ps。每版DCP、实际导出网表、SDF及运行输入均有SHA256；静态$sdf_annotate文件和xelab --maxdelay对应，原文件未编辑。

| 阶段 | 版本 | SDF单元数 | 关键单元 | 主验证注释成功 | 主验证时序告警 |
|---|---|---:|---|---|---:|
| original | baseline | 8705 | 64 CARRY4 / 256 FF / 7 LUT1 | True | 1159787 |
| original | compensated | 8759 | 64 CARRY4 / 256 FF / 7 LUT1 | True | 1159787 |
| optimized | baseline | 8768 | 64 CARRY4 / 256 FF / 7 LUT1 | True | 1159591 |
| optimized | compensated | 8794 | 64 CARRY4 / 256 FF / 7 LUT1 | True | 1159630 |

完整scope分类、5us前/后统计及原异常窗口告警在各批次timing_violation_counts/scopes.csv和原simulation.log。关键单元清单覆盖不是全局逐路径注释百分比；没有虚构工具未提供的成功率。
原Baseline的109条ILA告警来自ILA3异步PWM探针（bit27和G_NMU[4]），DCP扇入追踪见original_ila_pwm_warning_fanin.txt；不能当作ILA2同步计数器违例。TDL85,549条、PWM同步器383条、启动复位2条独立分类；MMCM未用CLKOUT5/6 period告警原因仍未获确认。
原Baseline本轮使用已有O2/typical快照，新编译采用官方O3/debug off加速计算，MAX SDF、timing checks及transport/pulse参数保持；原Compensated全量O3与原冻结O2的逐事件一致性记录作为编译优化对照。
上板、PVT/其他动态时序角及完整板级IO预算未执行。数值可输出不能代替亚稳态或硅片精度签核。
