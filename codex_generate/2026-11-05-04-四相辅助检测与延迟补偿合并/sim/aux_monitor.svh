// 只读记录辅助事件位置、跨相位采样与每相确认结果。
integer aux_fd;
initial begin
    #1;
    aux_fd=$fopen({output_dir,"/aux_trace.csv"},"w");
    $fdisplay(aux_fd,"time_ps,rise_slots,fall_slots,samples,armed,rise_match,fall_match,pack0,pack90,pack180,pack270,final0,final90,final180,final270");
end
`ifdef FOUR_PHASE_MONITOR
always @(negedge dut.clk_500m) if(aux_fd && $time>5000000)
    $fdisplay(aux_fd,"%0t,%0d,%0d,%0d,%0d,%0d,%0d,%h,%h,%h,%h,%0d,%0d,%0d,%0d",$time,
        dut.u_tdc_fine_layer.g_aux_4phase.aux_rise_slots,dut.u_tdc_fine_layer.g_aux_4phase.aux_fall_slots,
        dut.u_tdc_fine_layer.g_aux_4phase.ordered_samples,dut.u_tdc_fine_layer.g_aux_4phase.armed,
        dut.u_tdc_fine_layer.aux_rise_match,dut.u_tdc_fine_layer.aux_fall_match,
        dut.u_tdc_fine_layer.pack0_d1,dut.u_tdc_fine_layer.pack90_d2,dut.u_tdc_fine_layer.pack180_d1,dut.u_tdc_fine_layer.pack270_to90,
        dut.u_tdc_fine_layer.final_type0,dut.u_tdc_fine_layer.final_type90,dut.u_tdc_fine_layer.final_type180,dut.u_tdc_fine_layer.final_type270);
`endif
