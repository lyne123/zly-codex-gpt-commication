proc export_timing {folder} {
    file mkdir $folder
    update_timing -full
    report_timing_summary -delay_type min_max -report_unconstrained -file $folder/timing_summary.rpt
    report_timing -delay_type max -max_paths 40 -path_type full_clock_expanded -file $folder/setup_top40.rpt
    report_timing -delay_type min -max_paths 20 -file $folder/hold_top20.rpt
    foreach delay {max min} {
        set fd [open $folder/negative_${delay}.csv w]
        puts $fd "slack_ns,startpoint,endpoint"
        foreach p [get_timing_paths -quiet -delay_type $delay -slack_lesser_than 0 -max_paths 10000 -nworst 1] {
            puts $fd "[get_property SLACK $p],[get_property STARTPOINT_PIN $p],[get_property ENDPOINT_PIN $p]"
        }
        close $fd
    }
    set fd [open $folder/core_timing.csv w]
    puts $fd "module,delay_type,slack_ns,startpoint,endpoint"
    foreach module {u_tdc_fine_layer u_tdc_time_candicate u_tdc_time_locate u_tdc_time_merge u_fifo_tdc_result u_fifo_tdc_error} {
        set cells [get_cells -quiet -hier -filter "NAME =~ $module/*"]
        foreach delay {max min} {
            set p [get_timing_paths -quiet -to $cells -delay_type $delay -max_paths 1]
            if {[llength $p]} {puts $fd "$module,$delay,[get_property SLACK $p],[get_property STARTPOINT_PIN $p],[get_property ENDPOINT_PIN $p]"}
        }
    }
    close $fd
    report_clocks -file $folder/clocks.rpt
    report_exceptions -file $folder/exceptions.rpt
}
# Baseline报告复用同一AD23冻结DCP的已完成只读提取。

