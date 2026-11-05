`timescale 1ps/1ps
// 穷举所有高部取值及低部边界，直接比较完整有符号回卷位模式。
module wrap_check #(parameter CW=10)(output reg done=0);
localparam TW=CW+11, AW=(TW+2>20)?TW+2:20;
localparam LW=CW+4, HW=AW-LW;
localparam signed [AW-1:0] M=2000*(1<<CW);
reg signed [AW-1:0] injected,expected;
integer hi,k,low,count=0;
tdc_time_locate #(.COARSE_W(CW)) dut(.clk_500m(1'b0),.rst_n(1'b0),.edge_valid(1'b0),.edge_type_q(1'b0),.chosen_code(8'd0),.sel_index(2'd0),.polarity_conflict(1'b0),.repeat_error(1'b0));
initial begin
    force dut.s4_sum=injected;
    for(hi=-(1<<(HW-1));hi<(1<<(HW-1));hi=hi+1) begin
        for(k=0;k<5;k=k+1) begin
            case(k)
                0:low=0;
                1:low=1;
                2:low=(1<<(LW-1));
                3:low=(1<<LW)-2;
                4:low=(1<<LW)-1;
            endcase
            injected=hi*(1<<LW)+low;
            expected=(injected<0)?(injected+M):(injected>=M)?(injected-M):injected;
            #1;
            if(dut.wrapped_time!==expected) $fatal(1,"回卷不等价 CW=%0d sum=%0d expected=%0d actual=%0d",CW,injected,expected,dut.wrapped_time);
            count=count+1;
        end
    end
    release dut.s4_sum;
    $display("WRAP_EQUIVALENCE_PASS CW=%0d samples=%0d",CW,count);done=1;
end
endmodule
module tb_wrap_equivalence;
wire a,b,c;
wrap_check #(.CW(1)) small_counter(a);
wrap_check #(.CW(8)) default_counter(b);
wrap_check #(.CW(10)) project_counter(c);
initial begin wait(a&&b&&c);$finish;end
endmodule
