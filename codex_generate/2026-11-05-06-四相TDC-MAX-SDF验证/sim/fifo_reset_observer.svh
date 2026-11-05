// 仅测试平台观察，不改FIFO复位或写入逻辑。
integer fifo_write_fd,fifo_read_fd,reset_fd,orig_cycles=0,replica_cycles=0;
initial begin #1;
  fifo_write_fd=$fopen({output_dir,"/FIFO_WRITES.csv"},"w");
  fifo_read_fd=$fopen({output_dir,"/FIFO_READS.csv"},"w");
  reset_fd=$fopen({output_dir,"/RESET_TRACE.csv"},"w");
  $fdisplay(fifo_write_fd,"time_ps,kind,data,full,busy,measurement_valid");
  $fdisplay(fifo_read_fd,"time_ps,kind,data,empty,busy,output_valid");
  $fdisplay(reset_fd,"time_ps,signal,value,own_clock_cycles,original_Q,replica_Q,MMCM_locked");
end
always @(posedge dut.clk_500m) begin
  if(fifo_write_fd && dut.result_fifo_wr_en)
    $fdisplay(fifo_write_fd,"%0t,result,%0d,%0d,%0d,%0d",$time,dut.pulse_width_ps,dut.result_fifo_full,dut.result_fifo_wr_rst_busy,dut.pulse_width_valid);
  if(fifo_write_fd && dut.error_fifo_wr_en)
    $fdisplay(fifo_write_fd,"%0t,error,%0d,%0d,%0d,%0d",$time,dut.error_event_code,dut.error_fifo_full,dut.error_fifo_wr_rst_busy,dut.error_event_valid);
end
always @(posedge dut.clk_100m) begin
  if(fifo_read_fd && dut.result_fifo_rd_en)
    $fdisplay(fifo_read_fd,"%0t,result,%0d,%0d,%0d,%0d",$time,dut.pulse_width_ps_100m,dut.result_fifo_empty,dut.result_fifo_rd_rst_busy,dut.pulse_width_valid_100m);
  if(fifo_read_fd && dut.error_fifo_rd_en)
    $fdisplay(fifo_read_fd,"%0t,error,%0d,%0d,%0d,%0d",$time,dut.error_code_100m,dut.error_fifo_empty,dut.error_fifo_rd_rst_busy,dut.error_valid_100m);
end
always @(posedge dut.\rst_sync_500m_reg[1] .C_dly) orig_cycles=orig_cycles+1;
always @(posedge dut.rst_result_fifo_500m_reg.C_dly) replica_cycles=replica_cycles+1;
always @(dut.rst_sync_500m[1]) if(reset_fd)
  $fstrobe(reset_fd,"%0t,original,%0d,%0d,%0d,%0d,%0d",$time,dut.rst_sync_500m[1],orig_cycles,dut.rst_sync_500m[1],dut.rst_result_fifo_500m,dut.mmcm_locked);
always @(dut.rst_result_fifo_500m) if(reset_fd)
  $fstrobe(reset_fd,"%0t,replica,%0d,%0d,%0d,%0d,%0d",$time,dut.rst_result_fifo_500m,replica_cycles,dut.rst_sync_500m[1],dut.rst_result_fifo_500m,dut.mmcm_locked);
