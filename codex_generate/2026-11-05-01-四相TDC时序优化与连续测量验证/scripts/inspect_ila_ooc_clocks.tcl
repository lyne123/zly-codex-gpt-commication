# 从真实OOC检查点确认最终生效时钟，不仅依赖生成XDC文本。
set_param general.maxThreads 1
set root U:/
set out $root/inputs/ILA_OOC_TIMING_EVIDENCE
foreach variant {baseline compensated} {
    if {$variant eq "baseline"} {set dcp $root/inputs/baseline_synthesis_products/ila_2.dcp} else {set dcp $root/inputs/registered_ip_products/ila_2/ila_2.dcp}
    open_checkpoint $dcp
    report_clocks -file $out/${variant}_ila_2_ooc_clocks.rpt
    report_timing_summary -delay_type min_max -report_unconstrained -file $out/${variant}_ila_2_ooc_timing.rpt
    foreach clk [get_clocks] {puts "ACTUAL_OOC_CLOCK $variant [get_property NAME $clk] period_ns=[get_property PERIOD $clk]"}
    close_design
}
