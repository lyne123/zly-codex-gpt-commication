# 四相 TDC 辅助边沿检测优化结果

任务：`2026-11-05-03-四相TDC辅助边沿检测优化`。基于 `45f22db51d360878c9b1121be4468fe283f0908b`，器件 `xc7k325tffg900-2`，Vivado/XSim 2022.2。

## 结论

**新 Baseline 完整 MAX-SDF 验证达到 3512/3512 正确脉宽、7024/7024 有效边沿。丢失上升沿、丢失下降沿、重复边沿、错配均为 0，FIFO 输出与测量序列一致。六个历史异常事件全部恢复。**

本次只修改正式源码 `tdc_fine_layer.v` 的辅助采样、事件归属及确认输入。四条 TDL、CARRY4、编码器、候选选择规则、locate 补偿算法、merge、FIFO/USB 及原8参数均未修改。没有新增独立辅助功能 Verilog 模块。

用户后续明确暂不考虑 2 ns 以下脉宽；新增边界验收采用高、低电平均不短于 2 ns。原始3512激励没有修改，历史六事件的1.293～1.736 ns低间隔仍完整保留并通过。小于2 ns的早期试验作为能力边界及失败记录保留，不宣称整链通过。

## 实现及归属

- `ENABLE_AUX_4PHASE=0` 保留原单相逻辑；默认1启用新通路。原单个 pwm_meta/sync/history 由四相独立采样链替代，各相使用本相同步释放的复位。meta/sync 使用 ASYNC_REG、SHREG_EXTRACT 属性。
- 优先评估了 Toggle。四个源对短间隔的捕获情况可能不同，独立 Toggle 只传递翻转、不携带原采样位置，不能直接解决多相重复和先后归属。因此采用相关时钟下固定延迟的**采样电平记录**，沿270→180→90→0传输，名义最短跨相位预算1.5 ns；没有直接OR跨域脉冲，也没有添加异步时钟组或新时序例外。
- 在0°域将记录排成90°、180°、270°、下一周期0°的连续采样序列。相邻样本的0→1/1→0只有一个位置，分别产生rise_slots/fall_slots以及辅助事件；去重依据采样位置，不使用任意3拍/6 ns合并计时窗。复位预热后先用首帧建立初值，避免初始高电平产生虚假边沿。
- 原TDL输出帧在采样帧后 LEVELS+5 拍输出；新有序事件在帧后6拍形成。因此 CARRY_NUM=16 时补 LEVELS−2=2拍，替换未经验证沿用AUX_GATE_INDEX的做法。原单相模式仍保留其索引6以便A/B。
- 每相只查询本采样位置及之前3个500 ps槽位，保留相位归属，不把辅助事件扩展成长确认脉冲。对已在前一帧使用过的同一辅助事件记录归属位，阻止其尾部TDL候选与下一真实异极性边沿混成冲突帧。原候选模块的中心值、优先级和码值均保持不变。

对应说明和证据：[RTL差异](RTL.diff)、[修改后完整RTL](rtl/tdc_fine_layer.v)、[辅助事件关联](results/AUX_EVENT_ASSOCIATION.csv)、[确认帧关联](results/CONFIRMED_EVENT_ASSOCIATION.csv)。

## 验证

| 检查 | 实际结果 |
|---|---|
| RTL局部原激励 | 160/160正确脉宽 |
| 路径应力A/B | 原单相314/320边沿，丢失指定六边沿、3错配；新四相320/320边沿、160/160正确脉宽、0错配 |
| 25.3 ns、20 MHz 5%/50%/95% | 理想模型及路径应力均通过 |
| 2 ns高脉宽、2 ns低间隔、2/2 ns序列 | 各112个相位、224个脉冲，两组模型均通过；无丢沿/重复/冲突/错配 |
| 事件归属独立核对 | 16组测试共4352个边沿，各唯一对应一个辅助事件和一个确认帧 |
| 复位释放 | PWM初始及再次复位时为高，无虚假事件 |
| 冻结3512激励RTL | 3512/3512；candidate/timestamps/widths/fifo与上一版逐字节相同 |
| 原8参数功能检查 | 前端数据逐字节相同；320个补偿时间戳、160个脉宽算术结果全部正确；未重新校准 |
| 局部MAX-SDF | 160/160；六历史事件的上升、下降及脉宽各一次；0错配 |
| 完整MAX-SDF | 3512/3512；7024边沿；rise/fall辅助事件各3512；0丢沿/重复/错配/FIFO错误 |
| 局部/完整窗口一致性 | 13类CSV全部逐字段一致，包含温度计码、无valid周期及内部采样记录 |

路径应力是明确标注的RTL测试模型：辅助路径传输延迟2771 ps、每级LUT传输延迟1300 ps；顶层输入波形不变。它用于覆盖旧单相漏采条件，不冒充器件SDF或精度数据。早期模型的惯性延迟及上电计数问题已定位，失败日志保留；最终模型逐条检查传输路径没有删除输入转换。

实现后实际输入路径偏斜374 ps，四相有效采样间隔为309/411/404/876 ps，最大876 ps。0°仍漏采三个历史短低电平；前两组由180°/270°采到，第三组由90°/180°/270°采到，证明恢复来自四相覆盖。320个局部辅助事件的极性/时序归属均核对正确，各相采样至输出延迟固定。见 [SIX_EVENT_PHASE_COVERAGE.csv](results/SIX_EVENT_PHASE_COVERAGE.csv) 和 [SDF_CAPTURE_REVIEW.json](results/SDF_CAPTURE_REVIEW.json)。这些是波形时序观察，不是重新提取8个补偿参数。

