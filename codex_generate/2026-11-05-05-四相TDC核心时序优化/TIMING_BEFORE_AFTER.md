# 核心时序优化前后

器件XC7K325T-FFG900-2，Vivado2022.2，500MHz；原有效时钟/IO/TDL/IP约束保持，未增加false path、multicycle或更改频率。

| 全局指标 | 合并版（04任务） | 本次（05任务） |
|---|---:|---:|
| WNS ns | -0.050 | -0.050 |
| TNS ns | -0.257 | -0.166 |
| WHS ns | 0.054 | 0.054 |
| THS ns | 0.000 | 0.000 |
| Setup失败端点 | 18（核心4+ILA2 14） | 14（核心0+ILA2 14） |
| Hold失败端点 | 0 | 0 |

## 原四个核心违例端点

| 端点简称 | 原裕量ns | 新端点最差裕量ns | 新最差起点 |
|---|---:|---:|---|
| locate20 | -0.047 | +0.544 | u_tdc_time_locate/s4_sum_reg[16]/C |
| locate19 | -0.022 | +0.506 | u_tdc_time_locate/s4_sum_reg[16]/C |
| locate11 | -0.002 | +1.349 | u_tdc_time_locate/s4_sum_reg[11]/C |
| fifo_enable | -0.018 | +0.168 | u_fifo_tdc_result/U0/inst_fifo_gen/gconvfifo.rf/grf.rf/gntv_or_sync_fifo.gl0.wr/gwas.wsts/ram_full_i_reg/C |

四条原起点到原终点的组合路径均已移除，不能把不存在的原路径标成正裕量。上表重新查询各原终点的全部真实路径，给出最差值；完整名称和原路径是否存在记录于CORE_TIMING_PATHS.csv。

Locate原低位→高位宽比较/选择路径不再存在。bit20最差路径由5级（LUT2+3CARRY4+LUT5）变为3级LUT（LUT4+2LUT6），数据路径延迟从1.971降为1.381ns（逻辑0.771→0.388、布线1.200→0.993）。原wrapped_time2的21负载宽控制网络不再保留；低14位网表逐位核对为s4_sum Q直达timestamp D。

FIFO同拍复位副本的输出最差Setup为+0.173ns，输入Setup为+1.329ns。原末级与副本均为FDCE，实际D/C/CLR网络相同，位于SLICE_X21Y13的B5FF/BFF，原FIFO rst端口未改。
结果FIFO ENARDEN目前最差来自IP内部ram_full_i，而非原共享复位网络；没有省略其他驱动控制路径。
reset_replica_structure.csv的Q_endpoint_loads为跨组合逻辑的终端数量（原共享471、副本38），不是直接物理扇出，未混用两种口径。

## 模块边界最差裕量

| 模块（同时检查from/to，包含跨模块输入） | 最差Setup ns |
|---|---:|
| u_tdc_fine_layer | +0.050 |
| u_tdc_time_candicate | +0.265 |
| u_tdc_time_locate | +0.166 |
| u_tdc_time_merge | +0.166 |
| u_fifo_tdc_result | +0.099 |
| u_fifo_tdc_error | +0.132 |
| u_ila2 | -0.050 |

这里Locate的+0.166ns包含Locate输出到Merge使能的路径，不应误称为Locate内部回卷路径。全体核心最小裕量仍为Fine Layer +0.050ns。
四相辅助Setup/Hold为+0.220/+0.108ns，327个固定TDL/分发单元的类型/LOC/BEL完全一致。
原14条ILA2负路径的起点、终点、裕量与04任务逐项相同，实际扇出不回馈TDC/FIFO；本轮未针对ILA进行新优化。
无no_clock、unconstrained_internal_endpoints或loops；原两个no_input_delay保持不变。FIFO bus-skew报告最差裕量+1.343ns。

仅执行一次顶层综合、一次布局布线，4个原OOC IP产品均up-to-date直接复用。沿用原增量流程，Vivado实际将Explore路由请求覆盖为RuntimeOptimized，日志如实保留。没有重复综合或生成BIT；本轮没有运行SDF，不能据此宣称SDF功能/精度通过。
