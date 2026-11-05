# 四相TDC核心时序优化

**本轮验收：PASS（原3512脉冲RTL功能等价 + 核心静态时序）。四条核心Setup违例全部消除，其他核心无新增负裕量。全局仍有原14条ILA2违例，未宣称全局时序收敛。**

## 修改与等价性

仅修改正式RTL `tdc_time_locate.v`、`tdc_meas_top.v`；before/after完整源码位于original/rtl和rtl，差异见RTL.diff。其他3个RTL逐字节相同，已验证四相辅助检测、TDL、CARRY4、candidate、merge及顶层接口均保持。

Locate模数为2000×2^COARSE_W=125×2^(COARSE_W+4)。将原有符号s4_sum写成h×2^L+l（0≤l<2^L），s<0等价h<0，s≥M等价h≥125，加减M只改变高部。把有符号比较和±125限制到高部并行计算，低部直接连接。当前COARSE_W=10时仅处理9位高部，低14位原样通过。
原23位有符号s4_sum/wrapped_time、21位ps输出、粗/中/细合并、补偿减法和模回卷结果不变；第1～4级及第5级输出寄存器/valid代码完全相同，未添加流水级、未改变有效周期。

FIFO只新增一个原500MHz同步器末级的等价副本，原第一级同时驱动两末级；两者同clk、同D、同异步复位，复制不增加级数或释放拍数。DONT_TOUCH阻止综合合并，副本仅用于结果FIFO写门控。
原result/error FIFO rst端口、wr_rst_busy/full/pulse_width_valid条件、读逻辑、数据格式和IP配置均保留。网表实际D/C/CLR一致及同Slice布局已核对。没有删除复位条件或关闭时序检查。

## RTL验证

- 原3512个输入脉冲、真值、事件时间及参数全部冻结，未改变样本。
- 旁路和补偿各7024边沿、3512脉宽；raw/candidate/taps/aux/timestamps/widths/FIFO/errors及六历史事件的pipeline trace均与04任务逐字节一致。
- 7024次时间戳、3512次脉宽补偿算术及valid/极性时序核对通过；结果FIFO顺序一致，错误FIFO为空。
- 原8321个Locate边界样本通过，覆盖520个相位/极性/tap组合及正负回卷。
- 168960个完整有符号回卷位模式检查通过（COARSE_W=1/8/10，所有高部取值与低部边界）；包含原合法范围之外的位模式，仍与旧单次回卷表达式逐位一致。
- FIFO复位对照检查2552周期、76个输出、3次异步assert/4次同步release，旧/新写使能、读使能、脉宽及FIFO输出序列全部一致。

这些是理想RTL功能证据，不冒充器件SDF或精度统计。原CSV、完整日志和测试平台均保留。

## 时序结果

全局WNS/TNS：-0.050/-0.257 ns → -0.050/-0.166 ns；WHS/THS维持+0.054/0.000ns。
核心Setup违例4→0，Hold违例0，原14条ILA2负路径逐项不变。

| 原核心端点 | 原裕量ns | 新最差裕量ns | 当前最差起点 |
|---|---:|---:|---|
| locate20 | -0.047 | +0.544 | u_tdc_time_locate/s4_sum_reg[16]/C |
| locate19 | -0.022 | +0.506 | u_tdc_time_locate/s4_sum_reg[16]/C |
| locate11 | -0.002 | +1.349 | u_tdc_time_locate/s4_sum_reg[11]/C |
| fifo_enable | -0.018 | +0.168 | u_fifo_tdc_result/U0/inst_fifo_gen/gconvfifo.rf/grf.rf/gntv_or_sync_fifo.gl0.wr/gwas.wsts/ram_full_i_reg/C |

旧的具体起终点组合均不再存在；此表为原终点的真实最差路径，详见TIMING_BEFORE_AFTER.md和CORE_TIMING_PATHS.csv。
辅助Setup/Hold +0.220/+0.108ns；全体核心最低Setup为Fine Layer +0.050ns。无新增时序例外，约束覆盖与TDL固定结构检查通过。
一次顶层综合/P&R完成，4个OOC IP未重新综合；没有额外实现试探。

## 冻结补偿参数

| TDL相位 | 极性 | sel_index | offset ps |
|---|---|---:|---:|
| 90° | rise | 0 | 36011 |
| 90° | fall | 0 | 36011 |
| 180° | rise | 1 | 35742 |
| 180° | fall | 1 | 35742 |
| 270° | rise | 2 | 35756 |
| 270° | fall | 2 | 35756 |
| 0° | rise | 3 | 36081 |
| 0° | fall | 3 | 36081 |

参数与04任务CSV逐字节一致，实际综合generic逐项匹配；包含旧公共流水线偏移，rise/fall仍独立选择，没有校准或改值。

## 交付、归档和限制

按本次要求未运行完整MAX-SDF、未生成SDF或BIT、未做精度对比或参数校准；这些将在后续任务中用本轮冻结DCP验证，不将本轮PASS外推为实现后功能或精度PASS。
实现DCP、未注释时序网表、XDC/IP配置、所有时序报告、源码/原始CSV/日志均在本任务目录，关键文件有SHA256清单。
上一轮未推送合并成果234个文件已逐字节保存在独立的2026-11-05-04归档，原FAIL、旧DCP/SDF及报告均保持；仅新增Git LFS属性用于归档，没有覆盖历史任务。
本轮Git分支：`codex/2026-11-05-05-tdc-core-timing-fix`，提交说明严格为`2026-11-05-05-四相TDC核心时序优化`。实际Commit ID和推送核验在执行结束报告给出，未合并main、未强推。

复现：在新空目录复制本任务scripts/sim/inputs/rtl，映射W:；Y:为04合并任务，X:为03辅助任务，U:为01时序任务。先run_rtl.py、run_unit_checks.py，均通过后复用相同IP产品并执行build_timing.tcl，最后report_results.py。已冻结交付目录禁止覆盖。
build_timing.tcl使用本任务build/registered内已生成IP产品；若独立检出后无这些缓存，应在新副本导入原XCI生成同配置OOC产品，不能直接把缺缓存报错当RTL失败。
文件清单及哈希见FILE_LIST.md、SHA256SUMS.txt。