只执行一次成功的顶层综合与布局布线，导出同一设计的 BIT/DCP/网表/SDF；先局部SDF通过，再用同一快照完整运行一次3512激励。第一次IP产品准备因生成目录登记错误失败，日志保留；修正登记后完成构建。缓存未命中时工具在本任务目录生成了4个OOC IP产品，没有改IP参数。

## RMSE、Bias、STD

统计公式：RMSE=√mean(error²)，Bias=mean(error)，STD=√mean((error−Bias)²)，error=实际测得脉宽−输入真实fall/rise之差，单位ps。无异常样本删除或阈值裁剪。错误/丢失事件单列，失败批次不会把成功子集当作完整验收。

| 集合 | N | RMSE ps | Bias ps | STD ps |
|---|---:|---:|---:|---:|
| 上一版正确配对子集，完整集未通过 | 3506 | 174.661 | -0.599 | 174.660 |
| 新版完整3512 | 3512 | **161.614** | **1.647** | **161.606** |
| 新版与上一版相同3506事件 | 3506 | 161.724 | 1.640 | 161.715 |

相同3506事件集合的RMSE降低7.41%，没有异常恶化。新完整集新增的正确事件恰为2917、2918、2983、2984、3049、3050。保留逐事件原始CSV及关联残差，最小事件关联余量3310 ps。沿用冻结独立校准中的候选延迟仅用于辨认事件ID，没有修正Baseline测量值，也没有拟合验证集。

原补偿参数功能未破坏，但新物理实现后的正式补偿RMS未评价；本轮没有校准、没有生成新的补偿参数或Compensated实现。

## 时序及限制

| 项目 | 实际最差裕量 |
|---|---:|
| 新辅助相关Setup / Hold | +0.220 / +0.108 ns |
| 前端全部路径Setup | +0.050 ns |
| candidate / locate / merge Setup | +0.265 / +0.021 / +0.202 ns |
| 两个FIFO Setup | +0.099 / +0.136 ns |
| 全局WNS / TNS | -0.050 / -0.166 ns |
| 全局WHS / THS | +0.054 / 0 ns |

全局14条Setup违例仍全部位于ILA2，实际扇出不回馈TDC/FIFO；没有新增主要数字路径Setup/Hold违例，也没有无时钟或未约束内部端点。327个原TDL/分发树单元的类型、LOC、BEL与上一版一致。完整SDF活动期主要同步逻辑动态告警为0。

完整日志保留1312条辅助第一级异步采样告警、85416条TDL异步采样告警、177条ILA异步PWM采集告警、1073744条未使用MMCM CLKOUT5/6模型period告警及1条预热期reset告警；没有关闭timing checks。注释日志明确为SDF backannotation successful，使用slow/MAX、1 ps分辨率、xc7k325tffg900-2厂商模型。

两条Critical Warning如实保留：

1. 尝试的 `aux_capture_placement.xdc` 含Vivado XDC不支持的foreach，**未施加新增LOC**。实际meta/sync由ASYNC_REG自动相邻放置，并由真实STA及D/C波形验证。`effective_constraints.xdc`保存实际约束；`build_aux_used.tcl`保留运行脚本，修正后的复现脚本不再读取这个无效尝试。没有事后改变DCP/网表/SDF/比特流来掩盖警告。
2. 增量参考中的一项TDL type_pipe SRL物理优化未能重放。最终实际设计的TDL固定结构、主路径STA和两次SDF均已核验，未盲目重做实现。

仍未解决/未执行：原ILA2全局时序未收敛；上一轮Compensated locate约−0.019 ns仍待后续处理；没有硬件、其他PVT/抖动验证或新补偿校准。低于2 ns输入边界不作本轮可靠性承诺。

## 复现与文件

任务目录内提供完整修改后RTL、原始RTL、diff、testbench、刺激、原始CSV、失败记录、时序及实现产物。完整日志保存为无损gzip，压缩前SHA256和位置有清单；临时缓存、重复console及中间DCP不重复上传。4个最终实现文件通过Git LFS管理。

将本任务目录映射W:，上一轮时序优化任务映射U:，前端定位任务映射V:。工具路径为 `F:/Xilinx/Vivado/2022.2`、`F:/iverilog/bin`、Python3标准库；仓库检出后先拉取需要的LFS文件。

```powershell
# 已提供冻结RTL和刺激，可直接在新结果标签下重跑RTL，不必再次生成刺激。
& 'F:/Program Files/Python313/python.exe' W:/scripts/quick_rtl.py --mode 1 --run-tag review
```

SDF复现使用独立工作副本，仅复制scripts/sim/inputs/rtl，以及results/baseline中的design.v、design.sdf和design.dcp，保留空的gate_local/gate_full输出位置，避免覆盖本交付数据。依次运行 `run_gate.py prepare`、`compile`、`local`、`analyze_gate.py local`；局部通过后才运行 `full`及其分析。脚本拒绝覆盖已有输出。重新实现也应在独立工作副本先执行 `register_ip.tcl`，再使用修正的 `build_aux.tcl`，不要覆盖本次冻结结果。

文件和SHA256：[FILE_LIST.md](FILE_LIST.md)、[SHA256SUMS.txt](SHA256SUMS.txt)。完整原始数据与工具告警均可审查；没有把历史FAIL改写成PASS。

Windows将AUX视为保留设备名。历史RTL日志的aux.csv原件仍在本地原结果目录；Git交付使用字节完全一致的aux_trace.csv副本，详见[路径映射](inputs/ARCHIVE_PATH_MAPPING.csv)。活动测试平台已改用可移植文件名，没有更改任何CSV内容或重新运行实验来替换结果。
