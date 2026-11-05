# 四相 TDC 前端 SDF 丢沿定位

任务：`2026-11-05-02-四相TDC前端丢沿定位`。基础提交：`d30dfeb9779f7d3c4859fbfb300bebd2d9481a7b`。

## 结论

**六个异常事件的首次丢失位置均为辅助边沿通路的 `dut.u_tdc_fine_layer.pwm_meta_reg`。** 三段不足 2 ns 的低电平完整落在该寄存器相邻两个有效采样上升沿之间，D/D_dly 确实翻转，但 Q 始终保持 1。因此上一脉冲下降沿、下一帧头上升沿都没有进入 `pwm_sync → pwm_history` 边沿检测通路。对应辅助脉冲没有产生，`AUX_GATE_INDEX=6` 的确认窗口内 match 为 0；已经正确形成、编码并跨相位传送的 TDL 候选被确认门控过滤。

这不是从最终 raw.csv 反推的猜测：本轮直接读取实际实现网表寄存器的 D、D_dly、C、C_dly、Q，以及每条 TDL 和确认寄存器的实际输入。三段短窗口与上一轮完整 Baseline SDF 的九类输出全部逐字段相同。

本轮仅定位，没有实施修复。**上一轮 3506/3512、3 次错配及整体 FAIL 结论保留；没有将验收改成 PASS。**

## 首次丢失的精确位置与时间

以下全部为原始完整实验的绝对时间，单位 ps。局部仿真时间 = 表中时间 − 225280000。

| 事件对 | 真实下降沿 / 下一上升沿 | pwm_meta.D/D_dly 低电平区间 | 两侧 C_dly 上升沿 | 区间内采样数 | Q |
|---|---|---|---|---:|---|
| 2917 F / 2918 R | 238712660 / 238713990 | [238715431, 238716761) | 238715007 / 238717007 | 0 | 保持 1 |
| 2983 F / 2984 R | 242012697 / 242013990 | [242015468, 242016761) | 242015007 / 242017007 | 0 | 保持 1 |
| 3049 F / 3050 R | 245312254 / 245313990 | [245315025, 245316761) | 245315007 / 245317007 | 0 | 保持 1 |

三个 D 低脉冲宽度分别为 **1330、1293、1736 ps**，与原输入的低电平宽度完全相同。输入边沿到实际 D 的延迟均为 **2771 ps**。D 与 D_dly 的边界在本模型中相同，C 与 C_dly 的边界也相同。

“首次异常”是这段输入低脉冲没有被 `pwm_meta_reg` 存储，而不是下游 valid 下降的时刻。到低脉冲结束的 238716761、242016761、245316761 ps，即可确定完整脉冲未经一次采样；下一次上升沿分别在 238717007、242017007、245317007 ps 再次读到 D=1、Q_before=1。下降沿没有被存储，随后的上升沿也就没有可检测的 0→1 转换。表中同时给出完整异常区间和确认时刻，避免用单一时刻掩盖采样窗口问题。

| 事件 | 有效 TDL 编码输出（phase / type / code / Q 变化时间 ps） | 跨相位后、确认前的观察 | 首次位置 |
|---:|---|---|---|
| 2917 F | 270° / 2 / 38 / 238728677；0° / 2 / 26 / 238729177 | 238732151：pack270_to90=0x226、pack0_d1=0x21a；实际 final_type 均 0 | pwm_meta_reg 漏采上述低脉冲 |
| 2918 R | 180° / 3 / 38 / 238730158 | 238734151：pack180_d1=0x326；实际 final_type180=0 | 同一低脉冲漏采，未形成 aux_rise |
| 2983 F | 270° / 2 / 42 / 242028677；0° / 2 / 30 / 242029177 | 242032151：pack270_to90=0x22a、pack0_d1=0x21e；实际 final_type 均 0 | pwm_meta_reg 漏采上述低脉冲 |
| 2984 R | 180° / 3 / 38 / 242030158 | 242034151：pack180_d1=0x326；实际 final_type180=0 | 同一低脉冲漏采，未形成 aux_rise |
| 3049 F | 180° / 2 / 46 / 245328158；270° / 2 / 10 / 245328677 | 245332151：pack180_d1=0x22e、pack270_to90=0x20a；实际 final_type 均 0 | pwm_meta_reg 漏采上述低脉冲 |
| 3050 R | 180° / 3 / 38 / 245330158 | 245334151：pack180_d1=0x326；实际 final_type180=0 | 同一低脉冲漏采，未形成 aux_rise |

