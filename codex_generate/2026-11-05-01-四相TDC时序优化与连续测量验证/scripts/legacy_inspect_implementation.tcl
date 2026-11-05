# 只读检查冻结DCP；临时输入参考仅用于显示物理数据路径，绝不作为时序签核预算。
set root $::env(TDC_TASK_ROOT)
set variant [lindex $argv 0]
set out [file join $root results $variant]
open_checkpoint [file join $out design.dcp]
set fd [open [file join $out frontend_structure.csv] w]
puts $fd "name,ref_name,loc,bel"
foreach cell [lsort [get_cells -hier -filter {NAME =~ u_tdc_fine_layer/*}]] {
    set name [get_property NAME $cell]
    if {[string match *g_carry* $name] || [string match *thermo_q_reg* $name] || [string match *g_pwm_dist* $name]} {
        puts $fd "$name,[get_property REF_NAME $cell],[get_property LOC $cell],[get_property BEL $cell]"
    }
}
close $fd
set fd [open [file join $out frontend_route.tsv] w]
puts $fd "name\troute"
foreach net [lsort [get_nets -hier -filter {NAME =~ u_tdc_fine_layer/* || NAME =~ clk_500m* || NAME =~ pwm_in*}]] {
    puts $fd "[get_property NAME $net]\t[get_property ROUTE $net]"
}
close $fd
# 原XDC未给PWM输入设延迟。临时0ps参考用于提取route/cell数据，报告slack不可用于签核。
set_input_delay -clock [get_clocks sys_clk] 0 [get_ports pwm_in]
foreach phase {0 90 180 270} {
    set targets [get_pins -hier -filter "NAME =~ u_tdc_fine_layer/u_tdl${phase}/thermo_q_reg*/D"]
    report_timing -from [get_ports pwm_in] -to $targets -max_paths 64 -nworst 64 -path_type full_clock_expanded -input_pins -nets -file [file join $out pwm_distribution_${phase}_diagnostic.rpt]
}
close_design
