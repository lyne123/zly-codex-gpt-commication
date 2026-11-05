# 比较原实现与首个优化实现的真实BRAM模式，定位新增最小周期违例。
set_param general.maxThreads 2
foreach label {original optimized} {
    if {$label eq "original"} {set dcp T:/results/baseline/design.dcp} else {set dcp U:/results/optimized/baseline/design.dcp}
    open_checkpoint $dcp
    set fd [open U:/results/${label}_ila_bram_properties.txt w]
    foreach cell [get_cells -hier -filter {REF_NAME == RAMB36E1 && NAME =~ u_ila2/*}] {
        puts $fd "CELL=[get_property NAME $cell]"
        foreach prop [lsort [list_property $cell]] {puts $fd "$prop\t[get_property $prop $cell]"}
    }
    close $fd
    close_design
}
