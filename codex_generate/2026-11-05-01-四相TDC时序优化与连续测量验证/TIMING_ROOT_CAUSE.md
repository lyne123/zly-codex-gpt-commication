# 原始时序根因审查

版本先验核对通过：本地完整工程的五份RTL、两套BIT/DCP/SDF与上一轮Commit `fa5fd072d015dbcd03a2f7d2c895dc93bd72fca1`对应。没有用归档工程覆盖可运行工程。

两版各提取50条最差Setup路径及50条Hold路径，并执行report_design_analysis、check_timing、report_cdc、时钟交互与例外检查。Vivado 2022.2不支持本次首次尝试的redirect命令，按本地help改为check_timing自身的-file，完整重新提取；首次失败日志也保留。

## 已确认的物理瓶颈

- Baseline最差为90°计1树最终寄存器→组合范围/极性判定→0°pack90_d1，预算1.500 ns；数据1.241 ns，其中逻辑0.309、布线0.932，跨相位时钟偏斜-0.276和不确定度0.180后Slack=-0.163 ns。不是候选排序器本身。
- Compensated最差为同类路径，Slack=-0.173 ns，逻辑0.380/布线0.896 ns；还存在locate Stage2→Stage3的mid−fine−offset串联减法，最差Slack=-0.080 ns、逻辑1.252 ns。
- 两版500 MHz ILA内部计数比较/触发路径存在真实同步Setup违例，不能删除ILA或添加例外来隐去。
- candidate、merge、FIFO是否需要修改，以逐条实际路径为依据；本轮不机械增加它们的流水级。

## 最小优化方案（实施前记录）

1. 四相编码器的最终code/type/ready增加同相位寄存级，把组合范围判定从1.5 ns跨相位路径移入2 ns同相位路径；辅助门控延迟同步+1。不改PWM树、CARRY4、采样FF、码值窗口、候选规则或粗计数机制。新增公共延迟需重新校准。
2. 保留locate原5级，把每个mid−offset的常量在综合展开时计算，Stage2按index/type选择，Stage3只减fine；8参数、符号位和模回卷算法保持等价。
3. ILA先使用合理的时序驱动物理/布线策略，保留全部探针和异常检测。无新false path/multicycle，无降频。

## 约束与因果边界

原始所有内部端点均有时钟/时序约束，PWM输入和外部复位2个输入未指定板级input delay；这些是原工程已知边界，本次不伪造板级预算。四相是相关时钟，不能按异步CDC豁免；500→100 MHz使用原独立时钟FIFO与厂商约束。板级IO签核与同步数字逻辑时序分别报告。

已有物理报告只能解释Setup违例来源，不能证明20 MHz丢沿由这些违例导致。将实际运行原始/优化RTL与SDF四组对照，继续保留混合极性整帧丢弃规则。

## 逐路径审查索引

完整Startpoint/Endpoint、时钟、Required/Arrival、Logic/Net delay、Logic levels及建议见[SETUP_TOP50_REVIEW.csv](results/SETUP_TOP50_REVIEW.csv)。下面逐条列出模块、Slack与结论，原始完整时钟展开路径位于results/original_inspection。

