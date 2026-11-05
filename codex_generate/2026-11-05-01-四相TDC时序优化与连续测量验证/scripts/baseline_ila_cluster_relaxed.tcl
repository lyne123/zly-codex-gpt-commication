# 首个局部区域54 Slice不足，按实际61 Slice需求放宽为80 Slice再验证。
set_param general.maxThreads 2
set root U:/
set variant baseline
set applied_generics ENABLE_SKEW_COMP=0
set out $root/results/trials/baseline_ila_cluster_relaxed
if {[file exists $out/design.dcp]} {error "禁止覆盖已有试验"}
file mkdir $out
open_checkpoint $root/results/trials/baseline_ila_cluster/design.dcp
resize_pblock [get_pblocks pblock_ila_counter_local] -remove {SLICE_X14Y16:SLICE_X19Y24}
resize_pblock [get_pblocks pblock_ila_counter_local] -add {SLICE_X13Y16:SLICE_X20Y25}
route_design -unroute
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive AggressiveExplore
route_design -directive Explore
phys_opt_design -directive AggressiveExplore
set flow_notes "source=baseline_ila_cluster/design.dcp;localized_ILA_counter_pblock_relaxed_to_80_Slices_SLICE_X13Y16_X20Y25;place=ExtraPostPlacementOpt;phys=AggressiveExplore;route=Explore"
set export_bitstream 1
source $root/scripts/export_evidence.tcl
