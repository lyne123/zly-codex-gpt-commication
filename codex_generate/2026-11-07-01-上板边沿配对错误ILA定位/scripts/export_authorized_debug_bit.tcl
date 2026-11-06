# 用户本轮明确允许忽略上一轮ILA内部负裕量，导出同一冻结路由结果。
# 不重新综合、布局布线或修改正式RTL；测量核心和影子采集路径仍不能有负裕量。
set_param general.maxThreads 1
set work [file dirname [file normalize [info script]]]
set out $work/authorized_debug_01
if {[file exists $out/ILA_DEBUG.bit]} {error "已有Debug BIT，禁止覆盖"}
file mkdir $out
open_checkpoint $work/results/debug_routed.dcp
if {[get_property PART [current_design]] ne "xc7k325tffg900-2"} {error "器件不符"}
if {[get_property PACKAGE_PIN [get_ports pwm_in]] ne "AD23"} {error "PWM引脚不符"}
update_timing -full
set fd [open $out/ACCEPTED_TIMING_EXCEPTIONS.csv w]
puts $fd "delay_type,slack_ns,startpoint,endpoint"
set ila_setup_count 0
foreach delay {max min} {
    foreach p [get_timing_paths -quiet -delay_type $delay -slack_lesser_than 0 -max_paths 10000 -nworst 1] {
        set endpoint [get_property ENDPOINT_PIN $p]
        set startpoint [get_property STARTPOINT_PIN $p]
        if {$delay ne "max" || ![string match u_ila* $endpoint] || ![string match u_ila* $startpoint]} {
            error "发现ILA内部Setup以外的负路径，停止导出：$delay $startpoint -> $endpoint"
        }
        incr ila_setup_count
        puts $fd "$delay,[get_property SLACK $p],$startpoint,$endpoint"
    }
}
close $fd
report_timing_summary -delay_type min_max -file $out/timing_summary.rpt
report_route_status -file $out/route_status.rpt
write_debug_probes $out/ILA_DEBUG.ltx
set fd [open $out/USER_AUTHORIZATION.txt w]
fconfigure $fd -encoding utf-8
puts $fd "用户明确指令：上次时序没通过是ila的原因就不用管了；就是要烧录上一轮结果的bit。"
puts $fd "来源为上一轮冻结的debug_routed.dcp；没有重新综合、布局布线、修改RTL或参数。"
puts $fd "仅接受已存在的ILA内部Setup负裕量，共${ila_setup_count}条；未修改任何时序约束或检查。"
close $fd
puts "AUTHORIZED_DEBUG_BIT_EXPORT_START ILA_INTERNAL_NEGATIVE_SETUP=$ila_setup_count"
flush stdout
write_bitstream $out/ILA_DEBUG.bit
puts "AUTHORIZED_DEBUG_BIT_EXPORT_COMPLETE"
close_design
