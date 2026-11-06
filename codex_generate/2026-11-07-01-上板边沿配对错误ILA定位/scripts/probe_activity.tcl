# 只连接已烧录的本次Debug版本；普通活动快照不冒充A/B错误触发。
set work [file dirname [file normalize [info script]]]
set attempt [expr {[llength $argv]>0 ? [lindex $argv 0] : "hardware_debug_activity_01"}]
set out $work/$attempt
if {[file exists $out]} {error "禁止覆盖已有活动快照"}
file mkdir $out
set f [open $out/STATUS.txt w]
set opened 0
set rc [catch {
    open_hw_manager
    connect_hw_server -url localhost:3122 -cs_url TCP:127.0.0.1:3048
    set target [get_hw_targets -filter {NAME =~ *C3067D03ABCD*}]
    if {[llength $target]!=1} {error "C306目标不唯一"}
    set_property PARAM.FREQUENCY 1000000 $target
    open_hw_target $target
    set opened 1
    set device [get_hw_devices -filter {PART =~ xc7k325t*}]
    if {[llength $device]!=1} {error "XC7K325T不唯一"}
    current_hw_device $device
    set_property PROBES.FILE $work/authorized_debug_01/ILA_DEBUG.ltx $device
    set_property FULL_PROBES.FILE $work/authorized_debug_01/ILA_DEBUG.ltx $device
    refresh_hw_device $device
    foreach {instance depth} {u_ila3 2048 u_ila_edge_debug 1024} {
        set ila [get_hw_ilas -of_objects $device -filter "CELL_NAME == $instance"]
        if {[llength $ila]!=1} {error "未找到$instance"}
        puts $f "$instance UUID=[get_property CORE_UUID $ila]"
        foreach probe [get_hw_probes -of_objects $ila] {set_property DISPLAY_RADIX UNSIGNED $probe}
        set_property CONTROL.DATA_DEPTH $depth $ila
        set_property CONTROL.WINDOW_COUNT 1 $ila
        set_property CONTROL.TRIGGER_POSITION 0 $ila
        run_hw_ila -trigger_now $ila
        wait_on_hw_ila -timeout 0.1 $ila
        set data [upload_hw_ila_data $ila]
        set csv $out/${instance}_ACTIVITY.csv
        write_hw_ila_data -csv_file $csv $data
        write_hw_ila_data $out/${instance}_ACTIVITY.ila $data
        set stream [open $csv r];set lines [split [string trim [read $stream]] \n];close $stream
        set rows 0
        foreach line [lrange $lines 2 end] {if {[string is integer -strict [lindex [split [string trim $line] ,] 0]]} {incr rows}}
        puts $f "$instance sample_rows=$rows expected=$depth trigger_kind=IMMEDIATE_ACTIVITY_ONLY"
        puts "ACTIVITY $instance rows=$rows expected=$depth"
        flush stdout
        flush $f
    }
} reason]
puts $f "attempt_status=[expr {$rc ? {FAILED} : {COMPLETED}}]\nreason=$reason"
close $f
if {$opened} {catch {close_hw_target}}
catch {close_hw_manager}
if {$rc} {puts stderr $reason;exit 1}
