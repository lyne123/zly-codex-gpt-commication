# ILA信号对应表

本表对应独立Debug源码。只有本次BIT通过路由及时序门槛后，才能用于上板定位；未生成BIT时不能据此声称已捕获硬件信号。

`u_ila_edge_debug`：`clk_500m`，500 MHz，1024点。8个探针共314位；probe0参与触发，probe1～7只保存数据。所有输入先经同一个0°时钟的一拍只读影子寄存器，再经ILA四拍输入流水。观测延迟不进入正式测量通路。采集窗口2.048 μs，触发位置768，约1.536 μs历史、0.512 μs后续。

| 探针 | RTL连接 | 位宽 | 作用 |
|---|---|---:|---|
| 0 | `debug_control_q` | 32 | 原错误事件、配对状态、有效信号、FIFO溢出 |
| 1 | `debug_raw_q` | 40 | 确认门控之前的四相候选极性和原始fine code |
| 2 | `debug_aux_q` | 64 | 辅助有序采样、slot、历史、归属和匹配 |
| 3 | `debug_pipeline_q` | 40 | 确认后四相结果、最终选择、冲突/重复、timestamp有效 |
| 4 | `debug_timestamp_q` | 21 | `timestamp_ps`，ps |
| 5 | `debug_rise_ts_q` | 21 | 原FSM的`rise_timestamp_ps`，ps |
| 6 | `debug_counts_q` | 64 | `[31:0]`重复上升计数，`[63:32]`孤立下降计数 |
| 7 | `debug_cycle_q` | 32 | 500 MHz调试周期编号，按2^32回卷 |

## probe0，低位到高位

| 位 | 源信号 | 含义 |
|---|---|---|
| 0 | `debug_trigger_a` | 原`error_event_valid && error_event_code==1` |
| 1 | `debug_trigger_b` | 原`error_event_valid && error_event_code==2` |
| 2 | `error_event_valid` | 原500 MHz错误事件有效 |
| 6:3 | `error_event_code` | 1重复上升、2孤立下降、3时间越界 |
| 7 | `u_tdc_time_merge.rise_pending` | 原FSM状态：1等待下降沿、0没有待配对上升沿 |
| 8 | `u_tdc_time_merge.in_range` | 当前timestamp小于2048000 ps |
| 9 | `debug_last_edge_type` | 最近接受且in_range的边沿，1上升、0下降 |
| 10 | `debug_have_last_edge` | 位9已有合法记录 |
| 11 | `debug_last_rise_paired` | 最近接受的上升沿是否已被合法下降沿配对 |
| 12 | `timestamp_valid` | 真正送入配对模块的有效位 |
| 13 | `timestamp_edge_type` | 送入配对模块的极性 |
| 14 | `edge_valid` | candidate输出有效 |
| 15 | `polarity_conflict` | 原候选极性冲突标志 |
| 16 | `repeat_error` | 原候选非相邻同极性重复标志 |
| 17 | `pulse_width_valid` | 原500 MHz脉宽有效 |
| 18 | `result_fifo_overflow` | 原结果FIFO粘滞溢出标志，仅观测 |
| 19 | `error_fifo_overflow` | 原错误FIFO粘滞溢出标志，仅观测 |
| 20 | `rst_n_500m` | 原500 MHz同步释放复位 |
| 21 | `mmcm_locked` | MMCM锁定状态，仅状态参考，不据此分析瞬态 |
| 22 | `sync_valid` | 四相流水准备完成 |
| 23 | `u_tdc_fine_layer.frame_ready` | 确认之前的流水准备完成 |
| 31:24 | 0 | 保留 |

## probe1：四相确认前候选

源为`u_tdc_fine_layer.{pack0_d1,pack270_to90,pack180_d1,pack90_d2}`，每包`{type[1:0],code[7:0]}`。

| 相位 | 包位段 | 极性 | fine code |
|---|---|---|---|
| 90° | 9:0 | 9:8 | 7:0 |
| 180° | 19:10 | 19:18 | 17:10 |
| 270° | 29:20 | 29:28 | 27:20 |
| 0° | 39:30 | 39:38 | 37:30 |

