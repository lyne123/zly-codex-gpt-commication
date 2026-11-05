# 只读核查05冻结DCP中的两条CDC-11及FIFO复位链，禁止更改约束或设计。
set_param general.maxThreads 1
open_checkpoint W:/results/compensated/design.dcp
update_timing -full
set out Z:/results
proc props {property objects} {if {![llength $objects]} {return ""};return [join [get_property $property $objects] ;]}
set fd [open $out/CDC_RESET_STRUCTURE.csv w]
puts $fd "cell,reference,ASYNC_REG,INIT,clock,clock_period_ns,D_net,D_drivers,Q_net"
foreach fifo {u_fifo_tdc_result u_fifo_tdc_error} {
    set cells [get_cells -hier -filter "NAME =~ $fifo/*xpm_cdc_sync_rst_inst_wrst/syncstages_ff_reg*"]
    foreach cell [lsort $cells] {
        set name [get_property NAME $cell]
        set clock [get_clocks -quiet -of_objects [get_pins $name/C]]
        set dn [get_nets -of_objects [get_pins $name/D]]
        set qn [get_nets -of_objects [get_pins $name/Q]]
        set drivers [all_fanin -flat -startpoints_only -to [get_pins $name/D]]
        puts $fd "$name,[get_property REF_NAME $cell],[get_property ASYNC_REG $cell],[get_property INIT $cell],[props NAME $clock],[props PERIOD $clock],[props NAME $dn],[props NAME $drivers],[props NAME $qn]"
    }
}
close $fd
set fd [open $out/CDC_RESET_FANOUT.csv w]
puts $fd "endpoint,reference,clock,clock_period_ns"
foreach pin [lsort [all_fanout -flat -endpoints_only -from [get_pins {rst_sync_500m_reg[1]/Q}]]] {
    set name [get_property NAME $pin]
    if {![string match u_fifo_tdc_* $name]} {continue}
    set cell [get_cells -of_objects $pin]
    set clocks [get_clocks -quiet -of_objects [get_pins -of_objects $cell -filter {REF_PIN_NAME == C || REF_PIN_NAME == CLKARDCLK || REF_PIN_NAME == CLKBWRCLK}]]
    puts $fd "$name,[get_property REF_NAME $cell],[props NAME $clocks],[props PERIOD $clocks]"
}
close $fd
report_cdc -details -file $out/CDC_FROZEN_RECHECK.rpt
close_design
puts "READ_ONLY_CDC_AUDIT_COMPLETE"
