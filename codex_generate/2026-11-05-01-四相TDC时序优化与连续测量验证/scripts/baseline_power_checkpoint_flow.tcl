# 从冻结物理DCP创建独立实现分支，避免重复嵌套生成Debug Hub或清理已有run。
set_param general.maxThreads 2
set root U:/
set variant baseline
set applied_generics ENABLE_SKEW_COMP=0
set out $root/results/trials/baseline_power_replicated
if {[file exists $out/design.dcp]} {error "禁止覆盖已有试验"}
file mkdir $out
open_checkpoint $root/results/trials/baseline_initial/design.dcp
route_design -unroute
opt_design -bram_power_opt
set fd [open $out/bram_mode_after_power_opt.txt w]
foreach cell [get_cells -hier -filter {REF_NAME == RAMB36E1 && NAME =~ u_ila2/*}] {puts $fd "[get_property NAME $cell]\t[get_property WRITE_MODE_A $cell]\t[get_property PWROPT_WRITE_MODE_CHANGE_A $cell]"}
close $fd
place_design -directive ExtraPostPlacementOpt
phys_opt_design -directive Explore
source $root/scripts/replicate_ila_drivers.tcl
route_design -directive Explore
phys_opt_design -placement_opt -routing_opt -critical_cell_opt -critical_pin_opt
set flow_notes "source=Explore_opt_checkpoint;preplace_bram_power_opt;place=ExtraPostPlacementOpt;force_ILA_driver_replication;route=Explore;postroute=targeted_placement_routing"
set slack [get_property SLACK [get_timing_paths -delay_type max -max_paths 1]]
set export_bitstream [expr {$slack >= 0}]
source $root/scripts/export_evidence.tcl