`11`上升、`10`下降、`00`无候选。这里是TDL编码/有效范围筛选后、辅助确认前的真实候选，并非未编码的`thermo_q`。type为0时仅凭fine code不能证明真实物理边沿没有被TDL采到。

## probe2：辅助通路

以下信号均位于`u_tdc_fine_layer.g_aux_4phase`。四位位置低到高为90°、180°、270°、下一周期0°，每格名义500 ps。

| 位 | 源信号 |
|---|---|
| 3:0 | `ordered_samples`，四相`pwm_history`经过原有跨相位流水后的采样电平 |
| 4 | `previous_sample` |
| 5 | `armed` |
| 6 | `ordered_ready` |
| 10:7 | `aux_rise_slots` |
| 14:11 | `aux_fall_slots` |
| 18:15 | `rise_now` |
| 22:19 | `fall_now` |
| 26:23 | `rise_previous`，已扣除claimed的前帧上升slot |
| 30:27 | `fall_previous`，已扣除claimed的前帧下降slot |
| 34:31 | `rise_claimed_previous` |
| 38:35 | `fall_claimed_previous` |
| 42:39 | `rise_claimed_now` |
| 46:43 | `fall_claimed_now` |
| 50:47 | `aux_rise_match`，在fine_layer上一级定义 |
| 54:51 | `aux_fall_match`，在fine_layer上一级定义 |
| 63:55 | 0 |

并不存在名为`slot`的单一信号，实际对应`aux_*_slots`及有序位置。`claimed`对应上表四组实际信号。当前四相分支不使用旧单相分支的`AUX_GATE_INDEX=6`，使用`ALIGN_CYCLES=$clog2(CARRY_NUM)-2=2`及前帧归属。

## probe3：确认、筛选、时间戳有效

| 位 | 源信号 |
|---|---|
| 3:0 | `sync_edge_valid`，顺序90/180/270/0 |
| 11:4 | `sync_edge_polarity`，每相2位，顺序同上 |
| 12 | `sync_valid` |
| 14:13 | `sel_index`，0=90°、1=180°、2=270°、3=0° |
| 22:15 | `chosen_code` |
| 23 | `edge_valid` |
| 24 | `edge_type_q`，1上升、0下降 |
| 25 | `polarity_conflict` |
| 26 | `repeat_error` |
| 27 | `timestamp_valid`，实际的timestamp边沿有效信号，没有另造timestamp_edge_valid |
| 28 | `timestamp_edge_type` |
| 36:29 | `{final_type0,final_type270,final_type180,final_type90}`，辅助确认后的组合极性 |
| 37 | `frame_ready` |
| 39:38 | 0 |

`final_valid`对应`final_type!=00`；寄存后就是`sync_edge_valid`。不虚构单独的final_valid网名。

## 时钟域与顺序

- probe0～7全部由0°500 MHz影子寄存器采集。辅助slot/history/claimed、最终候选、Locate和Merge本来就在这个域。
- `pack270_to90`由90°域寄存器产生，按原设计在后续0°边沿接收，是同MMCM相关时钟的跨相位路径；新增影子接收路径必须接受STA检查，不能当作异步信号加false path。
- 原始0/90/180/270相位的`pwm_meta`、`pwm_sync`、`thermo_q`没有直接接到错误时钟域ILA。观测的是原有安全对齐后的电平记录和候选；不能把这些等同于直接捕获全部原相位寄存器。
- `u_ila3`原100 MHz五探针完全保留：valid、21位ps脉宽、错误valid、4位错误码、PWM输入。它只用于结果和粗略输入检查，不能用其10 ns采样间隔排除短毛刺，也不能与500 MHz事件逐行配对。
- probe1/2及组合final_type是本周期确认输入；`sync_edge_*`是原确认输出寄存器的上一周期结果。candidate和Locate继续各自原有流水。原Merge错误输出比产生错误的timestamp接受边沿晚一个寄存周期；看触发前一行的timestamp、pending及rise_timestamp可还原错误条件。
- 新增计数器在原错误事件有效周期累加，计数值比该事件标志的观测晚一拍。上板未验证前，不宣称这些波形已经实际取得。
