# 仅约束报告已确认的ILA内部计数/复位扇入，不涉及测量TDL。
if {![llength [get_pblocks -quiet pblock_ila_counter_local]]} {
    create_pblock pblock_ila_counter_local
    resize_pblock [get_pblocks pblock_ila_counter_local] -add {SLICE_X13Y16:SLICE_X20Y25}
    add_cells_to_pblock [get_pblocks pblock_ila_counter_local] [get_cells -hier -filter {NAME =~ u_ila2/inst/ila_core_inst/u_ila_cap_ctrl/u_cap_addrgen/* || NAME =~ u_ila2/inst/ila_core_inst/basic_trigger_reg*}]
}
