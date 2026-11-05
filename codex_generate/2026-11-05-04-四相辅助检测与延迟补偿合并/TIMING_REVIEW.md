# 核心时序验收：FAIL

器件xc7k325tffg900-2，Vivado 2022.2，500MHz四相；Slow/MAX Setup、Fast/Min Hold；沿用原有效XDC和IP约束，没有新增false path或multicycle。

WNS -0.050ns，TNS -0.257ns；WHS 0.054ns，THS 0.000ns；18个Setup端点失败、0个Hold失败。
其中14个ILA2端点与历史辅助Baseline相同，逐个实际扇出检查不回馈测量/FIFO；4个核心端点不能归入ILA或TDL异步采样告警。

## 4条真实同步Setup违例

- -0.047 ns：`u_tdc_time_locate/s4_sum_reg[2]/C` → `u_tdc_time_locate/timestamp_ps_reg[20]/D`。
- -0.022 ns：`u_tdc_time_locate/s4_sum_reg[0]/C` → `u_tdc_time_locate/timestamp_ps_reg[19]/D`。
- -0.018 ns：`rst_sync_500m_reg[1]/C` → `u_fifo_tdc_result/U0/inst_fifo_gen/gconvfifo.rf/grf.rf/gntv_or_sync_fifo.mem/gbm.gbmg.gbmga.ngecc.bmg/inst_blk_mem_gen/gnbram.gnativebmg.native_blk_mem_gen/valid.cstr/ramloop[0].ram.r/prim_noinit.ram/DEVICE_7SERIES.NO_BMM_INFO.SDP.SIMPLE_PRIM36.ram/ENARDEN`。
- -0.002 ns：`u_tdc_time_locate/s4_sum_reg[2]/C` → `u_tdc_time_locate/timestamp_ps_reg[11]/D`。

Locate最差路径属于原第5级时间戳模归一化/选择：s4_sum低位 → LUT2 → 3个CARRY4 → wrapped_time2 → LUT5 → timestamp高位。该路径不位于TDL采样或辅助同步器中。
实际数据延迟1.971ns（逻辑0.771、布线1.200），2ns周期，clock skew -0.050ns、uncertainty0.060ns。wrapped_time2单段网线0.708ns、扇出21。
旧Compensated的Locate最差-0.019ns；新版本-0.047ns，恶化28ps；相对于四相辅助Baseline的+0.021ns，恶化68ps。
这说明原补偿路径仍未收敛，不是RTL算法或新辅助采样功能错误的证据；不能凭STA推断具体输入事件一定丢失或一定通过。

结果FIFO违例是rst_sync_500m_reg[1] → 两级LUT → BRAM ENARDEN，数据延迟1.613ns（逻辑0.370、布线1.243），skew -0.017ns；同步复位释放后的控制路径真实参与测量FIFO，不能当作异步TDL告警或随意false-path。
模块输出端统计会漏掉来自外部复位寄存器的路径，因此本报告取from/to两类路径较差值。

## 模块最差Setup（含输入边界）

| 模块 | 最差裕量ns |
|---|---:|
| u_tdc_fine_layer | +0.050 |
| u_tdc_time_candicate | +0.265 |
| u_tdc_time_locate | -0.047 |
| u_tdc_time_merge | +0.168 |
| u_fifo_tdc_result | -0.018 |
| u_fifo_tdc_error | +0.132 |
| u_ila2 | -0.050 |

辅助Setup +0.220ns、Hold +0.108ns，与6b341d8辅助Baseline相同。327个TDL/CARRY/thermo/分发树单元的类型、LOC、BEL全部相同。
check_timing：no_clock=0、unconstrained_internal_endpoints=0、loops=0；原两个no_input_delay仍为sys_rst_n/pwm_in，并非新增漏约束。未关闭timing check。
6748条可布线网络全部已布线，route错误0；没有构建ERROR或Critical Warning。工具将原Explore请求按增量参考覆盖为RuntimeOptimized，实际日志保留，未把请求指令当作实际指令。

## 停止点与后续建议

依据本次任务“如果任何一步失败，停止后续依赖步骤”，没有运行新Compensated完整MAX-SDF，没有进行SDF精度/残余延迟验收，没有生成最终BIT。
已导出网表和Slow SDF仅用于下一步定位，未编译/注释，不能标注为验证通过。
最小后续方向：先审查Locate模回卷比较/选择路径及FIFO复位控制的布局、扇出和布线；保留补偿公式、位宽、5级流水与有效时序。若需改变流水结构或FIFO/复位架构，应作为新任务先分析，不在本次合并中擅自修改。

证据：results/compensated/locate_setup_top100.rpt、reset_control_setup_top50.rpt、result_fifo_incoming_setup_top50.rpt、module_all_boundary_setup.csv、negative_setup_reachability.csv、timing_summary.rpt及只读failure_audit_timing_summary.rpt。
