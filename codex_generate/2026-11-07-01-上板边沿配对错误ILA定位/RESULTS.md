# 上板边沿配对错误ILA定位

本轮最新状态：**DEBUG_PROGRAMMED_A_CAPTURED_B_UNOBSERVED**。上一轮Debug结果的BIT已导出：**是**；上板配置完成：**是**。具体硬件记录见`results/hardware_debug_05/HARDWARE_STATUS.txt`。

## 用户后续明确指令

用户明确要求“上次时序没通过是ila的原因就不用管了”“就是要烧录上一轮结果的bit”。因此从原冻结Debug路由DCP直接导出BIT/LTX，没有重新综合、布局布线、修改RTL或补偿参数。原来因时序门槛未导出BIT的记录保留在logs，未将原违例改写成时序收敛。

## 来源

源Commit：`ba978229094a8621b30770177727d8e70b831a74`，Git归档基点`31090be88d0fef94835f69a6edcff4e447328220`。实际生产来源为AD23版，顶层`tdc_meas_top`、器件`xc7k325tffg900-2`。原正式5个RTL及生产BIT再次核对SHA256未变。

- 冻结Debug DCP SHA256：`017bd5bd1e4ffdeb9a3dc839ae07a9b1184c8ed03d56c84a0493143298e3fb60`。
- 本轮`ILA_DEBUG.bit` SHA256：`4df6b364eda1511abf910637ad8edb64bc518cb092de91f53e7a567736ed58e7`，大小11443721字节。
- 配套`ILA_DEBUG.ltx` SHA256：`e95afcf627bc5e35036402b97c81c801b06fbff54386aebb817025b5611d3acc`。
- Debug ILA UUID：`A912571AD1ED54D397583B5696DB5C21`；原100MHz ILA UUID仍为`005AAA8F6BEB5365914C104C10152EC8`。

## 逻辑和时序

正式测量算法修改：**否**。独立Debug副本仅导出已有候选/辅助/配对状态，增加影子寄存器、只读状态记录、两个32位错误计数器和ILA；candidate/Locate、TDL结构、辅助判断规则、FIFO格式、五级Locate、valid时序全部保持。

8个固定补偿参数ps保持：0° rise/fall=36081，90°=36011，180°=35742，270°=35756。ENABLE_SKEW_COMP=1。未重新校准。

原3512脉冲单次Debug理想RTL验证3512/3512，10类CSV逐字节一致；另有12017周期配对/触发检查，覆盖2097次A和2281次B事件。见results/FULL_RTL_EQUIVALENCE.json、RTL_VALIDATION.json。

生产全局WNS/TNS=-0.050/-0.166ns；Debug=-0.164/-0.653ns，WHS/THS=+0.054/0ns。核心和影子采集没有负裕量，7条ILA内部Setup路径按本轮用户要求接受。未关闭timing check、未添加false path、未重新实现。详细路径见TIMING_BEFORE_AFTER.md和results/authorized_debug_export/ACCEPTED_TIMING_EXCEPTIONS.csv。

## 探针和触发

`u_ila_edge_debug`使用0°500MHz，8个探针314位，1024深度、768触发位置、四拍ILA输入流水。包含确认前四相type/code、辅助ordered_samples/slots/match/claimed、确认结果、最终选择、timestamp、原rise_pending状态、最近配对记录和错误计数。所有影子寄存器只读，不反馈测量。

Trigger A=`error_event_valid && error_event_code==1`，probe0位0；Trigger B=`error_event_valid && error_event_code==2`，probe0位1。原100MHz `u_ila3`五探针保留，不用它近似替代500MHz瞬态。操作及精确位图见ILA_SIGNAL_MAP.md、TRIGGER_CONDITIONS.md。

硬件A/B结果：`{"A": {"saved": true, "capture_attempt": "hardware_debug_04", "event_flag_observed": true, "sample_count": 1024, "sha256": "0bfb3038261c9d01d31253d1e445fad8d22bfd88caa34449da21e78b0dce3bca", "confirmed_capture": true}, "B": {"saved": true, "capture_attempt": "hardware_debug_05", "event_flag_observed": false, "sample_count": 0, "sha256": "b75c3e8a9e109f485cbb863ce0564162b2656df8ec3b0b475364a91865520c74", "confirmed_capture": false}}`。只在原始CSV存在并观测到对应事件标志时确认捕获；不以超时或trigger_now冒充错误触发。

