# 在布局前执行原默认流程已有的未读TDP端写模式优化；路由后该功能不受支持。
opt_design -bram_power_opt
set fd [open [file join [pwd] bram_mode_after_power_opt.txt] w]
foreach cell [get_cells -hier -filter {REF_NAME == RAMB36E1 && NAME =~ u_ila2/*}] {
    puts $fd "[get_property NAME $cell]\tWRITE_MODE_A=[get_property WRITE_MODE_A $cell]\tPWROPT=[get_property PWROPT_WRITE_MODE_CHANGE_A $cell]"
}
close $fd
