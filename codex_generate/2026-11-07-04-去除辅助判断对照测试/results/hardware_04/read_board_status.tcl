# 下载启动失败后只读配置状态，不重配、不访问Flash。
source -encoding utf-8 [lindex $argv 0]
set opened 0
set out [open $capture_dir/CONFIG_READBACK.txt w]
fconfigure $out -encoding utf-8
set rc [catch {
    open_hw_manager
    connect_hw_server -url localhost:3121 -cs_url TCP:127.0.0.1:3042
    set target [get_hw_targets -quiet -filter {NAME =~ *C3067D03ABCD*}]
    if {[llength $target]!=1} {error "需要唯一的既有C306目标"}
    set_property PARAM.FREQUENCY 1000000 $target
    open_hw_target $target
    set opened 1
    set dev [get_hw_devices -quiet -filter {PART =~ xc7k325t*}]
    if {[llength $dev]!=1} {error "需要唯一XC7K325T"}
    current_hw_device $dev
    refresh_hw_device -update_hw_probes false $dev
    foreach p [lsort [list_property $dev]] {
        if {[string match REGISTER.CONFIG_STATUS* $p] || [string match REGISTER.BOOT_STATUS* $p]} {
            if {![catch {get_property $p $dev} v]} {puts $out "$p=$v"}
        }
    }
    puts $out "part=[get_property PART $dev]"
} reason]
puts $out "read_status=[expr {$rc ? {FAILED} : {COMPLETED}}]\nreason=$reason"
close $out
if {$opened} {catch {close_hw_target}}
catch {close_hw_manager}
if {$rc} {puts stderr $reason;exit 1}
exit 0
