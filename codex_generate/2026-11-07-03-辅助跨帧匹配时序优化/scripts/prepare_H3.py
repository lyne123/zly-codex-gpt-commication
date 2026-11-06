"""仅对物理优化后剩余的early ready归约同拍寄存，保持F全部输出周期。"""
from pathlib import Path
import shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
dst=TASK/'variants/H3_ready_precompute';assert not dst.exists(),'禁止覆盖候选'
text=(TASK/'variants/H2_late_ready/tdc_fine_layer.v').read_text(encoding='utf-8')
text=text.replace('    reg ready180_d1;','    reg ready180_d1;\n    reg early_frame_ready_q;')
text=text.replace("            ready180_d1 <= 1'b0;","            ready180_d1 <= 1'b0;\n            early_frame_ready_q <= 1'b0;")
text=text.replace('            ready180_d1 <= ready180_to90;','''            ready180_d1 <= ready180_to90;
            // 等于本拍更新后的ready0_d1 & ready90_d2 & ready180_d1，不多打一拍。
            early_frame_ready_q <= ready0 & ready90_d1 & ready180_to90;''')
text=text.replace('wire early_frame_ready=ready0_d1 & ready90_d2 & ready180_d1;','wire early_frame_ready=early_frame_ready_q;')
assert text.count('early_frame_ready_q <=')==2
shutil.copytree(TASK/'variants/H2_late_ready',dst);(dst/'tdc_fine_layer.v').write_text(text,encoding='utf-8');shutil.copytree(dst,WORK/'H3_ready_precompute')
print('H3_PREPARED; early ready exactly retimed from existing ready input expressions; added cycles=0')
