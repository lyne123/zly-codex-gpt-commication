"""核对05提交及唯一冻结DCP；只复制验证输入，不修改设计。"""
from pathlib import Path
import csv,hashlib,json,shutil,subprocess
ROOT=Path('Z:/');SOURCE=Path('W:/');COMMIT='ba978229094a8621b30770177727d8e70b831a74'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    assert subprocess.check_output(['git','-C',str(SOURCE/'github'),'rev-parse','HEAD'],text=True).strip()==COMMIT
    previous={line.split('  ',1)[1]:line.split('  ',1)[0] for line in (SOURCE/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines()}
    names=['results/compensated/design.dcp','results/compensated/design.v','results/compensated/effective_constraints.xdc','results/compensated/timing_summary.rpt','results/compensated/cdc.rpt','sim/stimuli/full.txt','sim/stimuli/full_truth.csv','inputs/frozen_compensation.csv','inputs/compensation_params.tcl']+['rtl/'+p.name for p in (SOURCE/'rtl').glob('*.v')]
    manifest={}
    for name in names:
        p=SOURCE/name;assert sha(p)==previous[name],name
        manifest[name]=dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p))
        gitpath='codex_generate/2026-11-05-05-四相TDC核心时序优化/'+name
        blob=subprocess.check_output(['git','-C',str(SOURCE/'github'),'show',COMMIT+':'+gitpath])
        if name.endswith('design.dcp') or name.endswith('design.v'):
            assert b'oid sha256:'+sha(p).encode()+b'\n' in blob
        else:assert blob==p.read_bytes(),name
    for name in ['full.txt','full_truth.csv']:shutil.copyfile(SOURCE/'sim/stimuli'/name,ROOT/'inputs'/name)
    for name in ['frozen_compensation.csv','compensation_params.tcl']:shutil.copyfile(SOURCE/'inputs'/name,ROOT/'inputs'/name)
    for name in ['cdc.rpt','timing_summary.rpt','effective_constraints.xdc']:shutil.copyfile(SOURCE/'results/compensated'/name,ROOT/'inputs'/('source_'+name))
    shutil.copyfile(Path('X:/inputs/frozen_baseline_association.json'),ROOT/'inputs/frozen_event_association.json')
    formal=Path('D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/fpga_tdc_v3_cal_rtl')
    for p in (SOURCE/'rtl').glob('*.v'):assert sha(p)==sha(formal/p.name)
    (ROOT/'inputs/source_commit.txt').write_text(COMMIT+'\n',encoding='ascii')
    (ROOT/'inputs/stimulus_sha256.txt').write_text(''.join(f'{sha(ROOT/"inputs"/n)}  {n}\n' for n in ['full.txt','full_truth.csv']),encoding='ascii')
    (ROOT/'inputs/SOURCE_MANIFEST.json').write_text(json.dumps(dict(source_commit=COMMIT,sole_DCP_source='W:/results/compensated/design.dcp',files=manifest,formal_RTL_sha256={p.name:sha(p) for p in formal.glob('*.v')},no_RTL_XDC_IP_parameters_modified=True),ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'inputs/full_truth.csv').open(encoding='utf-8-sig') as f:truth=list(csv.DictReader(f))
    assert len(truth)==3512
    (ROOT/'results/FREEZE_CHECK.json').write_text(json.dumps(dict(pass_freeze=True,pulses=3512,edges=7024,source_commit=COMMIT,DCP_sha256=sha(SOURCE/'results/compensated/design.dcp')),indent=2),encoding='utf-8')
    index=formal.parent/'codex_generate/README.md';data=index.read_bytes();name='2026-11-05-06-四相TDC-MAX-SDF验证'
    if name.encode() not in data:
        eol=b'\r\n' if b'\r\n' in data else b'\n';row=f'| 2026-11-05-06 | [四相TDC-MAX-SDF验证]({name}/SDF_VALIDATION.md) |'.encode();pos=data.index(b'\n',data.index(b'| 2026-11-05-05 |'))+1;index.write_bytes(data[:pos]+row+eol+data[pos:])
    print('FROZEN_INPUTS_VERIFIED',len(names),'files; 3512 pulses; sole DCP source',sha(SOURCE/'results/compensated/design.dcp'))
if __name__=='__main__':main()
