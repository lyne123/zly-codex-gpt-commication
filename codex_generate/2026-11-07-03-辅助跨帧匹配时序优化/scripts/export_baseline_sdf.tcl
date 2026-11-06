# 核心时序通过后，只读导出实际AD23生产DCP，用同一3512激励作精度对照。
set_param general.maxThreads 1
set work [file dirname [file normalize [info script]]]
cd $work
set impl [lindex $argv 0]
if {$impl eq ""} {set impl implementation_fifo_reuse2}
if {$impl ni {implementation_closed implementation_H3_physical implementation_H3 implementation_I implementation_I_physical implementation_fifo_reuse2}} {error "未知已验收实现目录"}
set fd [open $work/$impl/TIMING_GATE.txt r]
set gate [read $fd]
close $fd
if {![string match *core_negative_endpoints=0* $gate]} {error "核心时序未通过，不运行SDF对照"}
set out $work/baseline_export
if {[file exists $out]} {error "禁止覆盖Baseline SDF"}
file mkdir $out
open_checkpoint $work/production_AD23.dcp
if {[get_property PACKAGE_PIN [get_ports pwm_in]] ne "AD23"} {error "Baseline引脚不匹配"}
write_verilog -mode timesim -sdf_anno false $out/post_route_timing.v
write_sdf -process_corner slow $out/post_route_max.sdf
close_design
puts "AD23_BASELINE_SDF_EXPORTED_READ_ONLY"
