# 仅复制实际负裕量路径的ILA源寄存器，不接触TDL、粗计数或候选/配对逻辑。
set nets {}
set fd [open [file join [pwd] ila_forced_replication_sources.txt] w]
foreach cell [get_cells -hier -filter {NAME =~ u_ila2/*}] {
    set name [get_property NAME $cell]
    set select 0
    foreach token {{iwcnt_reg[9]} {iscnt_reg[8]} {capture_qual_ctrl_reg[1]} {en_adv_trigger_reg}} {
        if {[string first $token $name]>=0} {set select 1}
    }
    if {[string first {G_NMU[1]} $name]>=0 && [string first {probeDelay2_reg[0]} $name]>=0} {set select 1}
    if {$select} {
        foreach pin [get_pins -of_objects $cell -filter {REF_PIN_NAME == Q}] {
            foreach net [get_nets -of_objects $pin] {lappend nets $net; puts $fd "$name\t[get_property NAME $net]"}
        }
    }
}
close $fd
set nets [lsort -unique $nets]
if {![llength $nets]} {error "未找到已报告的ILA关键路径源网络"}
phys_opt_design -force_replication_on_nets $nets
