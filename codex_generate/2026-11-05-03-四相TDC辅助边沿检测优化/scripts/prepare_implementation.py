"""实现入口的硬门槛：核验已通过的RTL数据及源码；不重算补偿参数。"""
from pathlib import Path
import hashlib,json

ROOT=Path('W:/')

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    cases=['local','fixed253','pwm20_5','pwm20_95','pwm20_50','high2ns','low2ns','high_low2ns']
    checked=[]
    for label,tag in [('l0_d0','r3'),('l1300_d2771','r4')]:
        for name in cases:
            folder=ROOT/'results'/f'rtl_a1_{label}_{name}_{tag}'
            summary=json.loads((folder/'summary.json').read_text(encoding='utf-8'))
            manifest=json.loads((folder/'INPUT_MANIFEST.json').read_text(encoding='utf-8'))
            assert summary['pass_measurement'] and summary['pass_aux'],folder
            for rtl,digest in manifest['rtl_sha256'].items():assert sha(ROOT/'rtl'/rtl)==digest,(folder,rtl)
            checked.append(dict(case=folder.name,summary_sha256=sha(folder/'summary.json'),expected_pulses=summary['expected_pulses'],matched=summary['correct_widths']))
    proof=dict(rtl_stage_pass=True,min_new_boundary_high_low_ps=2000,
               user_scope='用户明确暂不考虑2ns以下脉宽；原3512激励及六异常事件不删改',cases=checked)
    (ROOT/'results/RTL_STAGE_GATE.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2),encoding='utf-8')
    paths=list((ROOT/'rtl').glob('*.v'))+list((ROOT/'inputs/ip').rglob('*.xci'))+[ROOT/'inputs/combine.xdc',ROOT/'inputs/aux_capture_placement.xdc',Path('U:/results/optimized/baseline/design.dcp')]
    (ROOT/'inputs/IMPLEMENTATION_SHA256.json').write_text(json.dumps({str(p):dict(bytes=p.stat().st_size,sha256=sha(p)) for p in paths},ensure_ascii=False,indent=2),encoding='utf-8')
    print('RTL_STAGE_PASS',len(checked),'cases; one Baseline implementation authorized by task sequence')

if __name__=='__main__':main()
