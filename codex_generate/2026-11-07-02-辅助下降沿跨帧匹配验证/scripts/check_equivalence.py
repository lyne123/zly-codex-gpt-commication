"""余因子候选必须保持E的逐事件输出，且只允许细测确认源码变化。"""
from pathlib import Path
import hashlib,json
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
checks=[]
for folder,names in [('replay',['RTL_REPLAY.csv'])]+[(f'pwm_lut{d}',['candidate.csv','timestamps.csv','widths.csv','errors.csv','ASSOCIATION.csv','MEASUREMENTS.csv']) for d in (0,250,500)]:
    for name in names:
        if folder=='replay':a=TASK/'results/replay/E_guarded'/name;b=TASK/'results/replay/F_factored'/name
        else:
            d=folder.split('lut')[1];a=TASK/f'results/pwm/E_guarded_lut{d}'/name;b=TASK/f'results/pwm/F_factored_lut{d}'/name
        assert a.read_bytes()==b.read_bytes(),(a,b)
        checks.append(str(b.relative_to(TASK)))
for p in (TASK/'original/rtl').glob('*.v'):
    if p.name!='tdc_fine_layer.v':assert p.read_bytes()==(TASK/'variants/F_factored'/p.name).read_bytes()
    assert p.read_bytes()==(ROOT/'fpga_tdc_v3_cal_rtl'/p.name).read_bytes(),'验收前正式RTL不应变化'
(TASK/'results/E_F_EQUIVALENCE.json').write_text(json.dumps(dict(byte_equal_CSV=checks,all_equal=True,
    formal_RTL_unchanged_at_gate=True,only_candidate_changed='tdc_fine_layer.v'),ensure_ascii=False,indent=2),encoding='utf-8')
print('E_F_BYTE_EQUIVALENCE_PASS',len(checks))
