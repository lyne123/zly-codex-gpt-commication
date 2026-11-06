"""根据H的真实最差路径，对frame_ready的晚到90°输入继续作余因子分解。"""
from pathlib import Path
import re,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
dst=TASK/'variants/H2_late_ready';assert not dst.exists(),'禁止覆盖候选'
text=(TASK/'variants/H_registered_match/tdc_fine_layer.v').read_text(encoding='utf-8')
marker='    wire frame_ready = ready0_d1 & ready90_d2 & ready180_d1 & ready270_to90;'
assert text.count(marker)==1
text=text.replace(marker,marker+'\n    // 0°域三路ready先归约；90°域ready保留到末级选择，避免消耗1.5ns预算。\n    wire early_frame_ready=ready0_d1 & ready90_d2 & ready180_d1;')
pattern=r'(LUT6 #\(\.INIT\(64\x27h[0-9a-f]+\)\) u_(?!output)\w+ \()\.I0\((.*?)\),\.I1\((.*?)\),\.I2\(pack270_to90\[8\]\),\.I3\(pack270_to90\[9\]\),\.I4\((.*?)\),\.I5\(frame_ready\)'
def replacement(m):
    head,no,yes,unclaimed=m.groups()
    return head+f'.I0(early_frame_ready ? ({no}) : ({unclaimed})),.I1(early_frame_ready ? ({yes}) : ({unclaimed})),.I2(pack270_to90[8]),.I3(pack270_to90[9]),.I4({unclaimed}),.I5(ready270_to90)'
text,n=re.subn(pattern,replacement,text);assert n==6,n
old='''                .I0(if_invalid[bit_id]),.I1(if_fall[bit_id]),.I2(if_rise[bit_id]),
                .I3(pack270_to90[8]),.I4(pack270_to90[9]),.I5(frame_ready),.O(guarded_output_types[bit_id]));'''
new='''                .I0(if_invalid[bit_id] & early_frame_ready),.I1(if_fall[bit_id] & early_frame_ready),.I2(if_rise[bit_id] & early_frame_ready),
                .I3(pack270_to90[8]),.I4(pack270_to90[9]),.I5(ready270_to90),.O(guarded_output_types[bit_id]));'''
assert text.count(old)==1;text=text.replace(old,new)
shutil.copytree(TASK/'variants/H_registered_match',dst);(dst/'tdc_fine_layer.v').write_text(text,encoding='utf-8');shutil.copytree(dst,WORK/'H2_late_ready')
print('H2_PREPARED; same truth table and cycles; late ready only at final LUT')
