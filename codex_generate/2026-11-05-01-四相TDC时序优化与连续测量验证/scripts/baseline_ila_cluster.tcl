# 最差路径79%为布线，仅将ILA内部采样/窗口计数和触发寄存器聚集。
set_param general.maxThreads 2
set root U:/
set variant baseline
set applied_generics ENABLE_SKEW_COMP=0
set out $root/results/trials/baseline_ila_cluster
if {[file exists $out/design.dcp]} {error "禁止覆盖已有试验"}
file mkdir $out
open_checkpoint $root/results/trials/baseline_power_replicated/design.dcp
set cells [get_cells -hier -filter {NAME =~ u_ila2/inst/ila_core_inst/u_ila_cap_ctrl/u_cap_addrgen/* || NAME =~ u_ila2/inst/ila_core_inst/basic_trigger_reg*}]
set fd [open $out/cluster_cells.txt w]
foreach cell $cells {puts $fd "[get_property NAME $cell]\t[get_property REF_NAME $cell]\t[get_property LOC $cell]"}
close $fd
create_pblock pblock_ila_counter_local
resize_pblock [get_pblocks pblock_ila_counter_local] -add {SLICE_X14Y16:SLICE_X19Y24}
add_cells_to_pblock [get_pblocks pblock_ila_counter_local] $cells
route_design -unroute
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
route_design -directive Explore
phys_opt_design -directive AggressiveExplore
set flow_notes "source=baseline_power_replicated/design.dcp;localized_ILA_counter_pblock_SLICE_X14Y16_X19Y24;place=ExtraPostPlacementOpt;phys=AggressiveExplore;route=Explore"
set export_bitstream 1
source $root/scripts/export_evidence.tcl