| 版本 | 序号 | 模块 | Slack ns | 主要逻辑 | 建议 |
|---|---:|---|---:|---|---|
| baseline | 1 | tdc_fine_layer.v | -0.163 | LUT6=2 | 在编码器本相位寄存范围判定，code/type/ready和辅助门控同步增加一拍 |
| baseline | 2 | 厂商ILA IP | -0.125 | CARRY4=1 LUT2=1 SRL16E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| baseline | 3 | 厂商ILA IP | -0.044 | CARRY4=1 LUT2=1 SRL16E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| baseline | 4 | 厂商ILA IP | -0.044 | CARRY4=3 SRL16E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| baseline | 5 | tdc_fine_layer.v | -0.043 | LUT5=1 LUT6=1 | 在编码器本相位寄存范围判定，code/type/ready和辅助门控同步增加一拍 |
| baseline | 6 | 厂商ILA IP | -0.041 | CARRY4=1 LUT2=1 SRL16E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| baseline | 7 | 厂商ILA IP | -0.030 | CARRY4=1 SRL16E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| baseline | 8 | tdc_fine_layer.v | -0.027 | LUT6=2 | 在编码器本相位寄存范围判定，code/type/ready和辅助门控同步增加一拍 |
| baseline | 9 | 厂商FIFO IP | -0.024 | CARRY4=2 LUT4=1 LUT5=1 | 500MHz写指针至full标志路径，先评估物理/布线优化，不能按CDC豁免 |
| baseline | 10 | 厂商ILA IP | -0.022 | LUT2=1 LUT3=1 SRLC32E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| baseline | 11 | tdc_fine_layer.v | -0.019 | LUT6=2 | 在编码器本相位寄存范围判定，code/type/ready和辅助门控同步增加一拍 |
| baseline | 12 | 厂商FIFO IP | -0.006 | CARRY4=2 LUT4=1 LUT5=1 | 500MHz写指针至full标志路径，先评估物理/布线优化，不能按CDC豁免 |
| baseline | 13 | tdc_fine_layer.v | 0.011 | LUT2=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 14 | 厂商ILA IP | 0.011 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 15 | 厂商ILA IP | 0.033 | LUT5=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 16 | 厂商ILA IP | 0.042 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 17 | 厂商ILA IP | 0.042 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 18 | tdc_fine_layer.v | 0.052 | LUT4=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 19 | 厂商ILA IP | 0.062 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 20 | 厂商FIFO IP | 0.063 | LUT2=1 LUT4=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 21 | 厂商FIFO IP | 0.063 | LUT2=1 LUT4=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 22 | 厂商ILA IP | 0.063 | CARRY4=1 SRL16E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 23 | 厂商ILA IP | 0.065 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 24 | tdc_time_candicate.v | 0.076 | CARRY4=1 LUT4=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 25 | tdc_time_candicate.v | 0.076 | CARRY4=1 LUT4=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 26 | tdc_fine_layer.v | 0.096 | LUT5=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 27 | tdc_fine_layer.v | 0.120 | LUT4=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 28 | tdc_fine_layer.v | 0.121 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 29 | 厂商ILA IP | 0.122 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 30 | 厂商ILA IP | 0.122 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 31 | 厂商ILA IP | 0.122 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 32 | tdc_time_candicate.v | 0.124 | CARRY4=1 LUT4=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 33 | 厂商ILA IP | 0.125 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 34 | 厂商ILA IP | 0.125 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 35 | 厂商ILA IP | 0.125 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 36 | 厂商ILA IP | 0.125 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 37 | 厂商ILA IP | 0.125 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 38 | tdc_fine_layer.v | 0.131 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 39 | tdc_fine_layer.v | 0.134 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 40 | tdc_fine_layer.v | 0.135 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 41 | tdc_fine_layer.v | 0.136 | LUT4=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 42 | tdc_fine_layer.v | 0.140 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 43 | tdc_time_locate.v | 0.140 | CARRY4=3 LUT2=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 44 | tdc_time_candicate.v | 0.140 | CARRY4=1 LUT4=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 45 | 厂商ILA IP | 0.141 | LUT2=1 SRLC16E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 46 | 厂商ILA IP | 0.141 | LUT2=1 SRLC16E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 47 | tdc_fine_layer.v | 0.142 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 48 | 厂商FIFO IP | 0.145 | LUT2=1 LUT4=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 49 | 厂商FIFO IP | 0.145 | LUT2=1 LUT4=1 | 本路径没有违例；保留结构并在新实现中复核 |
| baseline | 50 | tdc_time_merge.v | 0.154 | 见完整路径报告 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 1 | tdc_fine_layer.v | -0.173 | LUT5=1 LUT6=1 | 在编码器本相位寄存范围判定，code/type/ready和辅助门控同步增加一拍 |
| compensated | 2 | 厂商ILA IP | -0.164 | CARRY4=1 LUT2=1 SRL16E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| compensated | 3 | tdc_fine_layer.v | -0.146 | LUT6=2 | 在编码器本相位寄存范围判定，code/type/ready和辅助门控同步增加一拍 |
| compensated | 4 | 厂商ILA IP | -0.131 | LUT2=1 SRLC32E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| compensated | 5 | tdc_time_locate.v | -0.080 | CARRY4=5 | 将中测常量减参数在展开时计算，Stage2选择，Stage3只做一次减法 |
| compensated | 6 | 厂商ILA IP | -0.044 | CARRY4=1 LUT2=1 SRL16E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| compensated | 7 | 厂商ILA IP | -0.044 | CARRY4=3 SRL16E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| compensated | 8 | 厂商ILA IP | -0.041 | CARRY4=1 LUT2=1 SRL16E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| compensated | 9 | 厂商ILA IP | -0.038 | LUT2=1 LUT3=1 SRLC32E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| compensated | 10 | tdc_fine_layer.v | -0.037 | LUT6=2 | 在编码器本相位寄存范围判定，code/type/ready和辅助门控同步增加一拍 |
| compensated | 11 | 厂商ILA IP | -0.030 | CARRY4=1 SRL16E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| compensated | 12 | tdc_fine_layer.v | -0.027 | LUT6=2 | 在编码器本相位寄存范围判定，code/type/ready和辅助门控同步增加一拍 |
| compensated | 13 | tdc_time_locate.v | -0.025 | CARRY4=5 | 将中测常量减参数在展开时计算，Stage2选择，Stage3只做一次减法 |
| compensated | 14 | tdc_time_locate.v | -0.025 | CARRY4=5 | 将中测常量减参数在展开时计算，Stage2选择，Stage3只做一次减法 |
| compensated | 15 | tdc_time_locate.v | -0.025 | CARRY4=4 | 将中测常量减参数在展开时计算，Stage2选择，Stage3只做一次减法 |
| compensated | 16 | 厂商FIFO IP | -0.024 | CARRY4=2 LUT4=1 LUT5=1 | 500MHz写指针至full标志路径，先评估物理/布线优化，不能按CDC豁免 |
| compensated | 17 | 厂商ILA IP | -0.017 | LUT2=1 LUT3=1 SRLC32E=1 | 保留ILA功能，优先针对实际内部路径进行物理/布线优化 |
| compensated | 18 | tdc_time_locate.v | -0.008 | CARRY4=4 | 将中测常量减参数在展开时计算，Stage2选择，Stage3只做一次减法 |
| compensated | 19 | 厂商FIFO IP | -0.006 | CARRY4=2 LUT4=1 LUT5=1 | 500MHz写指针至full标志路径，先评估物理/布线优化，不能按CDC豁免 |
| compensated | 20 | 厂商ILA IP | 0.016 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 21 | tdc_time_locate.v | 0.030 | CARRY4=4 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 22 | tdc_time_locate.v | 0.030 | CARRY4=4 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 23 | 厂商ILA IP | 0.033 | LUT5=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 24 | 厂商ILA IP | 0.050 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 25 | 厂商ILA IP | 0.050 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 26 | tdc_fine_layer.v | 0.052 | LUT4=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 27 | 厂商FIFO IP | 0.063 | LUT2=1 LUT4=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 28 | 厂商FIFO IP | 0.063 | LUT2=1 LUT4=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 29 | 厂商ILA IP | 0.063 | CARRY4=1 SRL16E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 30 | 厂商ILA IP | 0.065 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 31 | tdc_fine_layer.v | 0.065 | LUT5=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 32 | 厂商ILA IP | 0.067 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 33 | tdc_time_candicate.v | 0.076 | CARRY4=1 LUT4=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 34 | tdc_time_candicate.v | 0.076 | CARRY4=1 LUT4=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 35 | tdc_time_locate.v | 0.085 | CARRY4=4 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 36 | tdc_time_locate.v | 0.093 | CARRY4=3 LUT2=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 37 | tdc_fine_layer.v | 0.095 | 见完整路径报告 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 38 | tdc_fine_layer.v | 0.096 | LUT5=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 39 | tdc_time_locate.v | 0.101 | CARRY4=3 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 40 | tdc_time_locate.v | 0.115 | CARRY4=6 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 41 | tdc_fine_layer.v | 0.120 | LUT4=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 42 | tdc_fine_layer.v | 0.121 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 43 | tdc_time_candicate.v | 0.124 | CARRY4=1 LUT4=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 44 | tdc_time_locate.v | 0.125 | CARRY4=3 LUT2=1 LUT5=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 45 | tdc_time_locate.v | 0.130 | CARRY4=3 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 46 | tdc_fine_layer.v | 0.131 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 47 | tdc_fine_layer.v | 0.134 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 48 | tdc_fine_layer.v | 0.135 | LUT4=1 LUT6=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 49 | 厂商ILA IP | 0.135 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |
| compensated | 50 | 厂商ILA IP | 0.135 | LUT2=1 LUT3=1 SRLC32E=1 | 本路径没有违例；保留结构并在新实现中复核 |

