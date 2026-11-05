"""交付前核对冻结RTL、八组实际输入、原始CSV和实现文件对应关系。"""
from pathlib import Path
import hashlib
import json
import csv

ROOT=Path(__file__).resolve().parents[1]

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def main():
    state=json.loads((ROOT/'results/analysis_summary.json').read_text(encoding='utf-8'))
    assert state['completed_cases']==8
    frozen=json.loads((ROOT/'inputs/optimized_rtl_sha256.json').read_text(encoding='utf-8'))
    assert all(sha(ROOT/'rtl'/n)==h for n,h in frozen.items())
    formal=ROOT.parents[1]/'fpga_tdc_v3_cal_rtl'
    if formal.exists():assert all(sha(formal/n)==h for n,h in frozen.items())
    config=(ROOT/'results/optimized/compensated/build_metadata.txt').read_text(errors='replace')
    with (ROOT/'results/tdc_skew_calibration.csv').open(encoding='utf-8-sig') as f:
        for row in csv.DictReader(f):assert f"{row['polarity'].upper()}_OFFSET_{row['tdl_phase']}_PS={row['offset_ps']}" in config
    checks=[]
    for phase in ['original','optimized']:
        for variant in ['baseline','compensated']:
            for level in ['rtl','gate']:
                case=ROOT/'results'/phase/variant/f'{level}_validation'
                assert (case/'run_manifest.txt').exists()
                assert sha(case/'stimulus.txt')=='451a2cb59cc0704a9e5ac8454bb983237543705f2c4782789b3067be4d9fa76f'
                inputs=json.loads((case/'input_sha256.json').read_text(encoding='utf-8'))
                assert all(sha(Path(n))==r['sha256'] for n,r in inputs.items()),str(case)
                output_manifest=case/'raw_output_sha256.json'
                if output_manifest.exists():
                    for n,r in json.loads(output_manifest.read_text()).items():assert sha(case/n)==r['sha256']
                checks.append(dict(phase=phase,variant=variant,level=level,input_files=len(inputs),raw_output_manifest_present=output_manifest.exists()))
    bits=[]
    for v,n in [('baseline','Baseline_Optimized.bit'),('compensated','Compensated_Optimized.bit')]:
        p=ROOT/'results/optimized'/v/n
        assert p.stat().st_size>1000000
        bits.append(dict(variant=v,file=str(p.relative_to(ROOT)),bytes=p.stat().st_size,sha256=sha(p)))
    assert bits[0]['sha256']!=bits[1]['sha256']
    for name in ['TIMING_ROOT_CAUSE.md','RTL_CHANGE_REVIEW.md','TIMING_BEFORE_AFTER.md','CONTINUOUS_PWM_VALIDATION.md','SDF_VALIDATION.md','OLD_VS_NEW_CALIBRATION.csv','RMS_COMPARISON.csv','FINAL_REPORT.md','REPRODUCE.md','EVIDENCE_LIMITATIONS.md']:
        assert (ROOT/name).stat().st_size>0,name
    result=dict(eight_case_inputs_verified=True,rtl_frozen_hashes_verified=True,cases=checks,bits=bits,experimental_acceptance=json.loads((ROOT/'results/final_acceptance.json').read_text()))
    (ROOT/'results/DELIVERY_VERIFICATION.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))

if __name__=='__main__':main()
