"""保留每条原始timing violation，并区分异步采样、复位、核心同步及模型告警。"""
from pathlib import Path
from collections import Counter
import csv,gzip,hashlib,json,re,shutil
ROOT=Path('Z:/');CASE=ROOT/'results/compensated/gate_full'
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def main():
    assert (CASE/'run_manifest.txt').exists(),'尚未完成仿真，不能统计部分日志作为验收'
    reset=read(CASE/'RESET_TRACE.csv');release=max((int(r['time_ps']) for r in reset if r['value']=='1'),default=0)
    truth=read(ROOT/'inputs/full_truth.csv');first=min(int(t['rise_ps']) for t in truth)
    total=Counter();postreset=Counter();measurement=Counter();core_examples=[];unknown=[];n=0
    log=ROOT/'logs/simulation.log';csvfile=ROOT/'results/TIMING_VIOLATIONS.csv';viol=ROOT/'logs/timing_violations.log'
    pattern=re.compile(r'^WARNING: "(.+)" Line (\d+): Timing violation in scope (\S+) at time (\d+) ps \$(\w+)\s*(.*)')
    with log.open(encoding='utf-8',errors='replace') as source,csvfile.open('w',encoding='utf-8-sig',newline='') as f,viol.open('w',encoding='utf-8',newline='') as raw:
        writer=csv.writer(f);writer.writerow(['log_line','time_ps','category','check','scope','source_model','source_line','after_reset_release','after_first_input','detail'])
        for lineno,line in enumerate(source,1):
            if 'Timing violation in scope' not in line:continue
            raw.write(line);m=pattern.match(line)
            if not m:unknown.append(dict(log_line=lineno,line=line));continue
            filename,source_line,scope,time,check,detail=m.groups();time=int(time)
            if 'mmcm_adv_inst' in scope and ('CLKOUT5' in detail or 'CLKOUT6' in detail):kind='unused_MMCM_CLKOUT5_6_model'
            elif 'u_tdl' in scope and 'thermo_q_reg' in scope:kind='TDL_asynchronous_sampling'
            elif 'g_aux_4phase' in scope and 'pwm_meta_reg' in scope:kind='AUX_first_stage_asynchronous_sampling'
            elif 'u_fifo_tdc_' in scope and 'gic_rst.xpm_cdc_sync_rst_inst_wrst/syncstages_ff_reg[0]' in scope:kind='FIFO_reset_CDC_first_stage'
            elif 'rst_sync_' in scope or 'rst_result_fifo_' in scope:kind='reset_synchronizer'
            elif 'u_ila3/' in scope and ('shifted_data_in_reg[7][27]' in scope or 'G_NMU[4]' in scope):kind='ILA_PWM_asynchronous_debug'
            elif 'u_ila2/' in scope:kind='historical_ILA2'
            elif 'g_aux_4phase' in scope:kind='AUX_synchronous_requires_review'
            elif 'u_tdc_' in scope:kind='TDC_synchronous_requires_review'
            elif 'u_fifo_tdc_' in scope:kind='FIFO_synchronous_requires_review'
            else:kind='other_requires_review'
            total[kind,check]+=1
            if time>=release:postreset[kind,check]+=1
            if time>=first:measurement[kind,check]+=1
            writer.writerow([lineno,time,kind,check,scope,Path(filename).name,source_line,int(time>=release),int(time>=first),detail]);n+=1
            if 'requires_review' in kind and len(core_examples)<200:core_examples.append(dict(time_ps=time,category=kind,check=check,scope=scope,log_line=lineno))
    with csvfile.open('rb') as src,gzip.open(str(csvfile)+'.gz','wb',compresslevel=6) as dst:shutil.copyfileobj(src,dst)
    with log.open('rb') as src,gzip.open(str(log)+'.gz','wb',compresslevel=6) as dst:shutil.copyfileobj(src,dst)
    with viol.open('rb') as src,gzip.open(str(viol)+'.gz','wb',compresslevel=6) as dst:shutil.copyfileobj(src,dst)
    suspicious=sum(c for (kind,check),c in postreset.items() if 'requires_review' in kind or kind=='reset_synchronizer')
    report=dict(total_timing_violations=n,parse_failures=unknown,reset_release_ps=release,first_input_ps=first,raw_Timing_Check_pass=n==0,core_synchronous_after_reset_violations=suspicious,core_synchronous_after_reset_pass=suspicious==0 and not unknown,raw_checks_combined_note='setuphold为联合Setup/Hold检查，recrem为联合Recovery/Removal检查；保留仿真器原检查类型，不擅自拆分归因。',categories=[dict(category=k,check=c,count=v,after_reset_release=postreset[k,c],after_first_input=measurement[k,c]) for (k,c),v in sorted(total.items())],core_examples=core_examples,timing_checks_disabled=False,all_raw_lines_preserved=True,compression='lossless gzip; uncompressed originals retained locally')
    (ROOT/'results/TIMING_CHECK_SUMMARY.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    files=[]
    for p in [csvfile,log,viol]:
        with p.open('rb') as f:digest=hashlib.file_digest(f,'sha256').hexdigest()
        with gzip.open(str(p)+'.gz','rb') as f:assert hashlib.file_digest(f,'sha256').hexdigest()==digest
        files.append(dict(original=str(p),original_bytes=p.stat().st_size,compressed=str(p)+'.gz',compressed_bytes=Path(str(p)+'.gz').stat().st_size,uncompressed_sha256=digest))
    (ROOT/'inputs/LOG_COMPRESSION_MANIFEST.json').write_text(json.dumps(files,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(report,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