错误FIFO的500 MHz写指针→full/full反馈标志各有两条负裕量端点，Baseline和Compensated分别-0.024/-0.006 ns；这是FIFO写时钟域内同步路径，不是可以豁免的500→100 MHz CDC。与ILA一起优先做物理优化，保留原IP与全部告警。

## 首个优化实现的实际剩余问题

前端跨相位和FIFO路径已转正，负Setup的10个端点全部属于ILA2，最差-0.141 ns。另发现ILA2 BRAM最小周期2.095 ns在500 MHz下违例-0.095 ns。DCP逐属性比较确认原实现WRITE_MODE_A=NO_CHANGE且带PWROPT_WRITE_MODE_CHANGE_A=READ_FIRST:NO_CHANGE_2，新Explore实现为READ_FIRST。官方opt_design帮助说明-bram_power_opt会把未读的TDP写端转换为NO_CHANGE；下一试验使用该语义保持优化恢复原已用模式，并继续针对ILA控制器进行物理优化。没有更改主频或手工放宽最小周期。

## 补充：ILA独立综合目标与集成时钟

本轮追加核对发现，原Baseline和新Compensated的ILA2生成文件ila_2_ooc.xdc均含`create_clock -period 10 -name clk [get_ports clk]`，即OOC综合参考为100 MHz；集成后实际时钟及STA则为500 MHz（2 ns）。这说明顶层PerfOptimized策略没有自动将既有ILA OOC检查点按2 ns重新综合，可能影响该IP的映射选择。该证据不证明它是剩余违例的唯一原因；本轮未执行修改OOC目标后的独立映射对照，因此不宣称改成2 ns即可通过。

原始生成XDC已原样保存在inputs/ILA_OOC_TIMING_EVIDENCE；没有修改厂商生成文件，也没有降低集成时钟或添加时序例外。下一轮应优先建立独立的2 ns OOC综合约束（仅用于IP综合、不能覆盖集成MMCM时钟），验证配置合法性、映射和完整post-route时序，再重新校准/验证。Compensated另有Stage5回卷/选择−0.019 ns真实数据路径需要独立处理。
