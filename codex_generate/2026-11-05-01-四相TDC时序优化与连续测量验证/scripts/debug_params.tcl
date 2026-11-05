puts [help list_param]
foreach name [lsort [list_param]] {
    if {[string match chipscope.* $name]} {puts "$name = [get_param $name]"}
}
if {[catch {get_param chipscope.enable_nest_ui} value]} {puts $value} else {puts "enable_nest_ui=$value"}
