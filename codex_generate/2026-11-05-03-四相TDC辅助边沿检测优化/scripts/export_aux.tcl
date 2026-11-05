# 所有最终产物由同一份路由设计导出，不改变补偿或原工程文件。
update_timing -full
write_checkpoint $out/design.dcp
write_xdc $out/effective_constraints.xdc
report_timing_summary -delay_type min_max -report_unconstrained -file $out/timing_summary.rpt
report_timing -delay_type max -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/setup_top50.rpt
report_timing -delay_type min -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/hold_top50.rpt
report_clocks -file $out/clocks.rpt
report_clock_interaction -file $out/clock_interaction.rpt
report_cdc -details -file $out/cdc.rpt
report_exceptions -file $out/exceptions.rpt
check_timing -verbose -file $out/check_timing.rpt
report_route_status -file $out/route_status.rpt
report_drc -file $out/drc.rpt
report_utilization -hierarchical -file $out/utilization.rpt
set fd [open $out/module_worst_setup.csv w]
puts $fd "module,slack_ns,startpoint,endpoint,data_delay_ns,logic_delay_ns,net_delay_ns"
foreach module {u_tdc_fine_layer u_tdc_time_candicate u_tdc_time_locate u_tdc_time_merge u_fifo_tdc_result u_fifo_tdc_error u_ila2} {
    set cells [get_cells -quiet -hier -filter "NAME =~ $module/*"]
    set paths [get_timing_paths -quiet -from $cells -delay_type max -max_paths 1]
    if {![llength $paths]} {continue}
    set p [lindex $paths 0]
    puts $fd "$module,[get_property SLACK $p],[get_property STARTPOINT_PIN $p],[get_property ENDPOINT_PIN $p],[get_property DATAPATH_DELAY $p],[get_property DATAPATH_LOGIC_DELAY $p],[get_property DATAPATH_NET_DELAY $p]"
}
close $fd
set aux_cells [get_cells -quiet -hier -filter {NAME =~ u_tdc_fine_layer/g_aux_4phase*}]
if {![llength $aux_cells]} {error "新辅助逻辑未保留"}
report_timing -from $aux_cells -delay_type max -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/aux_setup_top50.rpt
report_timing -from $aux_cells -delay_type min -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/aux_hold_top50.rpt
set fd [open $out/negative_setup_reachability.csv w]
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
set fd [open $out/frontend_structure.csv w]
puts $fd "name,ref_name,loc,bel"
foreach cell [lsort [get_cells -hier -filter {NAME =~ u_tdc_fine_layer/*}]] {
    set name [get_property NAME $cell]
    if {[string match *g_carry* $name] || [string match *thermo_q_reg* $name] || [string match *g_pwm_dist* $name] || [string match *g_aux_4phase* $name]} {
        puts $fd "$name,[get_property REF_NAME $cell],[get_property LOC $cell],[get_property BEL $cell]"
    }
}
close $fd
write_verilog -mode timesim -sdf_anno true $out/design.v
write_sdf -process_corner slow $out/design.sdf
write_bitstream $out/Baseline_Aux4Phase.bit
set fd [open $out/BUILD_METADATA.txt w]
puts $fd "part=xc7k325tffg900-2\nvivado=[version -short]\nvariant=Baseline\nENABLE_SKEW_COMP=0\nENABLE_AUX_4PHASE=1\nfrequency_mhz=500\ncorner=slow/MAX\nnew_false_paths=0\nnew_multicycles=0\nimplementation_count=1"
close $fd
