`timescale 1ps/1ps
// 直接核对实际编码器表达式的全部码值/极性，强制仅存在于仿真。
module tb_range;
reg clk=0,rst=0;
always #1000 clk=~clk;
wire [7:0] code;wire ready;wire [1:0] kind;
tdc_phase_tdl_encoder #(.CARRY_NUM(16),.MAX_VALID_TAP(60),.MIN_VALID_TAP(5)) dut(
 .clk(clk),.rst_n(rst),.pwm_in(1'b0),.code(code),.code_valid(ready),.edge_type(kind));
integer c,t,n=0;reg [7:0] raw_code;reg [1:0] raw_type;reg expected;
initial begin
 #20000 rst=1;
 for(t=0;t<4;t=t+1) for(c=0;c<256;c=c+1) begin
  @(negedge clk);raw_code=c;raw_type=t;
  force dut.code_raw=raw_code;force dut.raw_edge_type=raw_type;force dut.encoder_ready=1'b1;
  expected=(t==3 && c>=1 && c<=60)||(t==2 && c>=5 && c<=63);
  #1;if(dut.code_in_range!==expected) $fatal(1,"RANGE_TRUTH_FAIL code=%0d type=%0d",c,t);
  @(posedge clk);#1;
  if(code!==raw_code || kind!==(expected?raw_type:2'b00)) $fatal(1,"RANGE_REGISTER_FAIL");
  n=n+1;
 end
 $display("RANGE_BOUNDARIES_PASS cases=%0d rise=1..60 fall=5..63",n);$finish;
end
endmodule

// 检查旁路整组数据的寄存时序，并穷举合法四相类型、辅助掩码及帧ready。
module tb_bypass;
reg c0=0,c90=0,c180=0,c270=0,rst=0;
always #1000 c0=~c0;
initial begin #500;forever #1000 c90=~c90;end
initial begin #1000;forever #1000 c180=~c180;end
initial begin #1500;forever #1000 c270=~c270;end
wire [31:0] code;wire [3:0] valid;wire [7:0] polarity;wire ready;
tdc_fine_layer #(.ENABLE_AUX_CONFIRM(0)) dut(.clk_500m(c0),.clk_500m_deg90(c90),.clk_500m_deg180(c180),.clk_500m_deg270(c270),.rst_n(rst),.pwm_in(1'b0),.all_fine_code(code),.sync_edge_valid(valid),.sync_edge_polarity(polarity),.sync_valid(ready));
reg [9:0] p0,p90,p180,p270;reg [3:0] aux;reg fr;
reg [31:0] previous_code;reg [7:0] previous_type,current_type;reg previous_ready;
integer x,a,b,i,k,n=0;reg [1:0] typ[0:3];
initial begin
 #20000 rst=1;
 // 等待四相本地复位同步释放后再开始强制输入，避免把复位清零误判为流水错误。
 repeat(10) @(negedge c0);
 for(x=0;x<81;x=x+1) for(a=0;a<16;a=a+1) for(b=0;b<2;b=b+1) begin
  @(negedge c0);k=x;
  for(i=0;i<4;i=i+1) begin typ[i]=(k%3==0)?0:(k%3==1)?2:3;k=k/3;end
  p90={typ[0],8'd30};p180={typ[1],8'd31};p270={typ[2],8'd32};p0={typ[3],8'd13};aux=a;fr=b;
  force dut.pack0_d1=p0;force dut.pack90_d2=p90;force dut.pack180_d1=p180;force dut.pack270_to90=p270;
  force dut.frame_ready=fr;force dut.aux_rise_match=aux;force dut.aux_fall_match=aux;
  current_type={typ[3],typ[2],typ[1],typ[0]};
  @(posedge c0);#1;
  if(n>0) begin
   if(code!==previous_code || ready!==previous_ready || polarity!==(previous_ready?previous_type:8'd0) || valid!==(previous_ready?{previous_type[7],previous_type[5],previous_type[3],previous_type[1]}:4'd0)) $fatal(1,"BYPASS_PIPELINE_OR_AUX_DEPENDENCY_FAIL n=%0d",n);
  end
  previous_code={p0[7:0],p270[7:0],p180[7:0],p90[7:0]};previous_type=current_type;previous_ready=fr;n=n+1;
 end
 $display("BYPASS_PIPELINE_PASS cases=%0d extra_cycles_vs_previous=0",n);$finish;
end
endmodule
