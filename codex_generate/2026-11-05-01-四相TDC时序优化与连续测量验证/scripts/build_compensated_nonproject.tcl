# 非工程流程独立综合补偿版；读取实际生成的IP产品，避免父/子综合同时驻留。
set_param general.maxThreads 1
set root U:/
set variant compensated
set out $root/results/optimized/$variant
if {[file exists $out/design.dcp]} {error "禁止覆盖冻结实现"}
file mkdir $out
create_project -in_memory -part xc7k325tffg900-2
config_ip_cache -use_cache_location $root/build/shared_ip_cache
set_property target_language Verilog [current_project]
read_verilog [glob $root/rtl/*.v]
foreach ip {clk_wiz_0 fifo_tdc_result ila_2 ila_3} {
    read_ip $root/build/compensated/timing_compensated.srcs/sources_1/ip/$ip/$ip.xci
}
foreach ip [get_ips] {
    # 在正式支持的非工程上下文核对注册产品，未过期产品不强制重生成。
    synth_ip $ip
}
source $root/results/calibration_params.tcl
set applied_generics $compensation_generics
synth_design -top tdc_meas_top -part xc7k325tffg900-2 -directive PerformanceOptimized -fsm_extraction one_hot -keep_equivalent_registers -resource_sharing off -no_lc -shreg_min_size 5 -generic $compensation_generics
write_checkpoint $out/top_synth.dcp
report_utilization -file $out/top_synth_utilization.rpt
read_xdc $root/inputs/combine.xdc
set_param general.maxThreads 2
opt_design -directive Explore
source $root/scripts/restore_bram_mode.tcl
write_checkpoint $out/post_opt.dcp
read_checkpoint -incremental $root/results/optimized/baseline/design.dcp
source $root/scripts/prepare_ila_cluster.tcl
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
write_checkpoint $out/post_place_phys.dcp
route_design -directive Explore
report_timing_summary -delay_type min_max -file $out/pre_postroute_physopt_timing.rpt
phys_opt_design -directive AggressiveExplore
set flow_notes "independent_nonproject_top_synthesis_PerformanceOptimized_with_frozen_8_parameters;actual_registered_IP_products;incremental_reference=frozen_optimized_baseline;preplace_BRAM_power_opt;localized_ILA_counter_pblock_SLICE_X13Y16_X20Y25;place=ExtraPostPlacementOpt;phys=AggressiveExplore;route=Explore;postroute=AggressiveExplore"
write_xdc $out/effective_constraints.xdc
set export_bitstream 1
source $root/scripts/export_evidence.tcl
