`timescale 1ps/1ps
// 独立检查实际候选RTL的保护条件；不把辅助事件注入位置当作物理延迟模型。
module tb_guard_properties;
reg clk=0,rst=0;
always #1000 clk=~clk;
reg [9:0] packs[0:3];
wire [9:0] p0=packs[3],p270=packs[2],p180=packs[1],p90=packs[0];
reg [3:0] rn=0,fn=0,rp=0,fp=0,rc=0,fc=0;
wire [31:0] codes;wire [3:0] valid;wire [7:0] polarity;wire ready;
tdc_fine_layer dut(.clk_500m(clk),.clk_500m_deg90(clk),.clk_500m_deg180(clk),.clk_500m_deg270(clk),
 .rst_n(rst),.pwm_in(1'b0),.all_fine_code(codes),.sync_edge_valid(valid),.sync_edge_polarity(polarity),.sync_valid(ready));
integer pat,mask,loc,claim,j,checks=0;
// 组合测试把history与预计算元数据设为同一逻辑状态；真实状态推进由miter另行核对。
function [3:0] prefix;input [3:0] x;begin prefix={|x,|x[2:0],|x[1:0],x[0]};end endfunction
function [3:0] suffix;input [3:0] x;begin suffix={x[3],|x[3:2],|x[3:1],|x};end endfunction
wire [3:0] r_prefix=prefix(rn),f_prefix=prefix(fn),r_suffix=suffix(rp & ~rc),f_suffix=suffix(fp & ~fc);
wire r_single=((rp & ~rc)!=0) && (((rp & ~rc) & ((rp & ~rc)-4'b0001))==0);
wire f_single=((fp & ~fc)!=0) && (((fp & ~fc) & ((fp & ~fc)-4'b0001))==0);

reg [7:0] orig_types,new_types;
reg [3:0] orig_r,orig_f;
initial begin
 #10000;rst=1;#100000;
 force dut.pack90_d2=p90;force dut.pack180_d1=p180;
 force dut.pack270_to90=p270;force dut.pack0_d1=p0;
 force dut.g_aux_4phase.rise_history[2]=rn;force dut.g_aux_4phase.fall_history[2]=fn;
 force dut.g_aux_4phase.rise_history[3]=rp;force dut.g_aux_4phase.fall_history[3]=fp;
 force dut.g_aux_4phase.rise_claimed_previous=rc;force dut.g_aux_4phase.fall_claimed_previous=fc;
 force dut.g_aux_4phase.rise_prefix_now=r_prefix;force dut.g_aux_4phase.fall_prefix_now=f_prefix;
 force dut.g_aux_4phase.rise_remaining_previous=r_suffix;force dut.g_aux_4phase.fall_remaining_previous=f_suffix;
 force dut.g_aux_4phase.rise_previous_single_q=r_single;force dut.g_aux_4phase.fall_previous_single_q=f_single;
 force dut.g_aux_4phase.base_rise_match={r_prefix[3],(r_prefix[2]|r_suffix[3]),(r_prefix[1]|r_suffix[2]),(r_prefix[0]|r_suffix[1])};
 force dut.g_aux_4phase.base_fall_match={f_prefix[3],(f_prefix[2]|f_suffix[3]),(f_prefix[1]|f_suffix[2]),(f_prefix[0]|f_suffix[1])};
 for(pat=0;pat<256;pat=pat+1) for(mask=0;mask<16;mask=mask+1)
 for(loc=0;loc<4;loc=loc+1) for(claim=0;claim<16;claim=claim+1) begin
  for(j=0;j<4;j=j+1) packs[j]=(((pat>>(2*j)) & 32'd3)<<8) | 32'd13;
  rn=0;fn=0;rp=0;fp=0;rc=claim;fc=claim;
  case(loc) 0:rn=mask;1:fn=mask;2:rp=mask;3:fp=mask;endcase
  #1;
  orig_r=dut.g_aux_4phase.base_rise_match;orig_f=dut.g_aux_4phase.base_fall_match;
  orig_types=0;
  for(j=0;j<4;j=j+1) begin
   if(packs[j][9:8]==3 && orig_r[j]) orig_types[2*j+:2]=3;
   if(packs[j][9:8]==2 && orig_f[j]) orig_types[2*j+:2]=2;
  end
  new_types={dut.final_type0,dut.final_type270,dut.final_type180,dut.final_type90};
  for(j=0;j<4;j=j+1)
   if(new_types[2*j+:2]!==dut.confirm_edge(packs[j][9:8],dut.aux_rise_match[j],dut.aux_fall_match[j])) $fatal(1,"余因子实现与E原式不等价");
  if(orig_types!=0 && orig_types!==new_types) $fatal(1,"原有效帧被改变");
  if((loc<2 || ((mask & ~claim)==0)) && orig_types!==new_types) $fatal(1,"无前帧可用事件却产生回退");
  if(dut.g_aux_4phase.raw_has_rise && dut.g_aux_4phase.raw_has_fall && orig_types!==new_types) $fatal(1,"混合极性发生推测匹配");
  if(new_types!=orig_types && ((mask & ~claim)==0 || (((mask & ~claim)&((mask & ~claim)-1))!=0))) $fatal(1,"多事件或已归属事件被回退");
  checks=checks+1;
 end
 $display("GUARD_PROPERTIES_PASS cases=%0d",checks);$finish;
end
endmodule
