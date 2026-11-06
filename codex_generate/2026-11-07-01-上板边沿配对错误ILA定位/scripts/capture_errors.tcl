# 从硬件管理器分别捕获A/B事件；本次用户已明确接受原ILA内部Setup负裕量。
# 调用参数：BIT所在目录、cs_server地址、hw_server地址、可选新采集目录。
set task [file normalize [lindex $argv 0]]
set bit $task/ILA_DEBUG.bit
set ltx $task/ILA_DEBUG.ltx
if {![file exists $bit] || ![file exists $ltx]} {error "没有配套Debug BIT/LTX，禁止烧录或冒充已采集"}
set capture_dir [expr {[llength $argv]>3 ? [lindex $argv 3] : "$task/results/captures"}]
if {[file exists $capture_dir]} {error "采集目录已存在，禁止覆盖原始记录"}
file mkdir $capture_dir
set summary [open $capture_dir/HARDWARE_STATUS.txt w]
fconfigure $summary -encoding utf-8
puts $summary "BIT=$bit\nprogramming=volatile_FPGA_RAM; no_flash_programming\nILA_internal_setup_accepted_by_user=1"
flush $summary
set opened 0
proc debug_config_snapshot {device output} {
    catch {refresh_hw_device -update_hw_probes false $device}
    set f [open $output w]
    foreach p [lsort [list_property $device]] {
        if {[string match REGISTER.CONFIG_STATUS* $p] || [string match REGISTER.BOOT_STATUS* $p]} {
            if {![catch {get_property $p $device} value]} {puts $f "$p=$value"}
        }
    }
    close $f
}
proc debug_csv_has_event {file mask} {
    # wait_on_hw_ila超时不一定抛错，必须检查真实采样行及对应事件位。
    set f [open $file r];set lines [split [string trim [read $f]] \n];close $f
    set columns [split [string trim [lindex $lines 0]] ,]
    set idx [lsearch -glob $columns debug_control_q*]
    if {$idx<0} {error "导出文件缺少调试控制列"}
    set radix [lindex [split [string trim [lindex $lines 1]] ,] $idx]
    set rows 0;set found 0
    foreach line [lrange $lines 2 end] {
        set fields [split [string trim $line] ,]
        if {![string is integer -strict [lindex $fields 0]]} {continue}
        incr rows
        set value [lindex $fields $idx]
        if {$radix eq "HEX"} {scan $value %x value}
        if {[expr {$value & $mask}]} {set found 1}
    }
    if {$rows!=1024 || !$found} {error "未确认错误触发：真实采样行=$rows，对应事件位=$found"}
}
set whole_rc [catch {
open_hw_manager
set hw_url [expr {[llength $argv]>2 ? [lindex $argv 2] : "localhost:3121"}]
if {[llength $argv]>1} {
    connect_hw_server -url $hw_url -cs_url [lindex $argv 1]
} else {connect_hw_server -url $hw_url}
set targets [get_hw_targets -quiet -filter {NAME =~ *C3067D03ABCD*}]
if {[llength $targets]!=1} {error "当前上板使用的C306目标不唯一或不可用"}
set target [lindex $targets 0]
puts $summary "selected_target=$target\nprogram_JTAG_Hz=1000000"
set_property PARAM.FREQUENCY 1000000 $target
open_hw_target $target
set opened 1
set device [get_hw_devices -quiet -filter {PART =~ xc7k325t*}]
if {[llength $device]!=1} {error "器件不是唯一XC7K325T"}
current_hw_device $device
puts $summary "device=[get_property PART $device]\nJTAG_connected=1"
debug_config_snapshot $device $capture_dir/CONFIG_BEFORE.txt
set_property PROGRAM.FILE $bit $device
set_property PROBES.FILE $ltx $device
set_property FULL_PROBES.FILE $ltx $device
puts $summary "programming_started=1"
flush $summary
puts "AUTHORIZED_DEBUG_PROGRAM_START"
flush stdout
set program_rc [catch {program_hw_devices $device} program_reason]
debug_config_snapshot $device $capture_dir/CONFIG_AFTER.txt
if {$program_rc} {error $program_reason}
puts $summary "programming_completed=1"
flush $summary
puts "AUTHORIZED_DEBUG_PROGRAM_COMPLETE"
flush stdout
set_property PARAM.FREQUENCY 1000000 $target
after 2000
refresh_hw_device $device
set ila [get_hw_ilas -of_objects $device -filter {CELL_NAME == u_ila_edge_debug}]
if {[llength $ila]!=1} {error "找不到本次500MHz ILA"}
if {[string toupper [get_property CORE_UUID $ila]] ne "A912571AD1ED54D397583B5696DB5C21"} {error "本次Debug ILA UUID不匹配"}
set control [get_hw_probes -of_objects $ila -filter {NAME =~ *debug_control_q*}]
if {[llength $control]!=1 || [get_property WIDTH $control]!=32} {error "控制探针不匹配"}
foreach probe [get_hw_probes -of_objects $ila] {set_property DISPLAY_RADIX UNSIGNED $probe}
set_property CONTROL.DATA_DEPTH 1024 $ila
set_property CONTROL.WINDOW_COUNT 1 $ila
set_property CONTROL.TRIGGER_POSITION 768 $ila
set_property CONTROL.TRIGGER_CONDITION AND $ila
puts $summary "ILA_clock_MHz=500\ndata_depth=1024\ntrigger_position=768"
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
        debug_csv_has_event $output [expr {$event eq "A" ? 1 : 2}]
        write_hw_ila_data $capture_dir/TRIGGER_${event}.ila $data
    } reason]
    if {$rc} {catch {stop_hw_ila $ila}}
    puts $summary "trigger_$event=[expr {$rc ? {NOT_CAPTURED} : {CAPTURED}}]; reason=$reason"
    flush $summary
    puts "AUTHORIZED_DEBUG_TRIGGER_$event=[expr {$rc ? {NOT_CAPTURED} : {CAPTURED}}]"
    flush stdout
}
} whole_reason]
puts $summary "attempt_status=[expr {$whole_rc ? {FAILED} : {COMPLETED}}]\nreason=$whole_reason"
close $summary
if {$opened} {catch {close_hw_target}}
catch {close_hw_manager}
if {$whole_rc} {puts stderr "AUTHORIZED_DEBUG_HARDWARE_FAILED=$whole_reason";exit 1}
