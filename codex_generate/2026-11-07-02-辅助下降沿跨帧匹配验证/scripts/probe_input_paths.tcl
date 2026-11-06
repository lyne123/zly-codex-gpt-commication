# 只读上一轮真实Debug DCP的输入到采样端点传播，不修改约束或实现。
set_param general.maxThreads 1
set work [file dirname [file normalize [info script]]]
set out $work/input_paths
file mkdir $out
open_checkpoint $work/reference_debug.dcp
update_timing -full
set targets {}
foreach c [get_cells -hier -filter {NAME =~ u_tdc_fine_layer/* && IS_PRIMITIVE}] {
    set name [get_property NAME $c]
    if {[string match *pwm_meta_reg $name] || [regexp {u_tdl(0|90|180|270)/thermo_q_reg\[(0|63)\]$} $name]} {
        lappend targets [get_pins -of_objects $c -filter {REF_PIN_NAME == D}]
    }
}
set f [open $out/INPUT_PATHS.csv w]
puts $f "transition,delay_type,delay_ns,logic_ns,net_ns,startpoint,endpoint"
set index 0
foreach target $targets {
    foreach type {max min} {
        foreach edge {rise fall} {
            set paths [get_timing_paths -quiet -${edge}_from [get_ports pwm_in] -to $target -delay_type $type -max_paths 1]
            if {![llength $paths]} {puts $f "$edge,$type,,,,unavailable,$target";continue}
            set p [lindex $paths 0]
            puts $f "$edge,$type,[get_property DATAPATH_DELAY $p],[get_property DATAPATH_LOGIC_DELAY $p],[get_property DATAPATH_NET_DELAY $p],[get_property STARTPOINT_PIN $p],[get_property ENDPOINT_PIN $p]"
            report_timing -of_objects $p -input_pins -file $out/path_[incr index].rpt
        }
    }
}
close $f
close_design
puts "ACTUAL_DCP_INPUT_PATH_PROBE_COMPLETE targets=[llength $targets]"
