# 从硬件管理器分别捕获A/B事件；必须先有通过时序门槛的本次BIT及LTX。
# 调用：vivado -mode batch -source capture_errors.tcl -tclargs <任务目录> <可选cs_server地址>
set task [file normalize [lindex $argv 0]]
set bit $task/ILA_DEBUG.bit
set ltx $task/ILA_DEBUG.ltx
if {![file exists $bit] || ![file exists $ltx]} {error "没有通过门槛的Debug BIT/LTX，禁止烧录或冒充已采集"}
set capture_dir $task/results/captures
file mkdir $capture_dir
open_hw_manager
if {[llength $argv]>1} {
    connect_hw_server -url localhost:3121 -cs_url [lindex $argv 1]
} else {connect_hw_server -url localhost:3121}
set targets [get_hw_targets -quiet]
if {[llength $targets]!=1} {error "JTAG目标不唯一或不可用"}
set target [lindex $targets 0]
set_property PARAM.FREQUENCY 3000000 $target
open_hw_target $target
set device [get_hw_devices -quiet -filter {PART =~ xc7k325t*}]
if {[llength $device]!=1} {error "器件不是唯一XC7K325T"}
current_hw_device $device
set_property PROGRAM.FILE $bit $device
set_property PROBES.FILE $ltx $device
set_property FULL_PROBES.FILE $ltx $device
program_hw_devices $device
set_property PARAM.FREQUENCY 1000000 $target
after 2000
refresh_hw_device $device
set ila [get_hw_ilas -of_objects $device -filter {CELL_NAME == u_ila_edge_debug}]
if {[llength $ila]!=1} {error "找不到本次500MHz ILA"}
set control [get_hw_probes -of_objects $ila -filter {NAME =~ *debug_control_q*}]
if {[llength $control]!=1 || [get_property WIDTH $control]!=32} {error "控制探针不匹配"}
foreach probe [get_hw_probes -of_objects $ila] {set_property DISPLAY_RADIX UNSIGNED $probe}
set_property CONTROL.DATA_DEPTH 1024 $ila
set_property CONTROL.WINDOW_COUNT 1 $ila
set_property CONTROL.TRIGGER_POSITION 768 $ila
set_property CONTROL.TRIGGER_CONDITION AND $ila
set summary [open $capture_dir/HARDWARE_STATUS.txt w]
puts $summary "programming=volatile_FPGA_RAM; no_flash_programming\nBIT=$bit\nILA_clock_MHz=500\ndata_depth=1024\ntrigger_position=768"
foreach event {A B} {
    # 控制位0/1直接来自原错误事件译码；不是粘滞位或计数器非零判定。
    set mask [expr {$event eq "A" ? "[string repeat X 31]1" : "[string repeat X 30]1X"}]
    set_property TRIGGER_COMPARE_VALUE "eq32'b$mask" $control
    set output $capture_dir/TRIGGER_${event}.csv
    if {[file exists $output]} {error "禁止覆盖已完成的原始捕获：$output"}
    set rc [catch {
        run_hw_ila $ila
        # Vivado的timeout单位为分钟；0.25分钟即15秒。
        wait_on_hw_ila -timeout 0.25 $ila
        set data [upload_hw_ila_data $ila]
        write_hw_ila_data -csv_file $output $data
        write_hw_ila_data $capture_dir/TRIGGER_${event}.ila $data
    } reason]
    if {$rc} {catch {stop_hw_ila $ila}}
    puts $summary "trigger_$event=[expr {$rc ? {NOT_CAPTURED} : {CAPTURED}}]; reason=$reason"
    flush $summary
}
close $summary
close_hw_target
close_hw_manager
