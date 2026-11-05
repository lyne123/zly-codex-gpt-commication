"""核对完整有符号回卷位模式及异步复位/同拍释放/FIFO序列。"""
from pathlib import Path
import json,re,subprocess
ROOT=Path('W:/')
def run(args,cwd,log):
    with log.open('wb') as f:subprocess.run(args,cwd=cwd,stdout=f,stderr=subprocess.STDOUT,check=True)
def main():
    work=ROOT/'build/unit';work.mkdir(exist_ok=True)
    checks={}
    for top,files in [('tb_wrap_equivalence',[ROOT/'sim/tb_wrap_equivalence.sv',ROOT/'rtl/tdc_time_locate.v']),('tb_fifo_reset',[ROOT/'sim/tb_fifo_reset.sv',ROOT/'sim/functional_models.v']+list((ROOT/'rtl').glob('*.v')))]:
        if top=='tb_fifo_reset':
            reference=work/'tdc_meas_top_reference.v'
            reference.write_text((ROOT/'original/rtl/tdc_meas_top.v').read_text(encoding='utf-8').replace('module tdc_meas_top #(','module tdc_meas_top_reference #('),encoding='utf-8');files+=[reference]
        run(['F:/iverilog/bin/iverilog.exe','-g2012','-s',top,'-I',str(ROOT/'sim'),'-o',str(work/(top+'.vvp'))]+[str(p) for p in files],work,work/(top+'_compile.log'))
        log=ROOT/'logs'/(top+'.log');run(['F:/iverilog/bin/vvp.exe',str(work/(top+'.vvp'))],work,log)
        text=log.read_text(encoding='utf-8');assert 'FATAL:' not in text,text
        if top=='tb_wrap_equivalence':
            samples={int(cw):int(n) for cw,n in re.findall(r'WRAP_EQUIVALENCE_PASS CW=(\d+) samples=(\d+)',text)};assert set(samples)=={1,8,10};checks['wrap_equivalence_samples']=samples
        else:
            m=re.search(r'FIFO_RESET_PASS checks=(\d+) outputs=(\d+) assertions=(\d+) releases=(\d+)',text);assert m,text
            checks['fifo_reset_checks']=dict(zip(['cycles','outputs','assertions','releases'],map(int,m.groups())))
        print(top,text.strip(),flush=True)
    checks['unit_pass']=True
    (ROOT/'results/UNIT_CHECKS.json').write_text(json.dumps(checks,indent=2),encoding='utf-8')

if __name__=='__main__':main()
