"""冻结上一轮合并成果并准备最小优化的独立实验，不覆盖历史目录。"""
from pathlib import Path
import difflib,hashlib,json,shutil

ROOT=Path('W:/');MERGE=Path('Y:/');AUX=Path('X:/')
FORMAL=Path('D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/fpga_tdc_v3_cal_rtl')
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    before=ROOT/'original/rtl';changed=[];diff=[]
    for p in FORMAL.glob('*.v'):
        assert sha(before/p.name)==sha(MERGE/'rtl'/p.name),p.name
        shutil.copyfile(p,ROOT/'rtl'/p.name)
        if sha(before/p.name)!=sha(p):changed.append(p.name)
        diff+=difflib.unified_diff((before/p.name).read_text(encoding='utf-8').splitlines(True),p.read_text(encoding='utf-8').splitlines(True),fromfile='before/'+p.name,tofile='after/'+p.name)
    assert sorted(changed)==['tdc_meas_top.v','tdc_time_locate.v']
    assert sha(ROOT/'rtl/tdc_fine_layer.v')==sha(AUX/'rtl/tdc_fine_layer.v')
    (ROOT/'RTL.diff').write_text(''.join(diff),encoding='utf-8')
    for name in ['frozen_compensation.csv','compensation_params.tcl','combine.xdc','frozen_baseline_association.json']:
        shutil.copyfile(MERGE/'inputs'/name,ROOT/'inputs'/name)
    shutil.copytree(MERGE/'inputs/ip',ROOT/'inputs/ip',dirs_exist_ok=True)
    for name in ['tb_quick.sv','functional_models.v','aux_monitor.svh','compensation_parameters.vh','tb_locate_boundary.sv']:
        shutil.copyfile(MERGE/'sim'/name,ROOT/'sim'/name)
    (ROOT/'sim/stimuli').mkdir(exist_ok=True)
    for name in ['full.txt','full_truth.csv']:shutil.copyfile(MERGE/'sim/stimuli'/name,ROOT/'sim/stimuli'/name)
    tb=(ROOT/'sim/tb_quick.sv').read_text(encoding='utf-8')
    tb=tb.replace('\nendmodule','''
// 只读检查复位末级副本与原同步器同拍，写门控的所有条件保持原逻辑。
always @(dut.rst_result_fifo_500m or dut.rst_n_500m) begin
    #1;
    if(dut.rst_result_fifo_500m!==dut.rst_n_500m) $fatal(1,"结果FIFO复位副本与原末级不等价");
end
endmodule''')
    (ROOT/'sim/tb_quick.sv').write_text(tb,encoding='utf-8')
    # 原平台与原分析只复用，增加本轮与上一轮完整输出逐字节核验。
    text=(MERGE/'scripts/run_rtl.py').read_text(encoding='utf-8')
    text=text.replace("b,c=variants['baseline'],variants['compensated']", """b,c=variants['baseline'],variants['compensated']
    for variant,case in variants.items():
        for name in ['raw.csv','candidate.csv','sampled_taps.csv','aux_trace.csv','timestamps.csv','widths.csv','fifo.csv','errors.csv','error_fifo.csv','anomaly_pipeline_trace.csv']:
            assert (case/name).read_bytes()==(Path('Y:/results/rtl')/variant/'rtl_full'/name).read_bytes(),(variant,name)
    print('FULL_RTL_BYTE_EQUIVALENCE_PASS both variants',flush=True)""")
    (ROOT/'scripts/run_rtl.py').write_text(text,encoding='utf-8')
    # 复用已生成且参数相同的4个OOC IP产品，避免无关IP重复综合。
    shutil.copytree(MERGE/'build/registered',ROOT/'build/registered',dirs_exist_ok=True)
    shutil.copytree(MERGE/'build/ip_cache',ROOT/'build/ip_cache',dirs_exist_ok=True)
    for name in ['restore_bram_mode.tcl','prepare_ila_cluster.tcl']:
        shutil.copyfile(MERGE/'scripts'/name,ROOT/'scripts'/name)
    build=(MERGE/'scripts/build_compensated.tcl').read_text(encoding='utf-8').replace('X:/results/baseline/design.dcp','Y:/results/compensated/design.dcp')
    build=build.replace('export_compensated.tcl','export_timing.tcl')
    (ROOT/'scripts/build_timing.tcl').write_text(build,encoding='utf-8')
    # 完整保存上一轮关键报告与本次所有输入哈希；不重算原8参数。
    shutil.copyfile(MERGE/'TIMING_REVIEW.md',ROOT/'inputs/TIMING_REVIEW_BEFORE.md')
    shutil.copyfile(MERGE/'results/TIMING_REVIEW.json',ROOT/'inputs/TIMING_BEFORE.json')
    paths=list((ROOT/'rtl').glob('*.v'))+list((ROOT/'original/rtl').glob('*.v'))+list((ROOT/'inputs/ip').rglob('*.xci'))+[ROOT/'inputs/frozen_compensation.csv',ROOT/'inputs/compensation_params.tcl',ROOT/'inputs/combine.xdc',ROOT/'sim/stimuli/full.txt',ROOT/'sim/stimuli/full_truth.csv',MERGE/'results/compensated/design.dcp']
    (ROOT/'inputs/SOURCE_SHA256.json').write_text(json.dumps({str(p):{'bytes':p.stat().st_size,'sha256':sha(p)} for p in paths},indent=2),encoding='utf-8')
    (ROOT/'PLAN.md').write_text('''# 最小修改方案

仅修改tdc_time_locate.v与tdc_meas_top.v，其他3个RTL逐字节不变，上一轮合并成果保存在2026-11-05-04任务目录及本任务original/rtl。

1. 模数M=2000*2^COARSE_W=125*2^(COARSE_W+4)。有符号s4_sum分解为h*2^L+l，0<=l<2^L，则s<0等价h<0，s>=M等价h>=125，加减M只改变高位。保留原23位有符号s4_sum/wrapped_time、21位输出及五级流水；仅显式将回卷逻辑限制在9位高部，低14位直连。
2. 复制500MHz复位同步器末级：同一个原第一级D、同clk、同异步复位，逻辑不增加级数或释放延迟，仅副本驱动结果FIFO写门控。原FIFO rst端口、busy/full/valid及读控制均不变；DONT_TOUCH防止副本再次合并，不修改FIFO IP。
3. RTL复用原3512输入/真值，旁路及补偿的全部关键CSV与上一轮逐字节比较；独立测试原signed回卷边界和复位语义。
4. RTL通过后只做一次顶层综合/布局布线，复用原4个OOC IP产品及上一轮路由参考；不添加时序例外、不优化ILA、不动TDL、不写BIT、不跑SDF。
5. 分别保留四条原核心路径的最终裕量、所有负Setup/Hold路径、模块输入/输出边界与约束覆盖检查。
''',encoding='utf-8')
    project=FORMAL.parent;index=project/'codex_generate/README.md';data=index.read_bytes();name='2026-11-05-05-四相TDC核心时序优化'
    if name.encode() not in data:
        eol=b'\r\n' if b'\r\n' in data else b'\n';row=f'| 2026-11-05-05 | [四相TDC核心时序优化]({name}/RESULTS.md) |'.encode()
        pos=data.index(b'\n',data.index(b'| 2026-11-05-04 |'))+1;index.write_bytes(data[:pos]+row+eol+data[pos:])
    print('PREPARED',changed,'frozen compensation and previous merge preserved')

if __name__=='__main__':main()
