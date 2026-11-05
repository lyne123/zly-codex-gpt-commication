# 官方TimingClosure模式以0ns为目标，避免RuntimeOptimized沿用负裕量参考。
set_param general.maxThreads 2
set root U:/
foreach variant {baseline compensated} {
    set out $root/results/trials/${variant}_incremental_timing_closure
    if {[file exists $out/design.dcp]} {error "禁止覆盖冻结试验"}
    file mkdir $out
    if {$variant eq "baseline"} {set applied_generics ENABLE_SKEW_COMP=0} else {
        source $root/results/calibration_params.tcl
        set applied_generics $compensation_generics
    }
    set reference $root/results/optimized/$variant/design.dcp
    open_checkpoint $reference
    read_checkpoint -incremental -directive TimingClosure $reference
    place_design -directive ExtraPostPlacementOpt
    phys_opt_design -directive AggressiveExplore
    route_design -directive Explore
    phys_opt_design -directive AggressiveExplore
    set flow_notes "source=$reference;incremental_directive=TimingClosure_target_WNS_0;place_phys_route_use_actual_TimingClosure_override;RTL_and_parameters_unchanged"
    set export_bitstream 1
    source $root/scripts/export_evidence.tcl
}
