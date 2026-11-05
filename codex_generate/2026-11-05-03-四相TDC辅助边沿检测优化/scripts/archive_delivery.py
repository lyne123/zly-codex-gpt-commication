"""只复制必要交付文件，保留失败记录和原始CSV，排除缓存与重复大日志。"""
from pathlib import Path
import csv,gzip,hashlib,json,re,shutil,xml.etree.ElementTree as ET

ROOT=Path('W:/');NAME='2026-11-05-03-四相TDC辅助边沿检测优化'
TARGET=ROOT/'github/codex_generate'/NAME

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def config(p):
    content=p.read_text(encoding='utf-8-sig')
    if content.lstrip().startswith('{'):
        params=json.loads(content)['ip_inst']['parameters']['component_parameters']
        return {k:[x.get('value') for x in v] for k,v in params.items()}
    result={}
    for e in ET.parse(p).iter():
        for key,value in e.attrib.items():
            if key.endswith('referenceId') and value.startswith('PARAM_VALUE.'):
                result[value]=(e.text or '').strip()
    return result

def main():
    full=json.loads((ROOT/'results/baseline/gate_full/VALIDATION.json').read_text(encoding='utf-8'))
    assert full['functional_pass'] and full['correct_widths']==3512 and full['active_synchronous_warning_count']==0
    assert json.loads((ROOT/'results/SHORT_FULL_EQUIVALENCE.json').read_text())['pass_all']
    assert json.loads((ROOT/'results/TIMING_REVIEW.json').read_text())['main_static_pass']
    assert json.loads((ROOT/'results/SDF_CAPTURE_REVIEW.json').read_text())['pass_all']
    assert json.loads((ROOT/'results/compensation_functional/FUNCTIONAL_CHECK.json').read_text())['pass_all']
    task_actual=Path(__file__).resolve().parents[1]
    formal=task_actual.parents[1]/'fpga_tdc_v3_cal_rtl'
    assert all(sha(p)==sha(formal/p.name) for p in (ROOT/'rtl').glob('*.v'))
    assert all(sha(p)==sha(ROOT/'original/rtl'/p.name) for p in (ROOT/'rtl').glob('*.v') if p.name!='tdc_fine_layer.v')
    assert (ROOT/'inputs/frozen_compensation.csv').read_bytes()==Path('U:/results/tdc_skew_calibration.csv').read_bytes()
    ip_status={}
    for ip in ['clk_wiz_0','fifo_tdc_result','ila_2','ila_3']:
        old=Path('U:/inputs/ip')/ip/(ip+'.xci')
        registered=ROOT/'build/registered/aux_baseline.srcs/sources_1/ip'/ip/(ip+'.xci')
        a,b=config(old),config(registered);difference={k:[a.get(k),b.get(k)] for k in a.keys()|b.keys() if a.get(k)!=b.get(k)}
        assert not difference,(ip,difference)
        ip_status[ip]=dict(parameter_values_equal=True,parameter_count=len(a),source_sha256=sha(old),registered_sha256=sha(registered))
    (ROOT/'results/IP_CONFIGURATION_CHECK.json').write_text(json.dumps(ip_status,indent=2),encoding='utf-8')
    logs=[]
    for case in ['gate_local','gate_full']:
        p=ROOT/'results/baseline'/case/'simulation.log';z=p.with_suffix('.log.gz')
        with gzip.open(z,'rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        assert digest==sha(p)
        logs.append(dict(original=str(p),archived=str(z.relative_to(ROOT)),original_bytes=p.stat().st_size,uncompressed_sha256=digest,compressed_bytes=z.stat().st_size))
    (ROOT/'inputs/LOG_PROVENANCE.json').write_text(json.dumps(logs,indent=2),encoding='utf-8')
    placements=[]
    with (ROOT/'results/baseline/frontend_structure.csv').open() as f:
        for r in csv.DictReader(f):
            if re.search(r'g_phase\[[0-3]\]\.pwm_(meta|sync)_reg',r['name']):placements.append(r)
    (ROOT/'results/CONSTRAINT_APPLICATION_STATUS.json').write_text(json.dumps(dict(attempted_extra_LOC_applied=False,reason='Vivado rejects foreach in XDC; active replay script omits the ineffective file; exact used script retained',actual_aux_placements=placements,critical_warnings=['Designutils 20-1307: unsupported foreach, no extra LOC applied','Vivado_Tcl 4-426: one reference SRL optimization not replayed'],implemented_effective_constraints_sha256=sha(ROOT/'results/baseline/effective_constraints.xdc')),indent=2),encoding='utf-8')
    files=[ROOT/'RESULTS.md',ROOT/'RTL.diff']
    for folder in ['rtl','original','sim']:
        files += [p for p in (ROOT/folder).rglob('*') if p.is_file() and p.suffix in ['.v','.sv','.svh','.csv','.txt']]
    files += [p for p in (ROOT/'scripts').glob('*') if p.suffix in ['.py','.tcl']]
    files += [p for p in (ROOT/'inputs').glob('*') if p.is_file() and p.suffix in ['.json','.csv','.xdc']]
    files += list((ROOT/'inputs/ip').rglob('*.xci'))
    for p in (ROOT/'results').rglob('*'):
        if not p.is_file():continue
        if p.suffix in ['.csv','.json','.rpt','.txt','.gz','.bat']:files.append(p)
        elif p.suffix=='.log' and p.name!='console.log' and not (p.name=='simulation.log' and p.parent.name.startswith('gate_')):files.append(p)
    for name in ['build_aux.log','build_aux.jou','ip_path_failure_build_aux.log','ip_path_failure_build_aux.jou','register_ip.log','register_ip.jou','gate_compile_console.log','aux_reset.log','lfs_preupload.log']:
        p=ROOT/'logs'/name
        if p.exists():files.append(p)
    for name in ['Baseline_Aux4Phase.bit','design.dcp','design.sdf','design.v']:files.append(ROOT/'results/baseline'/name)
    files=sorted(set(files))
    secrets=[]
    for p in files:
        if re.search(r'(?i)(\.lic$|id_rsa$|\.pem$|\.key$|^\.env$)',p.name):secrets.append(str(p))
        if p.suffix not in ['.bit','.dcp']:
            pattern=r'-----BEGIN (?:RSA |OPENSSH |EC )?PRIVATE KEY-----|ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}|AKIA[A-Z0-9]{16}'
            if p.suffix=='.gz':
                with gzip.open(p,'rt',encoding='utf-8',errors='replace') as f:
                    if any(re.search(pattern,line) for line in f):secrets.append(str(p))
            elif re.search(pattern,p.read_text(encoding='utf-8',errors='replace')):secrets.append(str(p))
    assert not secrets,('发现疑似敏感文件，停止归档',secrets)
    previous_sums={}
    if (TARGET/'SHA256SUMS.txt').exists():
        for line in (TARGET/'SHA256SUMS.txt').read_text(encoding='utf-8').splitlines():
            digest,name=line.split('  ',1);previous_sums[name]=digest
    for p in files:
        relative=p.relative_to(ROOT)
        if p.name.lower()=='aux.csv':relative=relative.with_name('aux_trace.csv')
        dest=TARGET/relative;dest.parent.mkdir(parents=True,exist_ok=True)
        if dest.exists() and sha(dest)!=sha(p):
            assert p.suffix in ['.py','.tcl','.svh','.md'] and previous_sums.get(relative.as_posix())==sha(dest),('拒绝覆盖用户修改或实验数据',dest)
            shutil.copyfile(p,dest)
        elif not dest.exists():shutil.copyfile(p,dest)
    index=ROOT/'github/codex_generate/README.md';data=index.read_bytes()
    if NAME.encode() not in data:
        ending=b'\r\n' if b'\r\n' in data else b'\n'
        row=f'| 2026-11-05-03 | [四相TDC辅助边沿检测优化]({NAME}/RESULTS.md) |'.encode()
        pos=data.index(b'\n',data.index(b'| 2026-11-05-02 |'))+1
        changed=data[:pos]+row+ending+data[pos:];assert changed.replace(row+ending,b'',1)==data;index.write_bytes(changed)
    names=sorted([p.relative_to(TARGET).as_posix() for p in TARGET.rglob('*') if p.is_file() and p.name not in ['FILE_LIST.md','SHA256SUMS.txt']]+['FILE_LIST.md','SHA256SUMS.txt'])
    listing='# 本次任务文件清单\n\n共 '+str(len(names))+' 个文件，另更新一行任务索引。4个最终实现文件由Git LFS保存；全部原始CSV和必要失败日志保留。未打包临时缓存、中间检查点和重复console日志。\n\n'+'\n'.join(f'- [{n}]({n})' for n in names)+'\n'
    (TARGET/'FILE_LIST.md').write_text(listing,encoding='utf-8')
    sums=''.join(f'{sha(p)}  {p.relative_to(TARGET).as_posix()}\n' for p in sorted(TARGET.rglob('*')) if p.is_file() and p.name!='SHA256SUMS.txt')
    (TARGET/'SHA256SUMS.txt').write_text(sums,encoding='utf-8')
    for name in ['FILE_LIST.md','SHA256SUMS.txt']:shutil.copyfile(TARGET/name,ROOT/name)
    actual=[p for p in TARGET.rglob('*') if p.is_file()]
    result=dict(task_files=len(actual),bytes=sum(p.stat().st_size for p in actual),max_file_bytes=max(p.stat().st_size for p in actual),sensitive_matches=0,original_parameters_unchanged=True,formal_modified_files=['tdc_fine_layer.v'],raw_csv_files=sum(p.suffix=='.csv' for p in actual),lossless_logs=True,main_gate_pass=True)
    (ROOT/'logs/ARCHIVE_CHECK.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps(result,indent=2))

if __name__=='__main__':main()
