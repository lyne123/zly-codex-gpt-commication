# 从已解决BRAM最小周期的冻结DCP继续物理优化，不改逻辑和约束。
set_param general.maxThreads 2
set root U:/
set variant baseline
set applied_generics ENABLE_SKEW_COMP=0
set out $root/results/trials/baseline_power_aggressive
if {[file exists $out/design.dcp]} {error "禁止覆盖冻结结果"}
file mkdir $out
open_checkpoint $root/results/trials/baseline_power_replicated/design.dcp
phys_opt_design -directive AggressiveExplore
report_timing_summary -delay_type min_max -file $out/after_aggressive.rpt
if {[get_property SLACK [get_timing_paths -delay_type max -max_paths 1]] < 0} {
    phys_opt_design -directive AlternateReplication
    report_timing_summary -delay_type min_max -file $out/after_alternate.rpt
}
set flow_notes "source=baseline_power_replicated/design.dcp;postroute=AggressiveExplore_then_AlternateReplication_if_negative;preplace_BRAM_power_opt_in_parent"
set export_bitstream 1
source $root/scripts/export_evidence.tcl
