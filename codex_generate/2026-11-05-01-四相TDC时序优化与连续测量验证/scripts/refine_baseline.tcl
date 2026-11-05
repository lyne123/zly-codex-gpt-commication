# 针对实际剩余ILA路径，恢复原流程已使用的未读BRAM写端NO_CHANGE优化。
set_param general.maxThreads 2
set out U:/results/trials/baseline_bram_routing
if {[file exists $out/design.dcp]} {error "禁止覆盖试验DCP"}
file mkdir $out
open_checkpoint T:/results/baseline/design.dcp
set fd [open U:/results/original_ila_pwm_warning_fanin.txt w]
foreach cell [get_cells -hier -filter {NAME =~ u_ila3/*}] {
    set name [get_property NAME $cell]
    if {[string first {shifted_data_in_reg[7][27]_srl8} $name]>=0 || ([string first {G_NMU[4]} $name]>=0 && [string first {probeDelay1_reg[0]} $name]>=0)} {
        foreach pin [get_pins -of_objects $cell -filter {REF_PIN_NAME == D}] {
            puts $fd "$name\t[get_property NAME [all_fanin -flat -startpoints_only -to $pin]]"
        }
    }
}
close $fd
close_design
open_checkpoint U:/results/optimized/baseline/design.dcp
opt_design -bram_power_opt
report_timing_summary -delay_type min_max -report_unconstrained -file $out/after_bram_power_opt.rpt
report_route_status -file $out/after_bram_route_status.rpt
phys_opt_design -placement_opt -routing_opt -critical_cell_opt -critical_pin_opt
report_timing_summary -delay_type min_max -report_unconstrained -file $out/timing_summary.rpt
report_timing -delay_type max -max_paths 50 -path_type full_clock_expanded -file $out/setup_top50.rpt
report_timing -delay_type min -max_paths 50 -path_type full_clock_expanded -file $out/hold_top50.rpt
check_timing -verbose -file $out/check_timing.rpt
report_route_status -file $out/route_status.rpt
write_checkpoint -force $out/design.dcp
close_design
