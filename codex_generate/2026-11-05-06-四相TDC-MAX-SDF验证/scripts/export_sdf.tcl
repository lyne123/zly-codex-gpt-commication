# 只读打开05轮最终路由DCP，不综合、不布局布线、不写DCP、不生成BIT。
set_param general.maxThreads 2
set root Z:/
if {![file exists $root/results/FREEZE_CHECK.json]} {error "冻结输入核验尚未通过"}
if {[file exists $root/netlist/post_route_max.sdf]} {error "禁止覆盖已导出的SDF证据"}
puts "ACTUAL_WRITE_SDF_OPTIONS_BEGIN"
help write_sdf
puts "ACTUAL_WRITE_SDF_OPTIONS_END"
puts "ACTUAL_WRITE_VERILOG_OPTIONS_BEGIN"
help write_verilog
puts "ACTUAL_WRITE_VERILOG_OPTIONS_END"
open_checkpoint W:/results/compensated/design.dcp
set fd [open $root/inputs/DCP_PRIMITIVES.csv w]
puts $fd "primitive,instances"
foreach ref [lsort -unique [get_property REF_NAME [get_cells -hier -filter {IS_PRIMITIVE == 1}]]] {
    puts $fd "$ref,[llength [get_cells -hier -filter "IS_PRIMITIVE == 1 && REF_NAME == $ref"]]"
}
close $fd
write_sdf -process_corner slow $root/netlist/post_route_max.sdf
write_verilog -mode timesim -sdf_anno false $root/netlist/post_route_timing.v
close_design
puts "FROZEN_DCP_SDF_EXPORT_COMPLETE"
