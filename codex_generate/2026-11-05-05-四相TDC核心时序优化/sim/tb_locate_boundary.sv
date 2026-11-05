`timescale 1ps/1ps
// 仅测试平台穷举原补偿算术，连续送入有效码并覆盖粗计数回卷。
module tb_locate_boundary;
reg clk=0,rst_n=0,valid=0,pol=0;
reg [7:0] code=0;
reg [1:0] index=0;
always #1000 clk=~clk;
wire bv,cv,bt,ct;
wire [20:0] baseline,compensated;
tdc_time_locate #(.COARSE_W(10)) bypass(.clk_500m(clk),.rst_n(rst_n),.edge_valid(valid),.edge_type_q(pol),.chosen_code(code),.sel_index(index),.polarity_conflict(1'b0),.repeat_error(1'b0),.timestamp_valid(bv),.timestamp_edge_type(bt),.timestamp_ps(baseline));
tdc_time_locate #(.COARSE_W(10),.ENABLE_SKEW_COMP(1),
.RISE_OFFSET_0_PS(18'sd36081),.RISE_OFFSET_90_PS(18'sd36011),.RISE_OFFSET_180_PS(18'sd35742),.RISE_OFFSET_270_PS(18'sd35756),
.FALL_OFFSET_0_PS(18'sd36081),.FALL_OFFSET_90_PS(18'sd36011),.FALL_OFFSET_180_PS(18'sd35742),.FALL_OFFSET_270_PS(18'sd35756)) adjusted(.clk_500m(clk),.rst_n(rst_n),.edge_valid(valid),.edge_type_q(pol),.chosen_code(code),.sel_index(index),.polarity_conflict(1'b0),.repeat_error(1'b0),.timestamp_valid(cv),.timestamp_edge_type(ct),.timestamp_ps(compensated));
integer infd,outfd,k;
initial begin
    infd=$fopen("W:/results/LOCATE_BOUNDARY_INPUT.csv","w");outfd=$fopen("W:/results/LOCATE_BOUNDARY_OUTPUT.csv","w");
    $fdisplay(infd,"time_ps,coarse,index,polarity,code");$fdisplay(outfd,"time_ps,polarity,baseline,compensated");
    #2000;rst_n=1;
    for(k=0;k<8320;k=k+1) begin
        @(negedge clk);valid=1;code=k%65;index=(k/65)%4;pol=(k/260)%2;
    end
    @(negedge clk);valid=0;
    // 额外构造上边界：下一拍粗计数1023、下一0°中测2000ps且fine为0。
    while(bypass.coarse_counter!=1022) @(negedge clk);
    valid=1;code=0;index=3;pol=1;
    @(negedge clk);valid=0;
    repeat(8) @(negedge clk);
    $display("LOCATE_BOUNDARY_DONE");$fclose(infd);$fclose(outfd);$finish;
end
always @(posedge clk) if(rst_n && valid)
    $fdisplay(infd,"%0t,%0d,%0d,%0d,%0d",$time,bypass.coarse_counter,index,pol,code);
always @(negedge clk) begin
    if(bv!==cv || (bv && bt!==ct)) $fatal(1,"补偿改变valid或极性时序");
    if(bv) $fdisplay(outfd,"%0t,%0d,%0d,%0d",$time-1000,bt,baseline,compensated);
end
endmodule
