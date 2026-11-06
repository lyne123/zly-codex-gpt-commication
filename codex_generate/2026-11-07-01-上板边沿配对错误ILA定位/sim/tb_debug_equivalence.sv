`timescale 1ns/1ps
// 比较原/调试配对模块，并核对触发、计数器及影子总线；不模拟真实TDL精度。
module tb_debug_equivalence;
reg clk_500m=0; always #1 clk_500m=~clk_500m;
reg rst_n_500m=0;
reg timestamp_valid=0, timestamp_edge_type=0;
reg [20:0] timestamp_ps=0;
wire pulse_width_valid, error_event_valid;
wire [20:0] pulse_width_ps;
wire [3:0] error_event_code;
wire debug_rise_pending,debug_in_range;
wire [20:0] debug_rise_timestamp;
wire old_valid,old_error;
wire [20:0] old_width;
wire [3:0] old_code;
tdc_time_merge #(.COARSE_W(10)) dut(
 .clk_500m(clk_500m),.rst_n(rst_n_500m),.timestamp_valid(timestamp_valid),
 .timestamp_edge_type(timestamp_edge_type),.timestamp_ps(timestamp_ps),
 .pulse_width_valid(pulse_width_valid),.pulse_width_ps(pulse_width_ps),
 .error_valid(error_event_valid),.error_code(error_event_code),
 .debug_rise_pending(debug_rise_pending),.debug_in_range(debug_in_range),
 .debug_rise_timestamp(debug_rise_timestamp));
tdc_time_merge_original #(.COARSE_W(10)) ref_dut(
 .clk_500m(clk_500m),.rst_n(rst_n_500m),.timestamp_valid(timestamp_valid),
 .timestamp_edge_type(timestamp_edge_type),.timestamp_ps(timestamp_ps),
 .pulse_width_valid(old_valid),.pulse_width_ps(old_width),.error_valid(old_error),.error_code(old_code));
reg [39:0] debug_raw_packets=40'h123456789a;
reg [63:0] debug_aux=64'h123456789abcdef0;
reg [7:0] debug_final_types=8'hab;
reg [31:0] all_fine_code=0;
reg [3:0] sync_edge_valid=4'hf;
reg [7:0] sync_edge_polarity=8'haa;
reg sync_valid=1,debug_frame_ready=1,mmcm_locked=1;
reg error_fifo_overflow=0,result_fifo_overflow=0,repeat_error=0,polarity_conflict=0;
reg edge_valid=1,edge_type_q=0;
reg [7:0] chosen_code=32;
reg [1:0] sel_index=2;
`include "debug_top_fragment.vh"
integer cycles=0, expected_a=0,expected_b=0, errors_a=0,errors_b=0;
reg next_a,next_b;
always @(posedge clk_500m) begin
    if (!rst_n_500m) begin expected_a=0;expected_b=0; end
    else begin
        if (debug_trigger_a) expected_a=expected_a+1;
        if (debug_trigger_b) expected_b=expected_b+1;
        next_a=timestamp_valid && debug_in_range && timestamp_edge_type && debug_rise_pending;
        next_b=timestamp_valid && debug_in_range && !timestamp_edge_type && !debug_rise_pending;
        #0.001;
        if (debug_trigger_a !== next_a || debug_trigger_b !== next_b) $fatal(1,"触发条件与原配对条件不等价");
        if (debug_trigger_a) errors_a=errors_a+1;
        if (debug_trigger_b) errors_b=errors_b+1;
    end
end
always @(negedge clk_500m) if (rst_n_500m) begin
    cycles=cycles+1;
    if ({pulse_width_valid,pulse_width_ps,error_event_valid,error_event_code} !== {old_valid,old_width,old_error,old_code}) $fatal(1,"原/调试配对输出不等价");
    if (debug_double_rise_count !== expected_a || debug_orphan_fall_count !== expected_b) $fatal(1,"错误计数器不等价");
    if (debug_raw_q !== debug_raw_packets || debug_aux_q !== debug_aux) $fatal(1,"影子总线映射不一致");
end
task event_in(input reg v,input reg p,input reg[20:0] ts);
begin @(negedge clk_500m); #0.1; timestamp_valid=v;timestamp_edge_type=p;timestamp_ps=ts;end
endtask
integer i; reg [31:0] rng=32'h12345678;
initial begin
 #0.2;rst_n_500m=1;#0.2;rst_n_500m=0;
 repeat(4) @(negedge clk_500m);#0.1;rst_n_500m=1;
 event_in(1,0,200);event_in(1,1,1000);event_in(1,1,2000);event_in(1,0,52000);
 event_in(1,1,2047000);event_in(1,0,49000);event_in(1,1,100);event_in(1,0,2097000);
 for(i=0;i<12000;i=i+1) begin
   rng=(rng<<1)^((rng[31])?32'h04c11db7:0);
   event_in(rng[0]|rng[1],rng[2],rng[23:3]);
 end
 event_in(0,0,0);repeat(8) @(negedge clk_500m);
 if(errors_a==0 || errors_b==0) $fatal(1,"未覆盖两种触发");
 $display("DEBUG_EQUIVALENCE_PASS cycles=%0d trigger_a=%0d trigger_b=%0d",cycles,errors_a,errors_b);
 $finish;
end
endmodule

module ila_edge_debug(input clk,input [31:0] probe0,input [39:0] probe1,input [63:0] probe2,
 input [39:0] probe3,input [20:0] probe4,input [20:0] probe5,input [63:0] probe6,input [31:0] probe7);
endmodule
