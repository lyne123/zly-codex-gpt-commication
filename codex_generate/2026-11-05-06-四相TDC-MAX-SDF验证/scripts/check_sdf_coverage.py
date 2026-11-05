"""对SDF请求项、仿真器严格注释诊断和冻结来源交叉核验，不混用模型总弧覆盖率。"""
from pathlib import Path
from collections import Counter
import hashlib,json,re
ROOT=Path('Z:/')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    sdf=ROOT/'netlist/post_route_max.sdf';net=ROOT/'netlist/post_route_timing.v';text=sdf.read_text(encoding='utf-8')
    counts={k:len(re.findall(r'\('+k+r'\b',text)) for k in ['CELL','INSTANCE','PATHPULSE','IOPATH','INTERCONNECT','SETUPHOLD','WIDTH','PERIOD','RECREM']}
    instances=re.findall(r'\(INSTANCE\s+([^)]*)\)',text);assert len(instances)==counts['CELL'] and len(set(instances))==len(instances)
    checks=sum(counts[k] for k in ['SETUPHOLD','WIDTH','PERIOD','RECREM'])
    log=(ROOT/'logs/sdf_annotation_xsim.log').read_text(encoding='utf-8',errors='replace')
    native_success='SDF backannotation was successful' in log and 'for root module "/tb_tdc/dut"' in log
    warnings=[line for line in log.splitlines() if re.search(r'\b(?:ERROR|WARNING):',line)]
    cmd=(ROOT/'build/xsim/compile.bat').read_text(encoding='ascii')
    forbidden=['--notimingchecks','--nospecify','--nosdfinterconnectdelays','--sdfnoerror','--sdfnowarn']
    no_disabled=all(x not in cmd for x in forbidden)
    original=json.loads((ROOT/'inputs/SOURCE_MANIFEST.json').read_text())
    dcp=Path(original['sole_DCP_source']);unchanged=sha(dcp)==original['files']['results/compensated/design.dcp']['sha256']
    model_attempts=[]
    for p in sorted((ROOT/'logs').glob('sdf_annotation*.log')):
        if 'unannotated' in p.name or p.name=='sdf_annotation_xsim.log':continue
        t=p.read_text(encoding='utf-8',errors='replace')
        model_attempts.append(dict(log=p.name,errors=len(re.findall(r'\*\* Error',t)),interconnect_not_connected=t.count('vsim-SDF-16107'),negative_zeroing_messages=t.count('Setting negative limit to zero')+t.count('negative limits were zeroed'),passed_for_acceptance=False))
    result=dict(annotation_pass=native_success and not warnings and no_disabled and unchanged,accepted_simulator='XSim 2022.2',sole_DCP_sha256=sha(dcp),SDF_sha256=sha(sdf),netlist_sha256=sha(net),SDF_version='3.0',timescale='1ps',corner='slow/MAX',SDF_generated=True,netlist_internal_sdf_annotations=net.read_text().count('$sdf_annotate'),external_annotation='/tb_tdc/dut once via xelab --sdfmax',SDF_construct_counts=counts,unique_SDF_instances_requested=len(instances),root_instances=sum(not x.strip() for x in instances),requested_timing_checks=checks,strict_global_annotation_success=native_success,unmatched_instance_path_or_check_diagnostics=warnings,zero_unmatched_diagnostics=True if not warnings else False,success_counts_interpretation='SDF请求项精确计数，与XSim严格全局注释成功且零缺失/路径/端口/检查诊断交叉核对；工具未提供逐条成功计数，不冒称逐条读回。',accepted_SDF_instances_inferred=len(instances) if native_success and not warnings else None,accepted_SDF_IOPATHs_inferred=counts['IOPATH'] if native_success and not warnings else None,accepted_SDF_INTERCONNECTs_inferred=counts['INTERCONNECT'] if native_success and not warnings else None,accepted_SDF_timing_checks_inferred=checks if native_success and not warnings else None,timing_checks_enabled=no_disabled,source_DCP_unchanged=unchanged,ModelSim_attempts_preserved=model_attempts,ModelSim_raw_percentage_note='68.94%/36.10%是原语完整specify对象分母，不是SDF请求项缺失率；ModelSim未用于验收是因为核心互连未匹配和负限制自动归零。',runtime_SDF_effect_verification='待完整仿真后用只读路径/时钟观测交叉确认')
    (ROOT/'results/SDF_COVERAGE.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps({k:result[k] for k in ['annotation_pass','accepted_simulator','SDF_construct_counts','strict_global_annotation_success','timing_checks_enabled']},ensure_ascii=False,indent=2))
    assert result['annotation_pass'] and result['netlist_internal_sdf_annotations']==0
if __name__=='__main__':main()
