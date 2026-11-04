# XC7K325T 四相TDC外部技术审查说明

**实验整体验收：FAIL。** 归档副本的完整性检查与实验是否通过是两个独立结论。本次只复制既有证据和编写说明，不修改RTL、参数、CSV、报告或日志，不重新运行综合、实现、仿真和统计。

原工作目录：`D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/codex_generate/2026-11-04-02-四相TDC固定延迟补偿验证/`。新归档任务：`2026-11-04-02-四相TDC固定延迟补偿`。FILE_INDEX.csv/JSON逐项记录源相对路径、实际归档路径、字节数、SHA256。完全相同的重复内容只保存一份，由索引映射；补偿前后各五份完整RTL单独保留。

## 1. 实际RTL修改与流水线

原实验仅修改 `tdc_meas_top.v`、`tdc_time_locate.v`。归档前版本在01_RTL/before/rtl，后版本在01_RTL/after。三份未修改RTL为tdc_fine_layer.v、tdc_time_candicate.v、tdc_time_merge.v，均包含在两套完整快照中。差异见01_RTL/补偿RTL变更.patch。此次归档没有任何新的RTL修改。

顶层传递ENABLE_SKEW_COMP和8个18位signed参数；locate第2级按候选index/type选择、寄存对应偏移，与coarse/fine对齐；第3级计算mid−fine−offset，第4级合成、第5级模回卷，原5级valid/type流水不变。开关0为显式generate旁路；默认0参数是未校准占位，正式补偿实现由calibration_params.tcl装载以下值。

## 2. 八项参数、计算与公共延迟

单位均为ps，按物理相位与独立极性定义：

| 物理相位 | sel_index | Rise偏移 | Fall偏移 | 原始平均偏差 Rise/Fall | 有效数 每极性 |
|---|---:|---:|---:|---:|---:|
| 下一周期0° | 3 | 34698 | 34698 | 34698.25 | 320 |
| 90° | 0 | 34710 | 34710 | 34710.00 | 328 |
| 180° | 1 | 34861 | 34861 | 34861.25 | 320 |
| 270° | 2 | 34796 | 34796 | 34795.50 | 320 |

独立baseline slow/MAX SDF校准800个25.3 ns脉冲，100个编程相位×8；验证集不参与拟合。公共时间参考coarse epoch=675150 ps，模数M=2048000 ps。每个有效通道/极性独立计算 `error=signed_mod(T_measured−((T_input−epoch) mod M))`，取mean，再按既有提取脚本round得到整数offset。原始四路虚拟时间采用 `((C_raw+6) mod 1024)*2000+mid−fine`；候选对应`((C_candidate+1) mod 1024)*2000+mid−fine`。1600个候选的5拍对齐及算术核对均已通过。

这8项是**包含公共流水线整数周期与输入分发延迟的绝对偏移**。不能把约34.7 ns全解释为四通道偏斜。相对0°通道差为0/11.75/163.00/97.25 ps。Rise/Fall独立拟合、独立参数化；本确定性模型两者相等不代表硅片相等。补偿`T_corrected=(T_measured−offset) mod M`。

参数CSV、逐观测、相位覆盖、JSON及Tcl在03_Calibration/results；提取脚本在02_Project/scripts/experiment.py；完整计算过程见08_Reports/original/CALIBRATION_REPORT.md。旧校准调度与stimulus_v1原样保留，未改变已执行输入。

## 3. RMSE公式、样本与异常规则

误差`e_i=measured_width_i−true_width_i`；RMSE=`sqrt(sum(e_i²)/N)`，Bias=`sum(e_i)/N`，STD=`sqrt(sum((e_i−Bias)²)/N)`（总体STD），MaxAbs=`max(abs(e_i))`。成功率为正确配对事件数/预期输入数。只按真实边沿事件ID关联，不按CSV行号强行配对；漏沿、错配、重复和错误原始记录均保留，无阈值裁剪或删除异常。完整性失败时主表指标N/A，成功子集条件统计明确单列，不能冒充全量精度。

| 既有测试 | N 前/后 | Baseline RMSE ps | Compensated RMSE ps |
|---|---:|---:|---:|
| 25.3 ns | 200/200 | 135.602 | 53.147 |
| 20 MHz/50% | 200/200 | 143.269 | 69.735 |
| 10 MHz完整暂定帧 | 1056/1056 | 125.406 | 66.700 |

上述数值由原始comparison_metrics.csv更高精度值按三位小数展示，未重新计算数据。**10 MHz完整暂定帧与10 MHz/50%单项不同**；后者确定性相位抵消为0→0，不能称为硅片0 ps。两版主验证3512输入、3509输出、3507正确配对，有效率99.857631%；各测试Bias/STD/MaxAbs/改善率见原CSV与FINAL_RMS_COMPARISON.md，所有图的CSV源数据均保留。

## 4. 激励一致性与20 MHz异常事件

两版主SDF验证使用字节完全相同的激励，SHA256：`451a2cb59cc0704a9e5ac8454bb983237543705f2c4782789b3067be4d9fa76f`。实际input_tb.sv、输入stimulus、truth、input_sha256及运行快照均保留；早期RTL与旧stimulus_v1另存，不与主SDF验证混用。

