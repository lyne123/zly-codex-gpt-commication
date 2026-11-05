# 核对优化后剩余Setup失败的逻辑扇出，区分只读调试核与测量数据通路。
set_param general.maxThreads 2
set root U:/
foreach variant {baseline compensated} {
    set dir $root/results/optimized/$variant
    if {[file exists $dir/negative_setup_reachability.csv]} {continue}
    open_checkpoint $dir/design.dcp
    update_timing -full
    set fd [open $dir/negative_setup_reachability.csv w]
    puts $fd "slack_ns,startpoint,endpoint,failed_cell,measurement_fifo_reachable_count,measurement_fifo_endpoints"
    foreach path [get_timing_paths -delay_type max -slack_lesser_than 0 -max_paths 1000] {
        set pin [get_property ENDPOINT_PIN $path]
        set cell [get_cells -of_objects [get_pins $pin]]
        if {[llength $cell]!=1} {error "无法唯一定位失败端点：$pin"}
        set outputs [get_pins -of_objects $cell -filter {DIRECTION == OUT}]
        set reached {}
        if {[llength $outputs]} {
            foreach end [all_fanout -flat -endpoints_only -from $outputs] {
                set name [get_property NAME $end]
                if {[string match u_tdc_* $name] || [string match u_fifo_tdc_* $name]} {lappend reached $name}
            }
        }
        set reached [lsort -unique $reached]
        puts $fd "[get_property SLACK $path],[get_property STARTPOINT_PIN $path],$pin,[get_property NAME $cell],[llength $reached],[join $reached ;]"
    }
    close $fd
    close_design
}
