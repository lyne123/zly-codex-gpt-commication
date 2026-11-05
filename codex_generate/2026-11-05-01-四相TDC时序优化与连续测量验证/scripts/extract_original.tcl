# 只读打开上一轮冻结DCP，全部新报告写入本次任务目录。
set_param general.maxThreads 2
set root U:/
help check_timing
help report_property
foreach variant {baseline compensated} {
    set out $root/results/original_inspection/$variant
    file mkdir $out
    open_checkpoint T:/results/$variant/design.dcp
    report_timing_summary -delay_type min_max -report_unconstrained -file $out/timing_summary.rpt
    report_timing -delay_type max -max_paths 50 -path_type full_clock_expanded -input_pins -nets -file $out/setup_top50.rpt
    report_timing -delay_type min -max_paths 50 -path_type full_clock_expanded -input_pins -nets -file $out/hold_top50.rpt
    report_design_analysis -max_paths 50 -setup -file $out/design_analysis_setup.rpt
    check_timing -verbose -file $out/check_timing.rpt
    report_clock_interaction -file $out/clock_interaction.rpt
    report_exceptions -file $out/exceptions.rpt
    report_cdc -details -file $out/cdc.rpt
    report_utilization -file $out/utilization.rpt
    set paths [get_timing_paths -delay_type max -max_paths 50]
    set fd [open $out/path_properties.txt w]
    foreach p $paths {
        foreach prop [list_property $p] { puts $fd "$prop\t[get_property $prop $p]" }
        puts $fd "END_PATH"
    }
    close $fd
    close_design
}
