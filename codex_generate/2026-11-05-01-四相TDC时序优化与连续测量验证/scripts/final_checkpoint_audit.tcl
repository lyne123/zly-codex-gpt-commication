# 补充四份冻结DCP的总线偏斜、分模块路径及实际ILA BRAM模式。
set_param general.maxThreads 2
set root U:/
foreach phase {original optimized} {
    foreach variant {baseline compensated} {
        set dir $root/results/$phase/$variant
        if {![file exists $dir/design.dcp]} {continue}
        if {[file exists $dir/bus_skew_audit.rpt] && [file exists $dir/module_worst_setup.csv] && [file exists $dir/ila_bram_modes_final.txt] && ($phase eq "original" || [file exists $dir/fresh_timing_summary.rpt])} {continue}
        open_checkpoint $dir/design.dcp
        if {$phase eq "optimized"} {
            puts [help update_timing]
            update_timing -full
            report_timing_summary -delay_type min_max -report_unconstrained -file $dir/fresh_timing_summary.rpt
            report_timing -delay_type max -max_paths 50 -path_type full_clock_expanded -input_pins -file $dir/fresh_setup_top50.rpt
            report_timing -delay_type min -max_paths 50 -path_type full_clock_expanded -input_pins -file $dir/fresh_hold_top50.rpt
            check_timing -verbose -file $dir/fresh_check_timing.rpt
        }
        if {![file exists $dir/bus_skew_audit.rpt]} {report_bus_skew -file $dir/bus_skew_audit.rpt}
        if {$phase eq "original"} {file copy $dir/bus_skew_audit.rpt $root/results/original_inspection/$variant/bus_skew_audit.rpt}
        if {![file exists $dir/hierarchical_utilization.rpt]} {report_utilization -hierarchical -file $dir/hierarchical_utilization.rpt}
        set fd [open $dir/module_worst_setup.csv w]
        puts $fd "module,slack_ns,startpoint,endpoint,data_delay_ns,logic_delay_ns,net_delay_ns"
        foreach module {u_tdc_fine_layer u_tdc_time_candicate u_tdc_time_locate u_tdc_time_merge u_ila2 u_fifo_tdc_result u_fifo_tdc_error} {
            set cells [get_cells -quiet -hier -filter "NAME =~ $module/*"]
            if {![llength $cells]} {continue}
            set paths [get_timing_paths -quiet -from $cells -delay_type max -max_paths 1]
            if {![llength $paths]} {continue}
            set path [lindex $paths 0]
            puts $fd "$module,[get_property SLACK $path],[get_property STARTPOINT_PIN $path],[get_property ENDPOINT_PIN $path],[get_property DATAPATH_DELAY $path],[get_property DATAPATH_LOGIC_DELAY $path],[get_property DATAPATH_NET_DELAY $path]"
        }
        close $fd
        set fd [open $dir/ila_bram_modes_final.txt w]
        foreach cell [get_cells -hier -filter {REF_NAME == RAMB36E1 && NAME =~ u_ila2/*}] {
            puts $fd "[get_property NAME $cell]\t[get_property WRITE_MODE_A $cell]\t[get_property WRITE_MODE_B $cell]\t[get_property DOA_REG $cell]\t[get_property DOB_REG $cell]"
        }
        close $fd
        close_design
    }
}
