`timescale 1ps/1ps
// 参考顶层只保留旧复位门控，测量模块与新顶层相同；重点核对末级复制语义。
`include "compensation_parameters.vh"
module tb_fifo_reset;
reg sys_clk=0,sys_rst_n=0,pwm_in=0;
always #5000 sys_clk=~sys_clk;
tdc_meas_top `COMPENSATION_PARAMETERS dut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
tdc_meas_top_reference `COMPENSATION_PARAMETERS reference_dut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));
integer checks=0,outputs=0,assertions=0,releases=0,i,fd;
initial begin
    fd=$fopen("W:/results/FIFO_RESET_TRACE.csv","w");
    $fdisplay(fd,"time_ps,rst_async_n,original_last_stage,replica,old_write_enable,new_write_enable");
    #137;sys_rst_n=1;
    #1000013;sys_rst_n=0;
    #711;sys_rst_n=1;
    #1234567;sys_rst_n=0;
    #2503;sys_rst_n=1;
    #1876543;sys_rst_n=0;
    #997;sys_rst_n=1;
    #1000000;
    if(outputs==0 || assertions<3 || releases<4) $fatal(1,"复位语义检查没有获得足够活动覆盖");
    $display("FIFO_RESET_PASS checks=%0d outputs=%0d assertions=%0d releases=%0d",checks,outputs,assertions,releases);
    $fclose(fd);$finish;
end
initial begin
    #400000;
    for(i=0;i<110;i=i+1) begin pwm_in=1;#25300;pwm_in=0;#24700;end
end
always @(negedge dut.rst_async_n) assertions=assertions+1;
always @(posedge dut.rst_n_500m) releases=releases+1;
always @(dut.rst_result_fifo_500m or dut.rst_n_500m) begin
    #1;
    if(dut.rst_result_fifo_500m!==dut.rst_n_500m) $fatal(1,"副本改变同步复位释放时序");
end
always @(negedge dut.clk_500m) begin
    if($time>10000) begin
        if({dut.rst_n_500m,dut.result_fifo_wr_en,dut.result_fifo_rd_en,dut.pulse_width_valid,dut.pulse_width_ps}!=={reference_dut.rst_n_500m,reference_dut.result_fifo_wr_en,reference_dut.result_fifo_rd_en,reference_dut.pulse_width_valid,reference_dut.pulse_width_ps}) $fatal(1,"FIFO复位/读写/测量时序与旧顶层不同");
        $fdisplay(fd,"%0t,%0d,%0d,%0d,%0d,%0d",$time,dut.rst_async_n,dut.rst_n_500m,dut.rst_result_fifo_500m,reference_dut.result_fifo_wr_en,dut.result_fifo_wr_en);
        checks=checks+1;
    end
end
always @(negedge sys_clk) begin
    if($time>10000 && {dut.pulse_width_valid_100m,dut.pulse_width_ps_100m}!=={reference_dut.pulse_width_valid_100m,reference_dut.pulse_width_ps_100m}) $fatal(1,"FIFO输出序列或读valid改变");
    if(dut.pulse_width_valid_100m) outputs=outputs+1;
end
endmodule
