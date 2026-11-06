# 使用真实ASCII工作路径与原IP；不增加约束、不修改参数、不创建虚拟盘符。
set_param general.maxThreads 1
set_param ips.addSpecialDataToCacheID 0
set work [file dirname [file normalize [info script]]]
cd $work
set out $work/implementation_F
file mkdir $out
if {[file exists $out/corrected_synth.dcp]} {error "已有综合结果，禁止覆盖重跑"}
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
create_project -in_memory -part xc7k325tffg900-2
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
config_ip_cache -use_cache_location $work/ip_cache
read_verilog [glob $work/F_factored/*.v]
foreach ip {clk_wiz_0 fifo_tdc_result ila_2 ila_3} {
    read_ip $work/registered/aux_compensated.srcs/sources_1/ip/$ip/$ip.xci
    synth_ip [get_ips $ip]
}
source -encoding utf-8 $work/compensation_params.tcl
puts "AUXFALL_STAGE=SYNTHESIS"
synth_design -top tdc_meas_top -part xc7k325tffg900-2 -directive PerformanceOptimized -fsm_extraction one_hot -keep_equivalent_registers -resource_sharing off -no_lc -shreg_min_size 5 -generic $compensation_generics
write_checkpoint $out/corrected_synth.dcp
read_xdc $work/combine_AD23.xdc
puts "AUXFALL_STAGE=IMPLEMENTATION"
opt_design -directive Explore
opt_design -bram_power_opt
read_checkpoint -incremental $work/production_AD23.dcp
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
write_checkpoint $out/corrected_placed.dcp
route_design -directive Explore
phys_opt_design -directive AggressiveExplore
write_checkpoint $out/corrected_routed.dcp
export_timing $out/after
report_route_status -file $out/after/route_status.rpt
report_drc -file $out/after/drc.rpt
report_utilization -hierarchical -file $out/after/utilization.rpt
write_debug_probes $out/Corrected.ltx
write_xdc $out/effective_constraints.xdc
# 先导出时序仿真证据；BIT只在SDF验收后单独导出。
write_verilog -mode timesim -sdf_anno false $out/post_route_timing.v
write_sdf -process_corner slow $out/post_route_max.sdf
set bad_core 0
foreach delay {max min} {
    foreach p [get_timing_paths -quiet -delay_type $delay -slack_lesser_than 0 -max_paths 10000 -nworst 1] {
        set end [get_property ENDPOINT_PIN $p]
        if {![string match u_ila* $end] && ![string match dbg_hub/* $end]} {incr bad_core}
    }
}
set fd [open $out/TIMING_GATE.txt w]
puts $fd "core_negative_endpoints=$bad_core\nbit_generated=0\nformal_rtl_modified=0\nfrequency_mhz=500"
close $fd
if {$bad_core} {error "CORE_TIMING_FAIL：保留证据，禁止宣称修复通过"}
puts "AUXFALL_IMPLEMENTATION_CORE_PASS"
close_design

