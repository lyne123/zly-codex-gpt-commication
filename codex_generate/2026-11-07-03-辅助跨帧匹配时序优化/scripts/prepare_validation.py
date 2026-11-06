"""复用上一轮激励、分析和组合检查，增加F与候选的全链路逐周期miter。"""
from pathlib import Path
import re,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
PREV=ROOT/'codex_generate/2026-11-07-02-辅助下降沿跨帧匹配验证'
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
ref=WORK/'F_renamed';ref.mkdir(exist_ok=True)
names=['tdc_meas_top','tdc_fine_layer','tdc_phase_tdl_encoder','tdl_edge_candidate','tdc_time_candicate','tdc_time_locate','tdc_time_merge']
for p in (TASK/'reference_F/rtl').glob('*.v'):
    text=p.read_text(encoding='utf-8')
    for name in names:text=re.sub(r'\b'+name+r'\b',name+'_reference',text)
    (ref/p.name).write_text(text,encoding='utf-8')
analyzer=(PREV/'scripts/test_pwm.py').read_text(encoding='utf-8')
analyzer='''"""逐字复用上一轮脉宽/事件ID分析函数，不重新拟合参数。"""
import csv,bisect
from collections import Counter
MOD=2048000
OFFSETS=[36011,35742,35756,36081]
'''+analyzer[analyzer.index('def read(p):'):analyzer.index('def run(args,log):')]+analyzer[analyzer.index('def analyze(case,truth,delay):'):analyzer.index('def main():')]
(TASK/'scripts/pwm_analysis.py').write_text(analyzer,encoding='utf-8')
for name in ['tb_pwm.sv','tb_replay.sv']:
    text=(PREV/'sim'/name).read_text(encoding='utf-8')
    marker='tdc_meas_top `COMPENSATION_PARAMETERS dut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));'
    assert text.count(marker)==1
    text=text.replace(marker,marker+'\ntdc_meas_top_reference `COMPENSATION_PARAMETERS refdut(.sys_clk(sys_clk),.sys_rst_n(sys_rst_n),.pwm_in(pwm_in));\n`include "miter_checks.svh"')
    if name=='tb_replay.sv':
        start=text.index(' force dut.u_tdc_fine_layer.pack0_d1=p0;');end=text.index(' while(!$feof(input_fd))',start)
        text=text[:end]+text[start:end].replace('force dut.','force refdut.')+text[end:]
    (TASK/'sim'/name).write_text(text,encoding='utf-8')
guard=(PREV/'sim/tb_guard_properties.sv').read_text(encoding='utf-8')
marker='integer pat,mask,loc,claim,j,checks=0;'
helper='''
// 组合测试把history与预计算元数据设为同一逻辑状态；真实状态推进由miter另行核对。
function [3:0] prefix;input [3:0] x;begin prefix={|x,|x[2:0],|x[1:0],x[0]};end endfunction
function [3:0] suffix;input [3:0] x;begin suffix={x[3],|x[3:2],|x[3:1],|x};end endfunction
wire [3:0] r_prefix=prefix(rn),f_prefix=prefix(fn),r_suffix=suffix(rp & ~rc),f_suffix=suffix(fp & ~fc);
wire r_single=((rp & ~rc)!=0) && (((rp & ~rc) & ((rp & ~rc)-4'b0001))==0);
wire f_single=((fp & ~fc)!=0) && (((fp & ~fc) & ((fp & ~fc)-4'b0001))==0);
'''
guard=guard.replace(marker,marker+helper)
marker=' for(pat=0;pat<256;pat=pat+1)'
guard=guard.replace(marker,''' force dut.g_aux_4phase.rise_prefix_now=r_prefix;force dut.g_aux_4phase.fall_prefix_now=f_prefix;
 force dut.g_aux_4phase.rise_remaining_previous=r_suffix;force dut.g_aux_4phase.fall_remaining_previous=f_suffix;
 force dut.g_aux_4phase.rise_previous_single_q=r_single;force dut.g_aux_4phase.fall_previous_single_q=f_single;
'''+marker)
(TASK/'sim/tb_guard_properties.sv').write_text(guard,encoding='utf-8')
shutil.copytree(TASK/'sim',WORK/'sim',dirs_exist_ok=True)
print('F_MITER_AND_PRIOR_CHECKS_PREPARED')