这些确认前观察点的 frame_ready=1、同极性 aux_match=0。pack 格式为 `{type[1:0],code[7:0]}`，type=2 表示下降、3 表示上升。

证据：[逐事件诊断](EVENT_DIAGNOSIS.csv)、[完整窗口采样](EVENT_TRACE.csv)、[实际辅助采样](results/short_baseline/aux_capture.csv)、[精确变化时间](results/short_baseline/signal_changes.csv)、[辅助采样摘要](results/AUX_SAMPLING_EVIDENCE.csv)、[TDL 编码证据](results/TDL_CANDIDATE_EVIDENCE.csv)、[确认门控证据](results/CONFIRM_GATE_EVIDENCE.csv)。

## A–I 逐级判断

| 检查 | 本轮已观测结论 |
|---|---|
| A：TDL 是否采到边沿 | 六个事件全部存在有效 TDL 候选，共 9 个；每个下降沿有 2 相，每个上升沿有 1 相。 |
| B：温度计码 | 对应 9 个样本已保存完整 64 bit；计 1 数与 code_q 相同。部分热码含泡泡或短脉冲中间状态，不能称为所有相均有理想单调热码。 |
| C：detected_type | 对应采样在极性流水线第一物理存储单元 D 端观测到预期 2 或 3，未在此处丢失有效候选。组合瞬态也原样保留，不能把瞬态变化误当作已采到的输出。 |
| D：code_raw 范围 | 9 个有效候选的 raw_type、code_raw、encoder_ready 在输出寄存器采样前均正确；按实际外层 MAX_VALID_TAP=60、MIN_VALID_TAP=5 重建的范围判定为 1。 |
| E：edge_type_q | 九个候选均正确输出，output_ready=1；见精确 Q 变化时间表。 |
| F：辅助检测 | 对六个目标事件未检测到相应边沿。pwm_meta 没有捕获低电平，pwm_sync/history 也没有该低电平，未产生本事件的 aux_fall/aux_rise。 |
| G：match 是否覆盖 | 对应候选到达确认输入时，bit5/bit6 同极性或值为 0。 |
| H：confirm_edge | 实际确认寄存器 D 输入为 0。逻辑按其“必须有辅助确认”的规则运行，却因此过滤了真实 TDL 候选；首因在更早的辅助漏采。 |
| I：跨相位错位 | 九个候选的 type/code 在包内保持配对，跨相位后仍与编码输出一致，没有发现这六个事件由传包错位造成。 |

`code_raw/raw_edge_type` 与 `code_q/edge_type_q` 属于不同流水拍，不能直接用 EVENT_TRACE 同一行的范围判定去否定当前 Q。TDL_CANDIDATE_EVIDENCE 明确分开编码输入观察时间、Q 变化时间和输出观察时间，并核验对应热码计数。

**TDL 采样窗口的影响：**并非每相都能采到每个边沿。例如 3049 的 0°分支出现 code=1 的无效候选，其他相也可能只见稳定全 0/全 1 或短脉冲中间码。但 3049 仍有 180°/270°两个合法下降沿候选，其余五事件也都有合法候选。因此个别相的采样窗口/范围淘汰不是这六个整事件完全丢失的首因。没有重设 TDL 或范围参数。

## 新增 2 ns 流水线与 AUX_GATE_INDEX=6

新增输出级已经输出正确 type/code，四相传输也保留了这些候选；首次丢失发生在其上游辅助输入同步器。故**这六个事件不是由新增一级流水线或索引错一拍首先造成**。

`aux_rise_match = rise_pipe[6] | rise_pipe[5]`，下降沿同理。目标事件的辅助脉冲根本没有产生，移动索引不能恢复不存在的脉冲。

注意目标候选附近确实还存在**下一脉冲下降沿**的辅助脉冲。以第一组为例，2918 的正常下降沿 238716490 ps 经 D=0@238719261、meta.Q=0@238721172，产生 aux_fall=1@238723856；其 match 从 238735174 到 238739157 ps 为 1。这是之后的真实下降沿，不是 2917 的补迟脉冲。2917 候选观察时 fall_pipe=8（bit3），2918 上升候选观察时 fall_pipe=16（bit4），bit5/6 尚无确认。扩大或前移窗口可能把相邻事件的辅助脉冲错误归给前一事件，不能作为本轮的修复结论。

本轮确认的是这六个事件的因果链，不宣称 AUX_GATE_INDEX=6 在全部输入频率、占空比、PVT 条件下已得到普遍证明。

## 短窗口等价性及运行边界

