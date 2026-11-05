`timescale 1ps/1ps
// 仅用于RTL功能检查的理想模型；不代表器件延迟，不用于校准或精度结论。
module LUT1 #(parameter [1:0] INIT=2'b10)(input I0,output O);
`ifndef RTL_LUT_DELAY
`define RTL_LUT_DELAY 0
`endif
    // 路径应力模型明确记录延迟，默认0保持上一轮理想模型。
    assign #(`RTL_LUT_DELAY) O=INIT[I0];
endmodule
module CARRY4(output [3:0] CO,output [3:0] O,input CI,CYINIT,input [3:0] DI,S);
    wire first_carry=CI|CYINIT;
    assign #10 CO[0]=S[0]?first_carry:DI[0];
    assign #10 CO[1]=S[1]?CO[0]:DI[1];
    assign #10 CO[2]=S[2]?CO[1]:DI[2];
    assign #10 CO[3]=S[3]?CO[2]:DI[3];
    assign O=S^{CO[2:0],first_carry};
endmodule
module clk_wiz_0(input clk_in1,reset,output reg locked,
    output reg clk_out1,clk_out2,clk_out3,clk_out4,output clk_out5);
    initial begin locked=0; clk_out1=0; clk_out2=0; clk_out3=0; clk_out4=0; end
    always #1000 clk_out1=~clk_out1;
    initial begin #500; forever #1000 clk_out2=~clk_out2; end
    initial begin #1000; forever #1000 clk_out3=~clk_out3; end
    initial begin #1500; forever #1000 clk_out4=~clk_out4; end
    assign clk_out5=clk_in1;
    always @(posedge reset) locked<=0;
    always @(negedge reset) begin #200000; if (!reset) locked<=1; end
endmodule
module fifo_tdc_result(input rst,wr_clk,rd_clk,input [22:0] din,input wr_en,rd_en,
    output reg [22:0] dout,output full,empty,output reg valid,
    output wr_rst_busy,rd_rst_busy);
    // 简单事件队列只验证读写序列；正式CDC验证必须使用厂商IP实现后模型。
    reg [22:0] memory[0:1023];
    integer wr_ptr=0,rd_ptr=0;
    initial begin dout=0; valid=0; end
    assign full=(wr_ptr-rd_ptr)>=1024;
    assign empty=wr_ptr==rd_ptr;
    assign wr_rst_busy=rst;
    assign rd_rst_busy=rst;
    always @(posedge wr_clk or posedge rst)
        if(rst) wr_ptr<=0;
        else if(wr_en&&!full) begin memory[wr_ptr%1024]<=din; wr_ptr<=wr_ptr+1; end
    always @(posedge rd_clk or posedge rst)
        if(rst) begin rd_ptr<=0; dout<=0; valid<=0; end
        else begin
            valid<=rd_en&&!empty;
            if(rd_en&&!empty) begin dout<=memory[rd_ptr%1024]; rd_ptr<=rd_ptr+1; end
        end
endmodule
module ila_2(input clk,input [1:0] probe0,input [20:0] probe1);
endmodule
module ila_3(input clk,input probe0,input [20:0] probe1,input probe2,input [3:0] probe3,input probe4);
endmodule
