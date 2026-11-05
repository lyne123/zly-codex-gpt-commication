# 只读打开冻结路由结果，补充模块输入边界及复位控制的具体违例路径。
set_param general.maxThreads 2
set out W:/results/compensated
open_checkpoint $out/design.dcp
update_timing -full
set fd [open $out/module_all_boundary_setup.csv w]
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
report_timing -from [get_cells {rst_sync_500m_reg[1]}] -delay_type max -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/reset_control_setup_top50.rpt
report_timing -to [get_cells -hier -filter {NAME =~ u_fifo_tdc_result/*}] -delay_type max -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/result_fifo_incoming_setup_top50.rpt
report_timing_summary -delay_type min_max -report_unconstrained -file $out/failure_audit_timing_summary.rpt
close_design
puts "READ_ONLY_FAILURE_AUDIT_COMPLETE"
