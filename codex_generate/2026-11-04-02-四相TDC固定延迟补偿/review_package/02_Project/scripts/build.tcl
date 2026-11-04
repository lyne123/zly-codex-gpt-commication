# 在本任务的独立工程内构建，不打开或改写参考工程。
if {[info exists ::env(TDC_TASK_ROOT)]} {
    set task_root $::env(TDC_TASK_ROOT)
} else {
    set task_root [file join [file dirname [info script]] ..]
}
set_param general.maxThreads 2
set variant [lindex $argv 0]
if {$variant ni {baseline compensated}} { error "variant must be baseline or compensated" }
set out [file join $task_root results $variant]
file mkdir $out
set project_dir [file join $task_root build ${variant}_ascii]
if {[file exists [file join $out design.dcp]]} { error "Refusing to overwrite implementation evidence" }
if {[file exists [file join $project_dir tdc_${variant}.xpr]]} {
    open_project [file join $project_dir tdc_${variant}.xpr]
} else {
create_project tdc_${variant} $project_dir -part xc7k325tffg900-2
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
set_property target_simulator XSim [current_project]
if {$variant eq "baseline"} {
    set rtl_dir [file join $task_root baseline rtl]
} else {
    set rtl_dir [file join $task_root rtl]
}
add_files [glob [file join $rtl_dir *.v]]
set_property top tdc_meas_top [get_filesets sources_1]
foreach ip {clk_wiz_0 fifo_tdc_result ila_2 ila_3} {
    import_ip -files [file join $task_root inputs ip $ip ${ip}.xci]
}
add_files -fileset constrs_1 [file join $task_root inputs combine.xdc]
set_property USED_IN_SYNTHESIS false [get_files combine.xdc]
set_property PROCESSING_ORDER LATE [get_files combine.xdc]
if {$variant eq "compensated"} {
    set param_file [file join $task_root results calibration_params.tcl]
    if {![file exists $param_file]} { error "No measured calibration parameters" }
    source $param_file
    set_property generic $compensation_generics [get_filesets sources_1]
}
generate_target all [get_ips]
}
foreach ip [get_ips] {
    if {![llength [get_runs -quiet ${ip}_synth_1]]} { create_ip_run $ip }
}
launch_runs synth_1 -jobs 2
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} { error "synthesis failed" }
if {$variant eq "compensated"} {
    # 尽可能复用已测量前端的布局布线，仍需用导出指纹检查实际复用结果。
    set_property INCREMENTAL_CHECKPOINT [file join $task_root results baseline design.dcp] [get_runs impl_1]
}
launch_runs impl_1 -to_step route_design -jobs 2
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} { error "implementation failed" }
open_run impl_1
write_checkpoint -force [file join $out design.dcp]
report_timing_summary -delay_type min_max -report_unconstrained -file [file join $out timing_summary.rpt]
report_timing -delay_type max -max_paths 40 -file [file join $out setup_paths.rpt]
report_timing -delay_type min -max_paths 40 -file [file join $out hold_paths.rpt]
report_utilization -file [file join $out utilization.rpt]
report_clocks -file [file join $out clocks.rpt]
report_clock_interaction -file [file join $out clock_interaction.rpt]
report_exceptions -file [file join $out exceptions.rpt]
report_drc -file [file join $out drc.rpt]
report_methodology -file [file join $out methodology.rpt]
report_route_status -file [file join $out route_status.rpt]
write_verilog -force -mode timesim -sdf_anno false [file join $out design.v]
write_sdf -force -process_corner slow [file join $out design.sdf]
foreach phase {0 90 180 270} {
    set pins [get_pins -hier -filter "NAME =~ *u_tdl${phase}*g_carry*0*CYINIT"]
    if {[llength $pins]} {
        report_timing -from [get_ports pwm_in] -to $pins -max_paths 4 -file [file join $out pwm_path_${phase}.rpt]
    }
}
set fd [open [file join $out build_metadata.txt] w]
puts $fd "vivado=[version -short]\npart=[get_property PART [current_project]]\nvariant=$variant\nstrategy=[get_property STRATEGY [get_runs impl_1]]\ncorner=slow\nsdf_mode=max\nseed=Vivado default; no public seed override used"
puts $fd "rtl=$rtl_dir"
close $fd
# 保留失败证据，不降低 DRC 严重级别或屏蔽时序检查。
if {[catch {write_bitstream -force [file join $out tdc_${variant}.bit]} bit_error]} {
    set fd [open [file join $out bitstream_failure.txt] w]
    puts $fd $bit_error
    close $fd
}
close_project
source [file join $task_root scripts inspect_implementation.tcl]
