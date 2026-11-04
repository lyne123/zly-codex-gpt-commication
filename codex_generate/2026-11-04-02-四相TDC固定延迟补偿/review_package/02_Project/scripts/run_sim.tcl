# 使用独立工程的正式IP模型或实现后网表，保留所有时序检查。
set root [file join [file dirname [info script]] ..]
if {[info exists ::env(TDC_TASK_ROOT)]} { set root $::env(TDC_TASK_ROOT) }
set variant [lindex $argv 0]
set dataset [lindex $argv 1]
set level [lindex $argv 2]
if {$variant ni {baseline compensated} || $dataset ni {calibration validation smoke} || $level ni {rtl gate}} {
    error "usage: baseline|compensated calibration|validation|smoke rtl|gate"
}
set out [file join $root results $variant ${level}_${dataset}]
file mkdir $out
if {[file exists [file join $out widths.csv]]} { error "Refusing to overwrite measurements" }
open_project [file join $root build ${variant}_ascii tdc_${variant}.xpr]
add_files -fileset sim_1 [file join $root sim tb_tdc.sv]
set_property top tb_tdc [get_filesets sim_1]
set options "-testplusarg STIMULUS=[file join $root sim stimuli ${dataset}.txt] -testplusarg OUTPUT_DIR=$out"
if {$level eq "gate"} {
    set_property verilog_define {GATE_SDF} [get_filesets sim_1]
    append options " -testplusarg SDF=[file join $root results $variant design.sdf]"
}
set_property -dict [list xsim.simulate.xsim.more_options $options] [get_filesets sim_1]
set_property xsim.simulate.runtime all [get_filesets sim_1]
set_property xsim.elaborate.debug_level all [get_filesets sim_1]
if {$level eq "gate"} {
    # launch_simulation还会对同一网表自动注释SDF，故测试平台注释只用于独立命令行方式。
    set_property verilog_define {GATE_NETLIST} [get_filesets sim_1]
    launch_simulation -mode post-implementation -type timing
} else {
    launch_simulation -mode behavioral
}
set manifest [open [file join $out run_manifest.txt] w]
puts $manifest "vivado=[version -short]\nlevel=$level\nvariant=$variant\ndataset=$dataset"
puts $manifest "testbench=[file join $root sim tb_tdc.sv]\nstimulus=[file join $root sim stimuli ${dataset}.txt]"
puts $manifest "timing_checks=enabled\nannotation=Vivado post-implementation timing flow; inspect xelab/xsim logs"
close $manifest
close_sim
close_project
