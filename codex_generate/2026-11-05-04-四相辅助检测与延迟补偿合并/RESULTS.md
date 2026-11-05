# 四相辅助检测与延迟补偿合并

**最终验收：FAIL。独立合并和全量RTL验证完成；实现后发现4条核心Setup违例，按任务要求停止后续依赖步骤，未运行新Compensated完整MAX-SDF，未生成最终BIT。**

## 1. 版本来源与修改范围

原Compensated：`d30dfeb9779f7d3c4859fbfb300bebd2d9481a7b`，`2026-11-05-01-四相TDC时序优化与连续测量验证/results/optimized/compensated/`。
四相辅助Baseline：`6b341d88497541f23eaefee1cfad4e4925c7f2aa`，`2026-11-05-03-四相TDC辅助边沿检测优化/rtl/`。
12个Git对象与本地源文件完成逐字节或仅CRLF等价校验，参数CSV哈希与原Compensated一致，见inputs/SOURCE_PROVENANCE.json。

本任务rtl/5个文件与6b341d8的辅助Baseline逐字节一致。相对于旧Compensated仅tdc_fine_layer.v变化：直接复用已通过的四相辅助采样、电平传输、有序边沿归属、rise/fall去重和confirm_edge；没有删寄存器、调整时序顺序或引入Toggle。
top、candidate、locate、merge逐字节保留旧补偿版本。实际启用补偿通过inputs/compensation_params.tcl的原generic与sim/compensation_parameters.vh完成，没有重写算法或改参数默认值。
正式工程当前Baseline与历史目录均未覆盖，5个正式RTL哈希不变；新增/修改的实验文件仅在本任务目录，另在任务索引追加一行。
四个版本源码分别保存在original/baseline_original、original/baseline_aux4、original/compensated_previous、rtl；历史大型实现文件保持原路径，不重复复制，源码/参数/测量证据有独立副本。

## 2. 补偿参数与原算法

| 物理TDL | 相位 | sel_index | Rise ps | Fall ps |
|---|---:|---:|---:|---:|
| TDL0 | 0°（下一周期） | 3 | 36081 | 36081 |
| TDL1 | 90° | 0 | 36011 | 36011 |
| TDL2 | 180° | 1 | 35742 | 35742 |
| TDL3 | 270° | 2 | 35756 | 35756 |

8参数来自旧独立SDF校准，包含公共流水线、输入分发及粗时间epoch的偏移，不能当作只有相对通道偏差。Rise/Fall独立选择，本组冻结值相等；没有全部设成相同值、没有重新拟合。
补偿位于候选选择后Time Locate中：第1级锁定code/index/type，第2级把原mid-offset常量与fine、coarse并行锁定，第3级计算relative，第4级加粗时间，第5级正常模回卷。
fine_rise=code×10ps；fine_fall=(64-code)×10ps；timestamp=(coarse×2000+mid-fine-offset) mod 2048000ps。正offset从正向时间戳减去。
保持18位有符号参数、19位中细时间、COARSE_W+11=21位输出、扩展有符号运算，10ps/tap；无新增舍入。原参数拟合的round规则未再执行。
脉宽修正关系为width_C=width_B+offset_rise-offset_fall（正常模回卷），公共偏移相消；该修正不改变输入真实PWM宽度，测量值会按原算法修正。

## 3. RTL功能验证：PASS

- 使用与6b341d8完全相同的3512脉冲输入/边沿/频率/占空比/扰动及真值文件，SHA256相同；没有减少或调整样本。
- 旁路与补偿各输出7024个边沿、3512个脉宽；前端raw/candidate/sampled_taps/aux_trace逐字节一致，FIFO序列等于脉宽输出，错误FIFO为空。
- 旁路的candidate/timestamps/widths/fifo与6b341d8冻结RTL结果逐字节相同；由此复用严格事件归属，补偿只改变原算术，7024次timestamp及3512次width逐项核对通过。
- valid、极性、候选选择、输出周期全部一致，未增加流水拍数。
- 8321个Locate边界样本覆盖4相×2极性×65有效tap的520组合，162次负向回卷、1次正向回卷，无无符号下溢或格式变化。
- 六个历史ID的rise/fall/width在RTL中各恢复一次。**新实现的SDF恢复情况未执行，不能沿用旧Baseline的SDF成功结论。**

