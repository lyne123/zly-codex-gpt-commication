# 两版本独立构建，保留全部既有TDL、时钟、IO与厂商CDC约束。
set_param general.maxThreads 1
set root U:/
set variant [lindex $argv 0]
set stage [lindex $argv 1]
if {$variant ni {baseline compensated}} {error "invalid variant"}
set out $root/results/optimized/$variant
if {[file exists $out/design.dcp]} {error "禁止覆盖已有冻结实现"}
file mkdir $out
set project_file $root/build/$variant/timing_$variant.xpr
if {[file exists $project_file]} {
    open_project $project_file
} else {
create_project timing_$variant $root/build/$variant -part xc7k325tffg900-2
config_ip_cache -use_cache_location $root/build/shared_ip_cache
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
add_files [glob $root/rtl/*.v]
set_property top tdc_meas_top [get_filesets sources_1]
foreach ip {clk_wiz_0 fifo_tdc_result ila_2 ila_3} {import_ip -files $root/inputs/ip/$ip/$ip.xci}
add_files -fileset constrs_1 $root/inputs/combine.xdc
set_property USED_IN_SYNTHESIS false [get_files combine.xdc]
set_property PROCESSING_ORDER LATE [get_files combine.xdc]
set_property strategy Flow_PerfOptimized_high [get_runs synth_1]
set_property strategy Performance_ExplorePostRoutePhysOpt [get_runs impl_1]
if {$variant eq "compensated"} {
    source $root/results/calibration_params.tcl
    set_property generic $compensation_generics [get_filesets sources_1]
    set_property INCREMENTAL_CHECKPOINT $root/results/optimized/baseline/design.dcp [get_runs impl_1]
} else {set_property generic {ENABLE_SKEW_COMP=0} [get_filesets sources_1]}
generate_target all [get_ips]
}
foreach ip [get_ips] {if {![llength [get_runs -quiet ${ip}_synth_1]]} {create_ip_run $ip}}
config_ip_cache -use_cache_location $root/build/shared_ip_cache
set applied_generics [get_property generic [get_filesets sources_1]]
if {$variant eq "compensated"} {
    # 根据Baseline实际路径采用局部ILA布局，并在路由前修复BRAM模式。
    set_property STEPS.OPT_DESIGN.TCL.POST $root/scripts/restore_bram_mode.tcl [get_runs impl_1]
    set_property STEPS.PLACE_DESIGN.TCL.PRE $root/scripts/prepare_ila_cluster.tcl [get_runs impl_1]
    set_property STEPS.PLACE_DESIGN.ARGS.DIRECTIVE ExtraPostPlacementOpt [get_runs impl_1]
    set_property STEPS.PHYS_OPT_DESIGN.IS_ENABLED true [get_runs impl_1]
    set_property STEPS.PHYS_OPT_DESIGN.ARGS.DIRECTIVE AggressiveExplore [get_runs impl_1]
    set_property STEPS.ROUTE_DESIGN.ARGS.DIRECTIVE Explore [get_runs impl_1]
    set flow_notes "independent_compensated_synthesis;incremental_reference=frozen_optimized_baseline;preplace_BRAM_power_opt;localized_ILA_counter_pblock_SLICE_X13Y16_X20Y25;place=ExtraPostPlacementOpt;phys=AggressiveExplore;route=Explore;postroute=AggressiveExplore"
}
if {$stage eq "prepare_only"} {
    # 仅准备独立工程/IP源产品，随后由正式非工程流程单进程综合。
    close_project
    return
}
if {$stage eq "prepare_impl"} {
    set_param general.maxThreads 2
    reset_run impl_1
    # 缩短嵌套Debug Hub子工程的工作路径，保留原有工程与失败目录。
    set run_dir $root/build/r$variant
    launch_runs impl_1 -to_step route_design -scripts_only -dir $run_dir -jobs 1
    puts "ACTUAL_RUN_DIRECTORY=[get_property DIRECTORY [get_runs impl_1]]"
    close_project
    return
}
if {$stage ne "export_impl"} {
# IP逐个执行；首轮并行失败日志已另存，避免同时驻留多个综合进程。
foreach ip [get_ips] {
    set run ${ip}_synth_1
    if {[get_property PROGRESS [get_runs $run]] ne "100%" && ![config_ip_cache -cache_was_used $ip]} {
        reset_run $run
        set_property STEPS.SYNTH_DESIGN.TCL.PRE $root/scripts/limit_threads.tcl [get_runs $run]
        launch_runs $run -jobs 1
        wait_on_run $run
        if {[get_property PROGRESS [get_runs $run]] ne "100%"} {error "IP synthesis failed: $ip"}
    }
}
reset_run synth_1
set_property STEPS.SYNTH_DESIGN.TCL.PRE $root/scripts/limit_threads.tcl [get_runs synth_1]
launch_runs synth_1 -jobs 1
wait_on_run synth_1
if {[get_property PROGRESS [get_runs synth_1]] ne "100%"} {error "synth failed"}
set_param general.maxThreads 2
launch_runs impl_1 -to_step route_design -jobs 1
wait_on_run impl_1
if {[get_property PROGRESS [get_runs impl_1]] ne "100%"} {error "route failed"}
}
if {$stage eq "export_impl"} {
    # 独立runme执行不会更新GUI运行面板；以真实完成标志和路由DCP打开结果。
    set routed_dir [get_property DIRECTORY [get_runs impl_1]]
    if {![file exists $routed_dir/.route_design.end.rst] || ![file exists $routed_dir/tdc_meas_top_routed.dcp]} {error "没有已完成的真实路由结果"}
    close_project
    open_checkpoint $routed_dir/tdc_meas_top_routed.dcp
} else {open_run impl_1}
report_timing_summary -delay_type min_max -report_unconstrained -file $out/pre_postroute_physopt_timing.rpt
# 该策略的route后物理优化在此显式执行，最终DCP、BIT、网表和SDF均从同一设计导出。
phys_opt_design -directive AggressiveExplore
report_timing_summary -delay_type min_max -report_unconstrained -file $out/postroute_physopt_timing.rpt
source $root/scripts/export_evidence.tcl
