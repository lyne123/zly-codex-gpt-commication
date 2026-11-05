# 每个实现仅编译一次，后续各独立批次直接复用同一个SDF仿真快照。
set root $::env(TDC_TASK_ROOT)
set variant [lindex $argv 0]
set simset [lindex $argv 1]
if {$simset eq ""} { set simset sim_1 }
open_project [file join $root build ${variant}_ascii tdc_${variant}.xpr]
if {![llength [get_filesets -quiet $simset]]} { create_fileset -simset $simset }
add_files -fileset $simset [file join $root sim tb_tdc.sv]
set_property top tb_tdc [get_filesets $simset]
set_property verilog_define {GATE_NETLIST} [get_filesets $simset]
set_property xsim.elaborate.debug_level typical [get_filesets $simset]
launch_simulation -simset $simset -mode post-implementation -type timing -scripts_only
close_project