两版缺失R事件2918、2984、3050；缺失F事件2917、2983，重复ID为0。baseline错配为F2918配R2917输出50900 ps、F2984配R2983输出50940 ps（对应帧头预期2500 ps）。关联ID而不是成功子集精度是判断错误的依据。

| 事件ID | 暂定位置 | high ps | 前一low ps |
|---|---|---:|---:|
| 2917 | bank6/ch63 | 47335 | 2669 |
| 2918 | bank7/header0 | 2500 | 1330 |
| 2983 | bank7/ch63 | 47416 | 2581 |
| 2984 | bank8/header0 | 2500 | 1293 |
| 3050 | bank9/header0 | 2500 | 1736 |

冲突238744150/242044150/245344150 ps，repeat245346150 ps，merge孤立下降沿错误2在245358150 ps。候选原始帧有混合极性，被既有门控丢弃。完整证据见ANOMALIES.md与raw/candidate/timestamps/widths/errors/summary CSV及JSON。暂定边沿对齐帧头加中心对齐SPWM带来短低电平，不等价于真实ATC芯片协议已失败。

## 5. 两版本静态时序

单位ns，未经归档重写：

| 版本 | WNS | TNS | WHS | THS | Setup失败端点 | Hold失败端点 |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | -0.163 | -0.589 | +0.058 | 0 | 12 | 0 |
| Compensated | -0.173 | -1.083 | +0.058 | 0 | 19 | 0 |

两个版本500 MHz setup均FAIL。最差路径90°编码树到0°pack90_d1，另有ILA路径。06_Timing包含原timing_summary、setup_paths、hold_paths、post-route报告；07_Bitstream保存版本明确的BIT/DCP，生成日志在05_Results。XDC未设板级PWM/reset输入延迟、dbg_hub频率元数据问题与基线约束使用阶段差异仍保留。两版前端236条同名网路由不同，不能声称完全同布局。

## 6. SDF、器件模型与告警

器件xc7k325tffg900-2，Vivado2022.2，simprims_ver及7-series器件模型，slow/MAX路由后SDF，1 ps分辨率。elaboration日志表明注释成功，实际注释SDF/网表及输入SHA均保留。64个TDL CARRY4、256个采样FF、7个LUT1关键清单齐全；这是关键清单覆盖，不是工具全局逐路径注释百分比，未生成虚假的注释率。

每版主验证1,159,787条动态告警：MMCM未用CLKOUT5/6 period 1,073,744；PWM同步setuphold383；TDL异步采样setuphold85,549；其他recrem2、setuphold109。所有原日志保留，未禁用timing checks/notifier。MMCM零周期检查原因未确认，不能当作已解释的误报。

## 7. PASS、FAIL及未执行

| 状态 | 项目与边界 |
|---|---|
| PASS | 原RTL/显式旁路/零参数及signed/wrap单元检查，COARSE_W=2和10各5044有效检查 |
| PASS | 理想原语RTL完整3512脉冲/7024时间戳功能回归；不代表物理精度 |
| PASS | 25.3 ns、各独立10/20 MHz固定占空比、95%帧头、10 MHz完整暂定帧的事件完整性与既有指标 |
| PASS（限范围） | SDF注释关键清单；结果FIFO序列核对；独立fifo_probe错误码2在500/100 MHz序列一致，非主验证全量错误FIFO审计 |
| FAIL | 两版500 MHz setup；20 MHz完整暂定帧；5%帧头全量；SPWM全量；全部输入全量事件关联；动态时序尚不能签核；整体验收 |
| 未执行 | 上板硅片、PVT/其他动态SDF角、真实ATC协议、板级完整IO时序签核；归档阶段没有重跑任何实验 |

## 8. 目录、压缩包、完整性与复现

01_RTL：完整前后版本与diff；02_Project：原/实际XPR、XDC、四种IP XCI、所有实验脚本及实际运行命令；03_Calibration：原参数与计算证据；04_Testbench：固定/PWM/帧头/SPWM、真实边沿、实际TB快照；05_Results：全部原CSV、图与数据、原始/失败日志；06_Timing：SDF/网表/原时序报告；07_Bitstream：两版BIT/DCP；08_Reports：原报告与新增审查说明。

`TDC_Review_Source_Results.zip`和`TDC_Review_Implementation.zip`位于本review_package的父目录。解压到同一目录可组合全部证据；两个包均附索引/报告，源码结果包也包含时序文本报告，实现包包含BIT/DCP/SDF/网表。没有因大小省略关键证据。

SHA256SUMS覆盖重要文件；FILE_INDEX涵盖全部原始CSV与.log/.jou/.vds路径，完全相同副本按哈希映射。EXCLUDED_CACHE_FILES只列不打包的构建缓存、可再生中间文件/工具二进制，原文件未删除。ARCHIVE_VERIFICATION记录字节一致性。原报告与工程配置中的历史路径保持原样，可由索引查找；原REPRODUCE及脚本也保留，复现须在新工作副本进行，不能在冻结证据上运行会重写输出的脚本。

Git归档版仅把>5 MB日志无损gzip压缩，PUBLICATION_INDEX逐项记录压缩前后路径/大小/SHA。解压所得字节必须与FILE_INDEX的原SHA一致。Git LFS用于BIT/DCP/SDF/大型网表和.gz日志，克隆后需`git lfs pull`获取真实内容。两个ZIP留作本地交付，Git不重复提交ZIP；所有关键证据已逐文件上传，不以外部本地路径代替上传。