仅运行 **1 次优化后 Baseline SDF**，160 个原始脉冲，仿真到本地 20732212 ps；没有运行四版本完整测试。四相时钟、复位释放 200000 ps、PWM 初始低电平和激励边沿顺序保持原测试平台定义。

平移量 225280000 ps = 22 × 10240000 ps，也是 10000 ps 系统时钟、2000 ps 四相周期及 2048000 ps 粗计数模周期的整数倍。首个局部上升沿为 12235453 ps；距第一个目标下降沿有 1197207 ps 的原始前缀边沿，并已完成时钟、复位及流水线预热。

在原绝对时间的 [238600000,238900000]、[241900000,242200000]、[245200000,245500000] 三个窗口，比较所有行、所有字段，不使用数值容差：

| 数据 | 原完整 / 本轮窗口行数 | 结果 |
|---|---:|---|
| raw / candidate / timestamps | 各 30 / 30 | 完全相同 |
| widths / fifo | 各 15 / 15 | 完全相同 |
| errors / error_fifo | 各 0 / 0 | 完全相同 |
| sampled_taps | 59 / 59 | 完全相同，含 thermo/carry |
| anomaly_pipeline_trace | 450 / 450 | 全部字段相同，含无 valid 周期 |

详见 [SHORT_WINDOW_EQUIVALENCE.json](results/SHORT_WINDOW_EQUIVALENCE.json)。这是对应窗口的输出等价性验证，不是恢复原完整实验所有历史内部状态的形式化证明。

## 实际网表观察映射

完整 81 个观察点见 [SIGNAL_MAPPING.json](inputs/SIGNAL_MAPPING.json) 和 [frontend_observer.svh](sim/frontend_observer.svh)。只读 testbench 引用，没有修改网表、正式 RTL 或物理属性。

- 四个 u_tdl 的 thermo_q/carry_tap 保留；code_raw 对应 code_q.D 的实际驱动网；code_q/edge_type_q 读物理寄存器 Q，另读 edge_type_q.D。
- detected_type 某些位被合并：读取极性流水线第一 SRL/phys_opt 拆分 FF 的实际 D 端。它含实际布线延迟，不冒充已不存在的原始全总线。
- encoder_ready 读取 output_ready_reg.D，output_ready 读取其 Q。
- code_in_range 独立节点被 LUT 合并，按实际 60/5 参数重建并明确标记；同时记录实际 edge_type_q.D/Q。
- aux_pipe[0:3] 读取 SRL16E 模型内部 data，[4:6] 读取实际 FF.Q；未使用的 bit7 已优化，不伪造物理波形。
- match 或表达式被融合到确认 LUT，观察中标记为重建表达式；final_type 读取 sync_edge_polarity 寄存器实际 D 输入，包含 frame_ready 门控和物理延迟。
- pack 四组读取实际寄存器 Q；恒 0 的 code bit7 明确补常数。sync_valid、sync_edge_valid/polarity 读取网表实际输出。

## 时序审查

使用 Vivado XSim 2022.2、`xc7k325tffg900-2` 对应 `simprims_ver` 器件模型。复用的 SDF 由上一轮 `export_evidence.tcl` 的 `write_sdf -process_corner slow` 生成；本轮选择 MAXIMUM/`--maxdelay`，1 ps 分辨率，保留全部 timing checks、transport 内部延迟和原有 pulse 选项。工具日志明确报告 SDF backannotation successful；这不等于凭空给出逐路径 100% 注释率。

三个目标窗口的告警为：TDL 异步采样 378 条、ILA 异步 PWM 调试采集 2 条、MMCM 未使用 CLKOUT5/6 模型 period 3600 条；**未发现目标窗口内主要同步 TDC 数字数据路径的动态时序告警**。原文完整保留于 [simulation.log.gz](logs/simulation.log.gz)，非 MMCM 目标窗口警告另见 [key_timing_warnings.log](logs/key_timing_warnings.log)。

全局还有 2 条 ready_pipe_reg[5] setuphold，发生在本地 684645、685645 ps 的复位/预热期，远早于 12235453 ps 首个输入；5 µs 后该类告警为 0。另有辅助异步同步器 setuphold 10 条，均在这三个目标窗口之外；没有隐藏或禁用。

沿用上一轮冻结的 STA 证据，本轮未重新运行 STA：

| 版本 | WNS ns | TNS ns | WHS ns | THS ns | 已知限制 |
|---|---:|---:|---:|---:|---|
| Baseline | -0.050 | -0.166 | 0.054 | 0.000 | 14 个失败端点均为 ILA2；上一轮已核查其不回馈 TDC/FIFO |
| Compensated | -0.050 | -0.185 | 0.054 | 0.000 | 除 ILA2 外，locate 主路径 -0.019 ns |