观察数据：results/rtl/*/rtl_full中的raw/candidate/timestamps/widths/FIFO等CSV，results/RTL_COMPENSATION_TRACE.csv、LOCATE_BOUNDARY_INPUT/OUTPUT.csv及RTL_STAGE_GATE.json。
首轮统计错误使用SDF物理延迟关联理想RTL，导致假错配；已确认原CSV与旧RTL逐字节一致，修正为旧RTL专用关联方法，失败分析完整保存在analysis_failed_sdf_reference，未改原始仿真数据。
首次边界覆盖检查发现缺少正向回卷用例，保留原测试日志并补充该用例后通过；未修改正式RTL。

## 4. 实现后验证与停止原因

完成一次顶层综合与布局布线，IP配置保持原值，在新目录登记并生成OOC产品；复用6b341d8路由参考、原有效XDC和既有ILA布局/BRAM功耗脚本。
导出同一冻结设计的design.dcp、design.v、Slow design.sdf、完整报告；未生成BIT。

全局WNS=-0.050ns、TNS=-0.257ns、WHS=+0.054ns、THS=0；18个Setup失败端点中14个为历史ILA2，4个是真实核心路径。
Locate最差-0.047ns（旧Compensated -0.019ns、辅助Baseline +0.021ns），另外Locate -0.022/-0.002ns；结果FIFO输入复位控制到BRAM ENARDEN -0.018ns。
辅助Setup/Hold仍为+0.220/+0.108ns，327个固定TDL/分发单元的类型/LOC/BEL保持不变。
**没有通过新增false path、降低500MHz或更改补偿/流水掩盖违例。** 详细起点、终点、逻辑及布线见TIMING_REVIEW.md。

## 5. SDF与四相残余固定延迟：未执行

因核心STA失败，完整MAX-SDF未编译、未运行，SDF注释成功率、动态timing warning及新版3512脉冲恢复情况均未取得。
PHASE_COMPENSATION_REPORT.csv列出原8参数及RTL算术覆盖；新版SDF raw/comp bias、相对TDL0残余延迟等字段明确留空并标注NOT_EXECUTED。
不能用RTL理想模型、旧Baseline或旧Compensated的SDF替代新实现证据，不能宣称四相残余延迟改善。

## 6. 精度比较

以下历史版本使用同一3512真值，保留各版本失败事件；RMSE仅对正确配对子集统计，不把它当作全量通过。

| 版本 | 正确配对 | Width RMSE ps | Bias ps | STD ps |
|---|---:|---:|---:|---:|
| A_original_baseline | 3507/3512 | 124.700 | -5.787 | 124.566 |
| B_previous_compensated | 3506/3512 | 68.837 | -1.045 | 68.829 |
| A2_optimized_baseline | 3506/3512 | 174.661 | -0.599 | 174.660 |
| D_aux4_baseline | 3512/3512 | 161.614 | 1.647 | 161.606 |
| C 新四相辅助+Compensated | 未执行 | — | — | — |

A为优化前原始Baseline；A2为Nov5时序优化Baseline；B为本次冻结参数对应的Nov5 Compensated；D为已验证的四相辅助Baseline，单独列出避免“Baseline”混淆。历史FAIL结论保持不变。
BASELINE_VS_COMPENSATED.csv保留历史Rise/Fall/Width RMSE、Bias/STD/MaxAbs及10MHz、20MHz、各占空比、ATC帧头/数据区统计，并列出A/B相同事件ID的公平比较。
逐事件误差保留在results/HISTORICAL_EVENT_COMPARISON.csv；源CSV和SHA256见results/historical及inputs/HISTORICAL_REFERENCE.json。
新版C的全部物理精度数据未执行，不能判断B/C同ID误差变化、频率切换影响或补偿效果是否保持；相应字段留空，而非填0或套用D的结果。
没有对3512验证数据重新拟合8参数，也没有删除离群样本。

## 7. BIT、限制与后续

最终Compensated BIT **未生成**。VALIDATION.json记录FAIL及bit_generation_allowed=false，完整SDF/物理补偿项目为NOT_EXECUTED_BLOCKED_BY_CORE_TIMING。
未执行硬件、其他PVT、2ns以下脉宽保证；旧版本的失败和先前bitstream保持原样。
下一步应先解决Locate最终模回卷路径及结果FIFO同步复位控制的实际Setup负裕量，再按完全相同3512激励运行完整MAX-SDF，验证四相残余延迟和B/C同ID精度，最后决定是否生成BIT。
本任务未做进一步时序优化或修改FIFO/流水，也未推送到GitHub；交付保存在本地独立任务目录。

文件清单见FILE_LIST.md，重要证据SHA256见SHA256SUMS.txt；复现及当前停止门槛见REPRODUCE.md。
