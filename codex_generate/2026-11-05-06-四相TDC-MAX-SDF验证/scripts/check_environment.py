"""优先核验ModelSim2020.4、门级SDF许可及本设计所需厂商模型。"""
from pathlib import Path
import hashlib,json,re,subprocess

ROOT=Path('Z:/');SOURCE=Path('W:/');MSIM=Path('F:/Program Files/modeltech64_2020.4/win64');VENDOR=Path('F:/Xilinx/Vivado/2022.2/data/verilog/src')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def run(args,cwd,log,timeout=180):
    with log.open('wb') as f:return subprocess.run([str(x) for x in args],cwd=cwd,stdout=f,stderr=subprocess.STDOUT,timeout=timeout).returncode
def main():
    work=ROOT/'build/environment';work.mkdir(exist_ok=True)
    run([MSIM/'vsim.exe','-c','-help'],work,ROOT/'logs/vsim_help.log')
    run([MSIM/'vlog.exe','-help'],work,ROOT/'logs/vlog_help.log')
    # 仅检查已有Xilinx库映射；已失效的历史绝对路径不作为可用库。
    historical=Path('D:/software/modelsim/xilinx_lib')
    libraries={name:dict(historical_path=str(historical/name),exists=(historical/name).exists()) for name in ['unisims_ver','unimacro_ver','simprims_ver','secureip']}
    text=(SOURCE/'results/compensated/design.v').read_text(encoding='utf-8')
    declared={name.lstrip('\\') for name in re.findall(r'^\s*module\s+(\\\S+|\w+)',text,re.M)}
    used=set(re.findall(r'^  (\w+)\s+(?:#\s*\(.*?\)\s*)?(?:\\\S+|\w+)\s*\(',text,re.M|re.S))
    # 所有外部单元必须有本版真实厂商模型，禁止自行生成行为替代物。
    primitive_names=sorted(used-declared-{'module','input','output','wire','assign','reg','always','if','else'})
    primitive_files={name:VENDOR/'unisims'/(name+'.v') for name in primitive_names}
    protected_ip=[name for name,p in primitive_files.items() if not p.exists() and name.startswith(('fifo_tdc_resultfifo_generator_','ila_2ila_','ila_3ila_'))]
    missing=[name for name,p in primitive_files.items() if not p.exists() and name not in protected_ip]
    assert not missing,('缺少原语文件',missing)
    primitive_files={name:p for name,p in primitive_files.items() if p.exists()}
    primitive_names=sorted(primitive_files)
    (ROOT/'inputs/PRIMITIVE_SOURCES.json').write_text(json.dumps({name:dict(path=str(p),bytes=p.stat().st_size,sha256=sha(p)) for name,p in primitive_files.items()},indent=2),encoding='utf-8')
    # 环境探针不是TDC验收：使用原厂FDCE及受控SDF确认许可、MAX路径和timing check。
    run([MSIM/'vlib.exe','work'],work,work/'vlib.log')
    (work/'probe.sv').write_text('''`timescale 1ps/1ps
module tb_environment;
reg c=0,d=0;wire q;
FDCE probe(.C(c),.CE(1'b1),.CLR(1'b0),.D(d),.Q(q));
initial begin
  #200000;d=1;#1000;c=1;#300;c=0;
  #1000;d=0;#1;c=1;#500;
  $display("ENVIRONMENT_SDF_PROBE_DONE");$finish;
end
always @(q) if($time>150000) $display("ENVIRONMENT_Q time_ps=%0t value=%0d",$time,q);
endmodule
''',encoding='utf-8')
    (work/'probe.sdf').write_text('''(DELAYFILE
(SDFVERSION "3.0") (DESIGN "FDCE") (DATE "environment probe") (VENDOR "testbench") (PROGRAM "environment probe") (VERSION "1") (DIVIDER /) (TIMESCALE 1ps)
(CELL (CELLTYPE "FDCE") (INSTANCE probe)
(DELAY (ABSOLUTE (IOPATH C Q (100:200:300) (100:200:300))))
(TIMINGCHECK (SETUPHOLD (posedge D) (posedge C) (50:50:50) (20:20:20)) (SETUPHOLD (negedge D) (posedge C) (50:50:50) (20:20:20)))))
''',encoding='ascii')
    rc=run([MSIM/'vlog.exe','+define+XIL_TIMING','-sv',VENDOR/'unisims/FDCE.v',VENDOR/'glbl.v',work/'probe.sv'],work,ROOT/'logs/environment_compile.log')
    assert rc==0,'ModelSim探针编译失败'
    args=[MSIM/'vsim.exe','-c','-t','1ps','-sdfmax','/tb_environment='+str(work/'probe.sdf'),'work.tb_environment','work.glbl','-do','run -all; quit -f']
    rc=run(args,work,ROOT/'logs/environment_sdf_probe.log')
    transcript=(ROOT/'logs/environment_sdf_probe.log').read_text(encoding='utf-8',errors='replace')
    supported=rc==0 and 'ENVIRONMENT_SDF_PROBE_DONE' in transcript and 'Error loading design' not in transcript and '201300 value=1' in transcript
    result=dict(ModelSim_version='SE-64 2020.4',ModelSim_binary=str(MSIM/'vsim.exe'),Vivado_version='2022.2',license_and_real_primitive_SDF_probe_pass=supported,probe_exit_code=rc,existing_library_mapping=libraries,required_primitives=primitive_names,primitive_count=len(primitive_names),protected_IP_units_to_validate_by_real_compilation=protected_ip,all_primitive_sources_from_Vivado_2022_2=True,secureip_required='SECUREIP' in primitive_names,full_library_compile_needed=not any(x['exists'] for x in libraries.values()))
    (ROOT/'results/ENVIRONMENT_CHECK.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8');print(json.dumps(result,ensure_ascii=False,indent=2))
    if not supported:raise SystemExit('ModelSim环境探针未通过；不得据此宣称TDC通过')

if __name__=='__main__':main()
