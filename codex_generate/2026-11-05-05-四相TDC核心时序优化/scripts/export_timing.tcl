# 本轮只导出冻结路由证据和时序报告，不生成SDF/BIT，不运行实现后仿真。
update_timing -full
write_checkpoint $out/design.dcp
write_verilog -mode timesim -sdf_anno false $out/design.v
write_xdc $out/effective_constraints.xdc
report_timing_summary -delay_type min_max -report_unconstrained -file $out/timing_summary.rpt
report_timing -delay_type max -max_paths 100 -path_type full_clock_expanded -input_pins -file $out/setup_top100.rpt
report_timing -delay_type min -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/hold_top50.rpt
report_clocks -file $out/clocks.rpt
report_clock_interaction -file $out/clock_interaction.rpt
report_cdc -details -file $out/cdc.rpt
report_exceptions -file $out/exceptions.rpt
report_bus_skew -file $out/bus_skew.rpt
check_timing -verbose -file $out/check_timing.rpt
report_route_status -file $out/route_status.rpt
report_drc -file $out/drc.rpt
report_utilization -hierarchical -file $out/utilization.rpt
set fd [open $out/module_setup.csv w]
puts $fd "module,perspective,slack_ns,startpoint,endpoint,data_delay_ns,logic_delay_ns,net_delay_ns"
foreach module {u_tdc_fine_layer u_tdc_time_candicate u_tdc_time_locate u_tdc_time_merge u_fifo_tdc_result u_fifo_tdc_error u_ila2} {
    set cells [get_cells -quiet -hier -filter "NAME =~ $module/*"]
    foreach direction {from to} {
        set paths [get_timing_paths -quiet -$direction $cells -delay_type max -max_paths 1]
        if {![llength $paths]} {continue}
        set p [lindex $paths 0]
        puts $fd "$module,$direction,[get_property SLACK $p],[get_property STARTPOINT_PIN $p],[get_property ENDPOINT_PIN $p],[get_property DATAPATH_DELAY $p],[get_property DATAPATH_LOGIC_DELAY $p],[get_property DATAPATH_NET_DELAY $p]"
    }
}
close $fd
set fd [open $out/core_targets.csv w]
puts $fd "target,before_slack_ns,original_startpoint,original_endpoint,original_path_exists,same_path_slack_ns,endpoint_worst_slack_ns,endpoint_worst_startpoint,actual_endpoint,data_delay_ns,logic_delay_ns,net_delay_ns"
set targets [list [list locate20 -0.047 {u_tdc_time_locate/s4_sum_reg[2]} {u_tdc_time_locate/timestamp_ps_reg[20]/D}] [list locate19 -0.022 {u_tdc_time_locate/s4_sum_reg[0]} {u_tdc_time_locate/timestamp_ps_reg[19]/D}] [list locate11 -0.002 {u_tdc_time_locate/s4_sum_reg[2]} {u_tdc_time_locate/timestamp_ps_reg[11]/D}]]
set ram_en [get_pins -quiet -hier -filter {NAME =~ u_fifo_tdc_result/*/ENARDEN}]
if {[llength $ram_en] != 1} {error "结果FIFO BRAM ENARDEN观察点不是唯一值"}
lappend targets [list fifo_enable -0.018 {rst_sync_500m_reg[1]} [get_property NAME $ram_en]]
foreach target $targets {
    lassign $target label before start endpoint
    set endpin [get_pins -quiet $endpoint]
    if {[llength $endpin] != 1} {error "关键端点不存在：$endpoint"}
    set worst [get_timing_paths -quiet -to $endpin -delay_type max -max_paths 1]
    if {![llength $worst]} {error "关键端点没有实际时序路径：$endpoint"}
    set oldpath [get_timing_paths -quiet -from [get_cells -quiet $start] -to $endpin -delay_type max -max_paths 1]
    set same_slack ""
    if {[llength $oldpath]} {set same_slack [get_property SLACK [lindex $oldpath 0]]}
    set p [lindex $worst 0]
    puts $fd "$label,$before,$start/C,$endpoint,[llength $oldpath],$same_slack,[get_property SLACK $p],[get_property STARTPOINT_PIN $p],[get_property ENDPOINT_PIN $p],[get_property DATAPATH_DELAY $p],[get_property DATAPATH_LOGIC_DELAY $p],[get_property DATAPATH_NET_DELAY $p]"
    report_timing -to $endpin -delay_type max -max_paths 10 -path_type full_clock_expanded -input_pins -file $out/${label}_setup.rpt
}
close $fd
set aux_cells [get_cells -quiet -hier -filter {NAME =~ u_tdc_fine_layer/g_aux_4phase*}]
report_timing -from $aux_cells -delay_type max -max_paths 30 -path_type full_clock_expanded -input_pins -file $out/aux_setup.rpt
report_timing -from $aux_cells -delay_type min -max_paths 30 -path_type full_clock_expanded -input_pins -file $out/aux_hold.rpt
report_timing -from [get_cells -hier -filter {NAME =~ u_tdc_time_locate/*}] -delay_type max -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/locate_setup.rpt
report_timing -from [get_cells {rst_result_fifo_500m_reg}] -delay_type max -max_paths 20 -path_type full_clock_expanded -input_pins -file $out/reset_replica_setup.rpt
report_timing -to [get_cells {rst_result_fifo_500m_reg}] -delay_type max -max_paths 10 -path_type full_clock_expanded -input_pins -file $out/reset_replica_input_setup.rpt
set fd [open $out/reset_replica_structure.csv w]
puts $fd "cell,ref_name,loc,bel,D_net,C_net,CLR_net,Q_net,Q_endpoint_loads,ASYNC_REG,DONT_TOUCH"
foreach name {{rst_sync_500m_reg[1]} rst_result_fifo_500m_reg} {
    set cell [get_cells $name]
    set pins {}
    foreach port {D C CLR Q} {lappend pins [get_property NAME [get_nets -of_objects [get_pins $name/$port]]]}
    lassign $pins dn cn rn qn
    set loads [llength [all_fanout -flat -endpoints_only -from [get_pins $name/Q]]]
    puts $fd "$name,[get_property REF_NAME $cell],[get_property LOC $cell],[get_property BEL $cell],$dn,$cn,$rn,$qn,$loads,[get_property ASYNC_REG $cell],[get_property DONT_TOUCH $cell]"
}
close $fd
set fd [open $out/negative_setup.csv w]
puts $fd "slack_ns,startpoint,endpoint,measurement_fifo_reachable_count,measurement_fifo_endpoints"
foreach p [get_timing_paths -quiet -delay_type max -slack_lesser_than 0 -max_paths 1000] {
    set pin [get_property ENDPOINT_PIN $p]
    set cell [get_cells -of_objects [get_pins $pin]]
    set reached {}
    foreach end [all_fanout -flat -endpoints_only -from [get_pins -of_objects $cell -filter {DIRECTION == OUT}]] {
        set name [get_property NAME $end]
        if {[string match u_tdc_* $name] || [string match u_fifo_tdc_* $name]} {lappend reached $name}
    }
    set reached [lsort -unique $reached]
    puts $fd "[get_property SLACK $p],[get_property STARTPOINT_PIN $p],$pin,[llength $reached],[join $reached ;]"
}
close $fd
set fd [open $out/negative_hold.csv w]
puts $fd "slack_ns,startpoint,endpoint"
foreach p [get_timing_paths -quiet -delay_type min -slack_lesser_than 0 -max_paths 1000] {puts $fd "[get_property SLACK $p],[get_property STARTPOINT_PIN $p],[get_property ENDPOINT_PIN $p]"}
close $fd
set fd [open $out/frontend_structure.csv w]
puts $fd "name,ref_name,loc,bel"
foreach cell [lsort [get_cells -hier -filter {NAME =~ u_tdc_fine_layer/*}]] {
    set name [get_property NAME $cell]
    if {[string match *g_carry* $name] || [string match *thermo_q_reg* $name] || [string match *g_pwm_dist* $name] || [string match *g_aux_4phase* $name]} {puts $fd "$name,[get_property REF_NAME $cell],[get_property LOC $cell],[get_property BEL $cell]"}
}
close $fd
set fd [open $out/BUILD_METADATA.txt w]
puts $fd "part=xc7k325tffg900-2\nvivado=[version -short]\nfrequency_mhz=500\nvariant=Compensated_Aux4Phase_CoreTimingFix\ngenerics=$compensation_generics\nnew_false_paths=0\nnew_multicycles=0\ntop_implementation_count=1\nMAX_SDF_executed=0\nBIT_generated=0"
close $fd
