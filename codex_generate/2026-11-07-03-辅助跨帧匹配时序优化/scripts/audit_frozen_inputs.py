"""核对长任务期间生产源码、原始激励、补偿参数和IP配置均未被意外改写。"""
from pathlib import Path
import hashlib,json
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
PREV=ROOT/'codex_generate/2026-11-07-02-辅助下降沿跨帧匹配验证';WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
source=json.loads((TASK/'inputs/SOURCE.json').read_text(encoding='utf-8'))
result=dict(formal_production_unchanged=True,original_data_unchanged=True,IP_configurations_unchanged=True,files={})
for name,digest in source['formal_RTL_sha256'].items():
    actual=sha(ROOT/'fpga_tdc_v3_cal_rtl'/name);assert actual==digest,name;result['files']['production/'+name]=actual
for name in ['TRIGGER_A.csv','frozen_compensation.csv','compensation_params.tcl','combine_AD23.xdc','PWM_INPUT.txt','PWM_TRUTH.csv']:
    actual=sha(TASK/'inputs'/name);assert actual==sha(PREV/'inputs'/name),name;result['files']['inputs/'+name]=actual
for ip in ['clk_wiz_0','fifo_tdc_result','ila_2','ila_3']:
    actual=sha(TASK/f'inputs/ip/{ip}/{ip}.xci')
    assert actual==sha(PREV/f'inputs/ip/{ip}/{ip}.xci'),ip
    assert actual==sha(WORK/f'registered/aux_compensated.srcs/sources_1/ip/{ip}/{ip}.xci'),ip
    result['files'][ip+'.xci']=actual
frozen=json.loads((TASK/'inputs/SDF_INPUT_MANIFEST.json').read_text(encoding='utf-8'))
for name in ['full.txt','full_truth.csv','frozen_event_association.json']:
    actual=sha(TASK/'inputs'/name);assert actual==frozen[name]['sha256'],name;result['files']['inputs/'+name]=actual
(TASK/'results/INPUT_FREEZE_AUDIT.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
print('PRODUCTION_RTL, INPUTS, 8-PARAMETERS, FOUR_IP_XCI_ALL_UNCHANGED')
