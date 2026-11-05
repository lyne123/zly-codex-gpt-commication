"""核对实际注释的SDF/网表哈希及关键单元，流式分类全部时序告警。"""
from pathlib import Path
from collections import Counter
import json
import re
import argparse
import experiment as e

ROOT=Path(__file__).resolve().parents[1]
OLD=ROOT.parent/'2026-11-04-02-四相TDC固定延迟补偿验证'

def audit(phase,variant):
    folder=ROOT/'results'/phase/variant
    if not (folder/'design.sdf').exists():return
    sdf=(folder/'design.sdf').read_text(encoding='utf-8')
    cells={m[2].replace('\\',''):m[1] for m in re.finditer(r'\(CELL\s+\(CELLTYPE "([^"]+)"\)\s+\(INSTANCE ([^)]*)\)',sdf)}
    structure=folder/'frontend_structure.csv'
    rows=e.read_csv(structure)
    inventory=Counter(r['ref_name'] for r in rows)
    missing=[r['name'] for r in rows if cells.get(r['name'])!=r['ref_name']]
    assert inventory['CARRY4']==64 and inventory['FDRE']==256 and inventory['LUT1']==7
    assert not missing,missing
    work=ROOT/'build'/f'gate_{phase}_{variant}'
    annotated_name=re.findall(r'\$sdf_annotate\("([^\"]+)"',(folder/'design.v').read_text(encoding='utf-8'))
    assert len(annotated_name)==1
    assert e.sha(work/annotated_name[0])==e.sha(folder/'design.sdf')
    assert e.sha(work/'design.v')==e.sha(folder/'design.v')
    cases=[]
    for case in sorted(folder.glob('gate_*')):
        if not (case/'run_manifest.txt').exists():continue
        log=(case/'elaboration.log').read_text(errors='replace')
        annotation_ok='SDF backannotation was successful' in log
        warnings=[line for line in log.splitlines() if 'SDF' in line and ('WARNING' in line or 'ERROR' in line)]
        total=Counter();active=Counter();window=[];scope_counts=Counter()
        with (case/'simulation.log').open(encoding='utf-8',errors='replace') as f:
            for lineno,line in enumerate(f,1):
                if 'Timing violation in scope' not in line:continue
                match=re.search(r'scope (\S+) at time (\d+) ps \$(\w+)',line)
                if not match:raise ValueError(f'未解析告警格式 {case}:{lineno}')
                scope,when,check=match[1],int(match[2]),match[3]
                if 'mmcm_adv_inst' in scope and ('CLKOUT5' in line or 'CLKOUT6' in line):category='MMCM_unused_CLKOUT5_6_model'
                elif 'u_tdl' in scope and 'thermo_q' in scope:category='TDL_asynchronous_sampling'
                elif 'pwm_meta' in scope or 'pwm_sync' in scope:category='PWM_asynchronous_synchronizer'
                elif 'rst_sync' in scope:category='reset_synchronizer'
                elif 'u_ila3/' in scope and ('shifted_data_in_reg[7][27]' in scope or 'G_NMU[4]' in scope):category='ILA_asynchronous_PWM_debug_capture'
                elif 'u_tdc_' in scope:category='synchronous_TDC_digital'
                elif 'u_ila' in scope:category='ILA_other_requires_endpoint_review'
                elif 'u_fifo' in scope:category='FIFO_IP_requires_endpoint_CDC_review'
                else:category='other_or_model'
                total[category,check]+=1;scope_counts[scope,check]+=1
                if when>=5_000_000:active[category,check]+=1
                if any(lo<=when<=hi for lo,hi in [(238600000,238900000),(241900000,242200000),(245200000,245500000)]):
                    window.append(dict(time_ps=when,category=category,check=check,scope=scope,log_line=lineno))
        values=[dict(category=k[0],check=k[1],all_time_count=n,after_5us_count=active[k]) for k,n in sorted(total.items())]
        e.write_csv(case/'timing_violation_counts.csv',values or [dict(category='none',check='',all_time_count=0,after_5us_count=0)])
        e.write_csv(case/'timing_violation_scopes.csv',(dict(scope=k[0],check=k[1],count=n) for k,n in sorted(scope_counts.items())))
        if window:e.write_csv(case/'anomaly_window_timing_warnings.csv',window)
        item=dict(case=case.name,annotation_success=annotation_ok,annotation_warnings=warnings,total_timing_warnings=sum(total.values()),categories=values)
        cases.append(item)
        print(phase,variant,case.name,item['total_timing_warnings'],values,flush=True)
    result=dict(phase=phase,variant=variant,critical_inventory=dict(inventory),missing_critical=missing,total_sdf_cells=len(cells),
        exported_and_annotated_sdf_sha256_equal=True,exported_and_compiled_netlist_sha256_equal=True,cases=cases,
        source_sha256={f.name:e.sha(f) for f in [folder/'design.dcp',folder/'design.sdf',folder/'design.v']},
        note='关键单元清单覆盖及工具成功日志不能冒充全局逐路径注释百分比；时序警告原文完整保留。')
    (folder/'sdf_audit.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('phase',choices=['original','optimized']);p.add_argument('variant',choices=['baseline','compensated']);a=p.parse_args();audit(a.phase,a.variant)
