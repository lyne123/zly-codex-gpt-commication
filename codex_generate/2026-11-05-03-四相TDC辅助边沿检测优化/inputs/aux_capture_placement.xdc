# 仅约束新增辅助同步器，缩小四相输入分支的物理偏斜。
# 原PWM分发树、TDL、时钟定义和时序例外均使用原XDC，不在此改写。
foreach phase {0 1 2 3} site {SLICE_X27Y0 SLICE_X28Y0 SLICE_X30Y0 SLICE_X31Y0} {
    foreach regname {pwm_meta_reg pwm_sync_reg} {
        set pattern [format {^u_tdc_fine_layer/g_aux_4phase[./]g_phase\[%d\][./]%s$} $phase $regname]
        set cell [get_cells -quiet -hier -regexp $pattern]
        if {[llength $cell]!=1} {error "无法唯一定位新增辅助同步器：$pattern"}
        set_property LOC $site $cell
    }
}
