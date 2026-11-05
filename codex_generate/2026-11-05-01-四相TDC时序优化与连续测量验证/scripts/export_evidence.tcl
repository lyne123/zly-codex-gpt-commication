# 从当前同一物理设计导出全部证据，不重新综合或修改参数。
write_checkpoint -force $out/design.dcp
report_timing_summary -delay_type min_max -report_unconstrained -file $out/timing_summary.rpt
report_timing -delay_type max -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/setup_top50.rpt
report_timing -delay_type min -max_paths 50 -path_type full_clock_expanded -input_pins -file $out/hold_top50.rpt
set fd [open $out/path_properties.txt w]
foreach path [get_timing_paths -delay_type max -max_paths 50] {
    foreach prop [list_property $path] {puts $fd "$prop\t[get_property $prop $path]"}
    puts $fd END_PATH
}
close $fd
report_design_analysis -max_paths 50 -setup -file $out/design_analysis_setup.rpt
check_timing -verbose -file $out/check_timing.rpt
report_utilization -file $out/utilization.rpt
report_clock_interaction -file $out/clock_interaction.rpt
report_clocks -file $out/clocks.rpt
report_exceptions -file $out/exceptions.rpt
report_cdc -details -file $out/cdc.rpt
report_drc -file $out/drc.rpt
report_route_status -file $out/route_status.rpt
report_bus_skew -file $out/bus_skew.rpt
if {[file exists [file join [pwd] tight_setup_hold_pins.txt]]} {
    file copy [file join [pwd] tight_setup_hold_pins.txt] $out/routing_tight_setup_hold_pins.txt
}
set fd [open $out/frontend_structure.csv w]
puts $fd "name,ref_name,loc,bel"
foreach cell [lsort [get_cells -hier -filter {NAME =~ u_tdc_fine_layer/*}]] {
    set name [get_property NAME $cell]
    if {[string match *g_carry* $name] || [string match *thermo_q_reg* $name] || [string match *g_pwm_dist* $name]} {
        puts $fd "$name,[get_property REF_NAME $cell],[get_property LOC $cell],[get_property BEL $cell]"
    }
}
close $fd
set fd [open $out/frontend_route.tsv w]
puts $fd "name\troute"
foreach net [lsort [get_nets -hier -filter {NAME =~ u_tdc_fine_layer/* || NAME =~ clk_500m* || NAME =~ pwm_in*}]] {
    puts $fd "[get_property NAME $net]\t[get_property ROUTE $net]"
}
close $fd
write_verilog -force -mode timesim -sdf_anno true $out/design.v
write_sdf -force -process_corner slow $out/design.sdf
set bitname [expr {$variant eq "baseline" ? "Baseline_Optimized.bit" : "Compensated_Optimized.bit"}]
if {![info exists export_bitstream] || $export_bitstream} {write_bitstream -force $out/$bitname}
set fd [open $out/build_metadata.txt w]
puts $fd "vivado=[version -short]\npart=xc7k325tffg900-2\nvariant=$variant\nfrequency_mhz=500\nsynthesis=Flow_PerfOptimized_high\nimplementation=Performance_ExplorePostRoutePhysOpt\npost_route_physopt=AggressiveExplore\ncorner=slow/MAX\nadded_frontend_cycles=1"
puts $fd "generics=$applied_generics"
if {[info exists flow_notes]} {puts $fd "flow_notes=$flow_notes"}
close $fd
if {$variant eq "compensated"} {file copy $root/results/calibration_params.tcl $out/parameters_used.tcl}
close_design
