"""只读审查实际实现，区分主通路与已确认不回馈测量的ILA违例。"""
from pathlib import Path
import csv,json,re

ROOT=Path('W:/')
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def main():
    out=ROOT/'results/baseline';text=(out/'timing_summary.rpt').read_text(encoding='utf-8',errors='replace')
    m=re.search(r'WNS\(ns\).*?\n\s*-+[^\n]*\n\s*([-\d.]+)\s+([-\d.]+)\s+(\d+)\s+(\d+)\s+([-\d.]+)\s+([-\d.]+)\s+(\d+)',text,re.S)
    assert m,'缺少完整时序摘要'
    modules=read(out/'module_worst_setup.csv');failed=read(out/'negative_setup_reachability.csv')
    acceptable=all(r['endpoint'].startswith('u_ila2/') and r['measurement_fifo_reachable_count']=='0' for r in failed)
    main_slacks={r['module']:float(r['slack_ns']) for r in modules if r['module']!='u_ila2'}
    check=(out/'check_timing.rpt').read_text(encoding='utf-8',errors='replace')
    counts={k:int(v) for k,v in re.findall(r'checking (\w+) \((\d+)\)',check)}
    old=read(Path('U:/results/optimized/baseline/frontend_structure.csv'))
    new=read(out/'frontend_structure.csv')
    def tdl(rows):return {r['name']:(r['ref_name'],r['loc'],r['bel']) for r in rows if any(k in r['name'] for k in ['g_carry','thermo_q_reg','g_pwm_dist'])}
    same=tdl(old)==tdl(new);assert same,'TDL/分发树单元位置或BEL与原固定结构不同'
    aux_setup=float(re.search(r'Slack \(MET\)\s*:\s*([-\d.]+)ns',(out/'aux_setup_top50.rpt').read_text(encoding='utf-8'))[1])
    aux_hold=float(re.search(r'Slack \(MET\)\s*:\s*([-\d.]+)ns',(out/'aux_hold_top50.rpt').read_text(encoding='utf-8'))[1])
    result=dict(wns_ns=float(m[1]),tns_ns=float(m[2]),setup_failing_endpoints=int(m[3]),whs_ns=float(m[5]),ths_ns=float(m[6]),hold_failing_endpoints=int(m[7]),
        main_module_slacks_ns=main_slacks,aux_setup_slack_ns=aux_setup,aux_hold_slack_ns=aux_hold,
        negative_setup_only_nonfeedback_ila2=acceptable,unchanged_fixed_tdl_structure=same,fixed_cells_checked=len(tdl(new)),constraint_checks=counts)
    result['main_static_pass']=acceptable and all(x>=0 for x in main_slacks.values()) and float(m[5])>=0 and int(m[7])==0 and all(counts.get(k,0)==0 for k in ['no_clock','unconstrained_internal_endpoints','loops'])
    (ROOT/'results/TIMING_REVIEW.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))

if __name__=='__main__':main()