历史首轮hardware_debug_02的A/B均为0采样行，旧脚本误标CAPTURED的原日志保留，核验JSON未将其计为捕获；旧普通快照的内存不足日志也保留。修正脚本后，hardware_debug_03重新烧录成功。普通快照02确认当时输入恒低；用户随后开启10MHz/50%输出，hardware_debug_04复用已有配置、不重烧，真实捕获A。hardware_debug_05仅对B再独立等待45秒，未捕获。全部尝试见results/ALL_TRIGGER_ATTEMPTS.json。

最新普通活动快照：`results/hardware_debug_activity_03/ACTIVITY_SUMMARY.json`，内容为`{"capture_kind": "IMMEDIATE_ACTIVITY_ONLY_NOT_ERROR_TRIGGER", "ILA100M": {"sample_count": 2048, "clock_domain_MHz": 100, "input_transitions": 409, "input_high_fraction": 0.50048828125, "input_rises": 204, "rise_period_clock_histogram": {"10": 203}, "valid_width_outputs": 205, "error_events": {}, "mean_width_ps": 50541.92195121951, "min_width_ps": 50410, "max_width_ps": 50586}, "ILA500M": {"sample_count": 1024, "clock_domain_MHz": 500, "reset_released_samples": 1024, "mmcm_locked_samples": 1024, "pipeline_ready_samples": 1024, "timestamp_rises": 21, "timestamp_falls": 20, "duplicate_rise_pulses": 0, "orphan_fall_pulses": 0, "A_counter_first_last": [133139, 133139], "B_counter_first_last": [0, 0], "cycle_increment_histogram": {"1": 1023}}}`。普通快照不当作错误触发，也不当作10000次正式精度验收。

## 已捕获A的丢失位置

见[逐拍定位报告](results/capture_analysis/CAPTURE_ANALYSIS.md)、EVENT_TRACE_A.csv和KEY_WINDOW_A.csv。样本731的0°TDL已输出下降候选、code=13，辅助下降事件已进入fall_previous=1000；aux_fall_match[3]=0使final_type0=00。claimed为0，后续candidate/Locate没有收到该下降有效位。样本767的新上升timestamp到来时pending仍为1，768报A，计数42801→42802。

本次1024样本的4096次confirm判定、1023次有效位跨拍传输与真实RTL一致。结论仅针对已捕获A；270°为何type=00、上游偏移来自何处、B的原因仍不确定，没有修改正式逻辑修复。

## 限制和保留记录

确认前pack是编码/范围筛选后的TDL候选，不是thermo_q；辅助ordered_samples是原有跨相位流水之后的真实电平记录，不是原相位第一层寄存器。仅凭这些ILA不能排除输入模拟毛刺。没有找到根因前不声称修复。

前期生产版重试遇到数据服务/目标占用及一次End of startup status LOW；相关失败日志和目录单独保留。用户澄清后不再用生产BIT替代，Debug硬件尝试只使用本轮4df6开头的BIT。用户重插C306 JTAG USB后执行新的硬件尝试；未自动烧写Flash。

## 文件和复现

生产来源与RTL副本在inputs，独立Debug源码在rtl，差异见RTL.diff；只读导出脚本为scripts/export_authorized_debug_bit.tcl，硬件脚本为scripts/capture_errors.tcl。真实ASCII运行目录：`D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/codex_generate/.vivado_work/tdc_edge_20261107_01`，没有创建虚拟盘符。

保留原失败构建日志、正式参数及约束、前后时序报告、DCP、BIT/LTX、真实采集CSV/ILA（若有）。不大量上传IP缓存和重复仿真输出，3512对照的逐文件SHA证据已归档。文件清单见FILE_LIST.txt，重要文件SHA见SHA256SUMS.txt。

Git分支：`codex/2026-11-07-01-edge-pairing-ila-debug`，提交说明：`2026-11-07-01-上板边沿配对错误ILA定位`。后续实际Commit及推送核验在本地GIT_DELIVERY.json和执行反馈中记录。未合并main、未强推。