Compensated 的确存在真实主要同步逻辑 Setup 违例：`u_tdc_time_locate/s4_sum_reg[11]/C → timestamp_ps_reg[10]/D`，数据延迟 1.971 ns（逻辑 0.665、布线 1.306），周期 2.000 ns，slack -0.019 ns。见 [路径摘录](logs/COMPENSATED_LOCATE_SETUP_PATH.rpt) 与 [模块表](inputs/COMPENSATED_MODULE_WORST_SETUP.csv)。它位于前端之后、只属 Compensated，本次 Baseline 复现已足以证明六事件的辅助漏采首因；没有把该 STA 问题伪称已修复，也没有以动态仿真未报错否定它。

## 已确认、未确认及最小修复建议

已确认：六事件均有合法 TDL 候选；辅助 D 低脉冲漏采；没有对应辅助边沿；确认输入将候选清零；跨相位包仍正确；局部与完整 SDF 对应窗口完全一致；正式源码和冻结输入哈希未变。

仍未确认：修改辅助通路后的最小可行实现及其全部边界行为；其他 PVT/抖动下的采样概率；真实硬件亚稳态和仪器观测结果；全输入域的确认索引充分性。本轮没有修复后仿真、重新实现或硬件验证，因此不作这些结论。原波形包含的组合毛刺及 TDL 异步告警均未额外处理。

建议下一轮把修复范围首先限定在**辅助边沿捕获能力及确认条件的设计前提**：单相 2 ns 电平采样不能保证捕获任意相位的 <2 ns 低电平。先制定在现有四相可分辨边沿条件下可验证的辅助捕获方式（例如复用多相边沿信息、或经严格 CDC 验证的边沿保持机制），再检查其与现有包的延迟对齐。无需先改候选选择算法或重设计 TDL。不要只平移 AUX_GATE_INDEX、扩大确认窗口、改校准参数或改激励来宣称修复。这些建议尚未实现，新增硬件必须另行评估资源、CDC、复位和 STA。

## 复现

依赖上一轮任务目录中的原始 `results/optimized/baseline/design.v`、`design.sdf`、`sim/tb_tdc.sv`、`sim/stimuli/validation*`、`inputs/xsim.ini` 及完整 gate_validation CSV。Git 检出时需用 Git LFS 拉取对应冻结文件，不能把 LFS 指针当网表/SDF。其来源 SHA256 记录在 [SOURCE_SHA256.json](inputs/SOURCE_SHA256.json)。

在保留本次证据的独立目录副本内复现；V: 必须为空闲盘符，或已经映射到该副本。Vivado 默认安装路径为 `F:/Xilinx/Vivado/2022.2`，Python 使用标准库。按本机实际路径调整脚本工具路径即可，不需要改 RTL。

```powershell
subst V: "D:\00-code\FPGA_Prj\fpga_tdc_v3_cal\codex_generate\2026-11-05-02-四相TDC前端丢沿定位"
$env:PYTHONIOENCODING = 'utf-8'
& 'F:/Program Files/Python313/python.exe' V:/scripts/run_probe.py
```

run_probe 在发现已有 simulation.log、raw.csv 或 EVENT_DIAGNOSIS.csv 时拒绝覆盖；重新运行应使用只含 scripts、sim、inputs 的独立副本且该副本尚无仿真输出，并保持上一轮目录可访问。步骤为 prepare → xvlog → xelab → xsim → 严格窗口比较 → 告警审计 → 逐事件证据断言。只编译仿真，不调用综合、布局布线或 BIT 生成。

## 归档范围与完整性

本目录只归档新增代码、局部原始测量 CSV、观察日志、诊断及必要来源记录。大型原网表/SDF/DCP/BIT 不重复上传，仍在基础提交的上一轮任务目录，来源与大小在 SOURCE_SHA256 中明确列出。新快照及网表/SDF的本地编译副本位于本任务 build，不纳入 Git。

原始 20 MB 仿真日志本地保留在 `results/short_baseline/simulation.log`；Git 中保存逐字节可还原的 gzip 副本，未丢弃失败/告警行。原始 CSV 均保留，EVENT_TRACE 仅在观察采样副本前增加事件对编号；绝对时间平移及原始局部时间均明示。重要文件 SHA256 和完整文件清单随交付提供。

没有修改正式 RTL、网表、SDF、激励边沿形状、补偿参数、FIFO、时序约束或历史数据；没有重新综合、实现、生成 BIT 或关闭 timing checks。独立分支归档，不合并 main。
