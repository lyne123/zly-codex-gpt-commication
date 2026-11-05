# 复用原IP配置和已成功的OOC缓存，仅对新增辅助逻辑做一次顶层综合与实现。
set_param general.maxThreads 1
set root W:/
set out $root/results/compensated
if {![file exists $root/results/RTL_STAGE_GATE.json]} {error "尚未通过RTL阶段"}
if {![file exists $root/results/UNIT_CHECKS.json]} {error "尚未通过回卷及FIFO复位等价检查"}
if {[file exists $out/design.dcp] || [file exists $out/top_synth.dcp]} {error "禁止覆盖已有实现；需先定位后从检查点继续"}
file mkdir $out
create_project -in_memory -part xc7k325tffg900-2
set_property target_language Verilog [current_project]
set_property simulator_language Mixed [current_project]
config_ip_cache -use_cache_location $root/build/ip_cache
read_verilog [glob $root/rtl/*.v]
foreach ip {clk_wiz_0 fifo_tdc_result ila_2 ila_3} {read_ip $root/build/registered/aux_compensated.srcs/sources_1/ip/$ip/$ip.xci}
puts "AUX_BUILD_STAGE=IP_PRODUCTS"
foreach ip [get_ips] {synth_ip $ip}
foreach ip {clk_wiz_0 fifo_tdc_result ila_2 ila_3} {
    if {![file exists $root/build/registered/aux_compensated.gen/sources_1/ip/$ip/$ip.dcp]} {error "IP产品未就绪，禁止进入顶层综合：$ip"}
}
puts "AUX_BUILD_STAGE=TOP_SYNTHESIS"
source $root/inputs/compensation_params.tcl
synth_design -top tdc_meas_top -part xc7k325tffg900-2 -directive PerformanceOptimized -fsm_extraction one_hot -keep_equivalent_registers -resource_sharing off -no_lc -shreg_min_size 5 -generic $compensation_generics
write_checkpoint $out/top_synth.dcp
report_utilization -file $out/top_synth_utilization.rpt
read_xdc $root/inputs/combine.xdc
# 实际实现中该foreach XDC被工具拒绝，未施加任何LOC；保留原文件及used脚本供审查。
# 复现仅使用原有效XDC和RTL中的ASYNC_REG，避免重复读取无效LOC尝试。
set_param general.maxThreads 2
puts "AUX_BUILD_STAGE=OPTIMIZATION"
opt_design -directive Explore
source $root/scripts/restore_bram_mode.tcl
write_checkpoint $out/post_opt.dcp
read_checkpoint -incremental Y:/results/compensated/design.dcp
source $root/scripts/prepare_ila_cluster.tcl
puts "AUX_BUILD_STAGE=PLACEMENT"
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
write_checkpoint $out/post_place_phys.dcp
puts "AUX_BUILD_STAGE=ROUTING"
route_design -directive Explore
phys_opt_design -directive AggressiveExplore
puts "AUX_BUILD_STAGE=EXPORT"
source $root/scripts/export_timing.tcl
close_design
puts "AUX_BUILD_COMPLETE"
