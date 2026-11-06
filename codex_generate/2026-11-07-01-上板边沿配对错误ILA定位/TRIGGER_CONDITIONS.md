# 两个独立错误触发条件

正式错误判断未复制、未修改。调试触发直接译码原500 MHz注册错误事件，计数器也使用同一译码脉冲。

```verilog
debug_trigger_a = error_event_valid && (error_event_code == 4'd1);
debug_trigger_b = error_event_valid && (error_event_code == 4'd2);
```

原Merge在接受timestamp的时钟边沿按以下顺序判断：

1. `timestamp_valid && !in_range`：时间越界，清除pending。
2. `timestamp_valid && in_range && timestamp_edge_type && rise_pending`：重复上升，发code1，同时用新上升时间戳覆盖旧值，pending保持1。
3. `timestamp_valid && in_range && !timestamp_edge_type && !rise_pending`：孤立下降，发code2，不产生脉宽。
4. 有pending的合法下降沿：计算脉宽并清pending。

`in_range=(timestamp_ps<2048000)`，`rise_pending`就是原一位配对FSM，1等待下降沿，0空闲。这里列出原逻辑用于审查，没有将其复制到测量反馈。错误valid在每个普通周期默认清0；连续相邻错误可以连续为1，但每个高电平周期代表独立事件，不是粘滞错误。

新增32位计数器按2^32自然回卷，复位清0。最近接受的边沿类型和最近上升是否已配对仅作为调试记录，不反馈FSM。

## Vivado操作

只使用与本次`ILA_DEBUG.bit`配套的`ILA_DEBUG.ltx`，选择`u_ila_edge_debug`（500 MHz），不是`u_ila3`。设置1024深度、单窗口、trigger position=768、ALWAYS采样。

- Trigger A：probe0 `debug_control_q[0]==1`，32位比较值为`eq32'bXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX1`。
- Trigger B：probe0 `debug_control_q[1]==1`，32位比较值为`eq32'bXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX1X`。

两次分别arm，分别导出原始CSV及ILA文件；不把两种触发同时AND。只保留每种触发arm后首次满足条件的一份波形即可。计数器非零和FIFO溢出粘滞位都不是这两个触发条件。

`scripts/capture_errors.tcl`在本次BIT存在时可由批处理连接硬件、烧录易失配置并先后捕获A/B；不控制信号发生器、不烧Flash、不覆盖已有CSV。超时应报告NOT_CAPTURED，不能用trigger_now代替真实错误触发。

采集脚本尚未上板执行。每种触发等待15秒；Vivado的`-timeout`参数单位是分钟，因此代码使用0.25。二进制ILA导出采用默认文件格式，CSV使用`-csv_file`，命令语法按[AMD Vivado 2022.2命令参考](https://docs.amd.com/r/2022.2-English/ug835-vivado-tcl-commands/write_hw_ila_data)核对。

逐拍功能检查见`results/RTL_VALIDATION.json`：原Merge与调试副本输出比较、原条件和事件译码对应关系、计数器及影子总线检查。它不代替上板触发验收。

## 如何判读

从触发前一行的timestamp接受条件向前追踪：确认前包是否有下降候选→aux_fall_slots是否产生→fall_now/previous是否覆盖→claimed是否扣除→aux_fall_match是否有效→final_type是否保留→sync_edge_valid/polarity→candidate edge_valid/type/conflict/repeat→timestamp_valid/type→原rise_pending。

只有最早出现不一致的一级才可作为定位证据。确认前候选为空时仍可能是编码/范围筛选，不能仅凭这组ILA认定TDL物理上没有采到边沿；输入毛刺需要输入端模拟波形配合判断。
