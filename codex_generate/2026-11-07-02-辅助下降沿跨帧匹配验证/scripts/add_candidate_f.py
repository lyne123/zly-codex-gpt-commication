"""对E做布尔余因子分解，让较晚的90°包只经过末级选择；不增加状态或延迟。"""
from pathlib import Path
import shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
assert not (TASK/'results/replay/F_factored/RTL_REPLAY.csv').exists(),'已有验证结果，禁止覆盖候选源码'
text=(TASK/'variants/E_guarded/tdc_fine_layer.v').read_text(encoding='utf-8')
marker='    wire frame_ready = ready0_d1 & ready90_d2 & ready180_d1 & ready270_to90;'
assert text.count(marker)==1
text=text.replace(marker,marker+'\n    wire [7:0] guarded_final_types;')
marker='        assign aux_fall_match = base_fall_match | {4{fall_fallback}};'
assert text.count(marker)==1
block='''
        // 270°包在90°时钟产生，到下一0°仅1.5ns；提前计算三个余因子，避免晚到信号穿过全局归约。
        // 与上方E规则完全等价，末级LUT5只选择对应候选类型；没有增加寄存器或跨域采样。
        function [7:0] guarded_types;
            input [7:0] types;
            input [3:0] base_r,base_f;
            input single_r,single_f;
            reg confirmed,has_r,has_f,back_r,back_f;
            integer q;
            begin
                confirmed=0;has_r=0;has_f=0;
                for(q=0;q<4;q=q+1) begin
                    has_r=has_r || types[2*q+:2]==2'b11;
                    has_f=has_f || types[2*q+:2]==2'b10;
                    confirmed=confirmed || (types[2*q+:2]==2'b11 && base_r[q]) ||
                                           (types[2*q+:2]==2'b10 && base_f[q]);
                end
                back_r=!confirmed && has_r && !has_f && single_r;
                back_f=!confirmed && has_f && !has_r && single_f;
                for(q=0;q<4;q=q+1)
                    guarded_types[2*q+:2]=confirm_edge(types[2*q+:2],base_r[q] | back_r,base_f[q] | back_f);
            end
        endfunction
        wire [7:0] if_invalid=guarded_types({pack0_d1[9:8],2'b00,pack180_d1[9:8],pack90_d2[9:8]},base_rise_match,base_fall_match,rise_previous_single,fall_previous_single);
        wire [7:0] if_fall=guarded_types({pack0_d1[9:8],2'b10,pack180_d1[9:8],pack90_d2[9:8]},base_rise_match,base_fall_match,rise_previous_single,fall_previous_single);
        wire [7:0] if_rise=guarded_types({pack0_d1[9:8],2'b11,pack180_d1[9:8],pack90_d2[9:8]},base_rise_match,base_fall_match,rise_previous_single,fall_previous_single);
        genvar bit_id;
        for(bit_id=0;bit_id<8;bit_id=bit_id+1) begin : g_guard_mux
            LUT5 #(.INIT(32'hINIT_VALUE)) u_mux (
                .I0(if_invalid[bit_id]),.I1(if_fall[bit_id]),.I2(if_rise[bit_id]),
                .I3(pack270_to90[8]),.I4(pack270_to90[9]),.O(guarded_final_types[bit_id]));
        end
'''
init=sum(( ((i>>2)&1) if i&16 and i&8 else ((i>>1)&1) if i&16 else i&1)<<i for i in range(32))
text=text.replace(marker,marker+block.replace('INIT_VALUE',f'{init:08x}'))
for j,phase,pack in [(0,90,'pack90_d2'),(1,180,'pack180_d1'),(2,270,'pack270_to90'),(3,0,'pack0_d1')]:
    import re
    pattern=rf'(wire \[1:0\] final_type{phase}\s*=\s*)(confirm_edge\([^;]+\));'
    text,n=re.subn(pattern,rf'\g<1>ENABLE_AUX_4PHASE ? guarded_final_types[{2*j}+:2] : \g<2>;',text)
    assert n==1,(phase,n)
dst=TASK/'variants/F_factored';shutil.copytree(TASK/'original/rtl',dst,dirs_exist_ok=True)
(dst/'tdc_fine_layer.v').write_text(text,encoding='utf-8')
shutil.copytree(dst,ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02/F_factored',dirs_exist_ok=True)
print('F_FACTORED_PREPARED; LUT5_INIT=',hex(init))
