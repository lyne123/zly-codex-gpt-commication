"""按冻结DCP的实际叶单元编译Vivado2022.2原厂时序模型。"""
from pathlib import Path
import csv,hashlib,json,subprocess
ROOT=Path('Z:/');MSIM=Path('F:/Program Files/modeltech64_2020.4/win64');VENDOR=Path('F:/Xilinx/Vivado/2022.2/data/verilog/src')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(args,cwd,log):
    with log.open('wb') as f:subprocess.run([str(x) for x in args],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,check=True)
def main():
    work=ROOT/'build/modelsim';work.mkdir(exist_ok=True)
    rows=list(csv.DictReader((ROOT/'inputs/DCP_PRIMITIVES.csv').open(encoding='utf-8')))
    sources=[]
    for row in rows:
        p=VENDOR/'unisims'/(row['primitive']+'.v');assert p.exists(),p
        sources.append(dict(primitive=row['primitive'],instances=int(row['instances']),source=str(p),sha256=sha(p)))
    for name in ['work','simprims_ver']:
        if (work/name).exists():raise RuntimeError('禁止覆盖已有ModelSim库：'+name)
        run([MSIM/'vlib.exe',name],work,work/('vlib_'+name+'.log'))
    (work/'modelsim.ini').write_text('[Library]\nothers = $MODEL_TECH/../modelsim.ini\nwork = Z:/build/modelsim/work\nsimprims_ver = Z:/build/modelsim/simprims_ver\n',encoding='ascii')
    (work/'vendor_models.f').write_text(''.join('"'+r['source'].replace('\\','/')+'"\n' for r in sources),encoding='ascii')
    command=[MSIM/'vlog.exe','-modelsimini',work/'modelsim.ini','-work','simprims_ver','+define+XIL_TIMING','-sv','-f',work/'vendor_models.f']
    run(command,work,ROOT/'logs/vendor_models_compile.log')
    (ROOT/'inputs/VENDOR_MODEL_MANIFEST.json').write_text(json.dumps(dict(tool='ModelSim SE-64 2020.4',Vivado='2022.2',library='simprims_ver',XIL_TIMING=True,behavioral_replacements=False,primitive_sources=sources,command=[str(x) for x in command]),ensure_ascii=False,indent=2),encoding='utf-8')
    print('REAL_VENDOR_TIMING_MODELS_COMPILED',len(sources),'types',sum(r['instances'] for r in sources),'DCP leaf cells')
if __name__=='__main__':main()
