"""收集本次必要构建证据、报告及清单，不复制运行缓存或历史仿真数据。"""
from pathlib import Path
import csv,hashlib,json,re,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_edge_20261107_01'
OLD=ROOT/'codex_generate/2026-11-05-05-四相TDC核心时序优化'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def metrics(p):
    s=p.read_text(errors='replace');m=re.search(r'WNS\(ns\).*?\n\s*-+.*?\n\s*([-\d.]+)\s+([-\d.]+)\s+\d+\s+\d+\s+([-\d.]+)\s+([-\d.]+)',s,re.S)
    return dict(zip(['WNS','TNS','WHS','THS'],map(float,m.groups()))) if m else {}
def read_csv(p):
    if not p.exists():return []
    with p.open(newline='') as f:return list(csv.DictReader(f))
def main():
    src=json.loads((TASK/'inputs/SOURCE.json').read_text(encoding='utf-8'))
    for name,digest in src['formal_RTL_sha256'].items():assert sha(ROOT/'fpga_tdc_v3_cal_rtl'/name)==digest
    assert sha(Path(src['production_bit']))==src['production_bit_sha256']
    assert sha(Path(src['reference_dcp']))==src['reference_dcp_sha256']
    shutil.copytree(WORK/'results',TASK/'results',dirs_exist_ok=True)
    for name in ['ILA_DEBUG.bit','ILA_DEBUG.ltx']:
        if (WORK/'results'/name).exists():shutil.copy2(WORK/'results'/name,TASK/name)
    for ext in ['*.log','*.jou']:
        for p in WORK.glob(ext):shutil.copy2(p,TASK/'logs'/p.name)
    for name in ['clk_wiz_0','fifo_tdc_result','ila_3']:
        dst=TASK/'inputs/ip'/name;dst.mkdir(parents=True,exist_ok=True)
        shutil.copy2(OLD/'inputs/ip'/name/(name+'.xci'),dst/(name+'.xci'))
    p=WORK/'new_ip/ila_edge_debug/ila_edge_debug.xci'
    if p.exists():
        dst=TASK/'inputs/ip/ila_edge_debug';dst.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst/p.name)
    shutil.copy2(WORK/'production_AD23.dcp',TASK/'inputs/production_AD23.dcp')
    before=metrics(TASK/'results/before/timing_summary.rpt')
    after_file=TASK/'results/after/timing_summary.rpt'
    after=metrics(after_file) if after_file.exists() else {}
    negative=read_csv(TASK/'results/after/negative_setup.csv')
    core=[r for r in negative if not r['endpoint'].startswith(('u_ila','debug_','dbg_hub/'))]
    bit=(TASK/'ILA_DEBUG.bit').exists()
    status=dict(status='DEBUG_BIT_READY' if bit else 'TIMING_GATE_FAIL' if after else 'BUILD_INCOMPLETE',
        source_commit=src['source_commit'],before=before,after=after,
        formal_RTL_modified=False,compensation_parameters_modified=False,
        production_bit_unchanged=True,debug_bit_generated=bit,new_negative_core_setup_paths=core,
        hardware_programmed=False,trigger_A_hardware_captured=False,trigger_B_hardware_captured=False,
        hardware_note='只完成定位工具；没有真实硬件错误触发记录时不宣称上板定位成功')
    (TASK/'results/STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=['# 时序前后对照\n','基准为实际AD23生产DCP，不是另一份历史SDF实现。单位ns。\n',
           '| 实现 | WNS | TNS | WHS | THS |\n|---|---:|---:|---:|---:|']
    for name,m in [('当前生产版',before),('本次Debug路由版',after)]:
        lines.append('|'+name+'|'+('|'.join(str(m.get(k,'未完成')) for k in ['WNS','TNS','WHS','THS']))+'|')
    lines+=['\n生产版全局负路径来自历史ILA2；核心和调试路径必须分开审查。',
       '\n| 模块 | 原Setup最差 | Debug Setup最差 | 原Hold最差 | Debug Hold最差 |\n|---|---:|---:|---:|---:|']
    b=read_csv(TASK/'results/before/core_timing.csv');a=read_csv(TASK/'results/after/core_timing.csv')
    def find(rows,module,delay):return next((r['slack_ns'] for r in rows if r['module']==module and r['delay_type']==delay),'未完成')
    for module in dict.fromkeys(r['module'] for r in b):
        lines.append('|'+module+'|'+'|'.join([find(b,module,'max'),find(a,module,'max'),find(b,module,'min'),find(a,module,'min')])+'|')
    lines+=['\n新增核心负Setup路径数：'+str(len(core))+'。详细起终点见results/after/negative_setup.csv；Hold见negative_hold.csv。',
        '\nBIT门槛：任何测量核心、影子采集、ILA或Hub路径有负Setup/Hold均停止BIT生成。没有新增false path、multicycle或关闭timing check。',
        '\n最终状态：'+status['status']+'。未生成BIT时不得烧录中间DCP或其他版本替代本任务验收。']
    (TASK/'TIMING_BEFORE_AFTER.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    result=f'''# 上板边沿配对错误ILA定位工具

本轮状态：**{status['status']}**。Debug BIT生成：**{'是' if bit else '否'}**。本次没有修复错误、调整精度或进行码密度校准。

## 来源与完整性

- 当前上板RTL源Commit：`{src['source_commit']}`；原3512脉冲MAX-SDF验证归档Commit为`31090be88d0fef94835f69a6edcff4e447328220`。
- 实际生产版为AD23引脚ECO后的DCP/BIT，SHA256见inputs/SOURCE.json；生产BIT、生产DCP及正式5个RTL均再次逐字节核验未变。
- 工程根目录不是Git仓库。新分支从当前源版本之后的验证归档Commit建立，只向本次任务目录及索引增加文件，没有用历史仿真RTL覆盖实际工程。
- 顶层`tdc_meas_top`，器件`xc7k325tffg900-2`，PWM=AD23/LVCMOS18、sys_clk=AD12/SSTL135、sys_rst_n=C22/LVCMOS18；约束完整副本在inputs。

## 调试改动

正式测量逻辑修改：**否**。独立rtl副本中的fine_layer/merge仅增加只读输出端口；top增加影子寄存器、只读状态记录和两个独立32位错误计数器，并将原500 MHz窄ILA替换为本次ILA。candidate/Locate算法不变。原100 MHz结果ILA、FIFO格式、全部valid、五级Locate、8个补偿参数、TDL和辅助判断规则均保持。

8个参数ps：0° rise/fall=36081，90°=36011，180°=35742，270°=35756。ENABLE_SKEW_COMP=1，未重新提取或调整。

两种触发直接来自原`error_event_valid && error_event_code==1/2`，不是粘滞状态；详见TRIGGER_CONDITIONS.md。全部前端和配对观测使用0°500 MHz影子采样，原100 MHz ILA不接收500 MHz瞬态探针。信号对应表见ILA_SIGNAL_MAP.md。

## 验证和实现

- 配对FSM及调试监测逐拍等价检查：12017周期，A事件2097次、B事件2281次，通过；见results/RTL_VALIDATION.json。
- 复用冻结3512脉冲进行单次Debug理想RTL测试，10类CSV与当前上板源版本冻结结果逐字节一致，3512/3512有效输出；见results/FULL_RTL_EQUIVALENCE.json。不是重新执行MAX-SDF。
- 顶层综合完成。新增ILA为1024深度、四拍输入流水，仅控制总线用于触发。增量参考为实际生产AD23 DCP。
- 初次缺IP输出目录、两次Hub内存不足等构建失败日志保留。识别并复用历史验证Hub缓存键后从综合检查点继续，未反复综合测量RTL。未创建虚拟盘符。
- 路由时序：before={before}；after={after}。新增核心负Setup路径{len(core)}条。详见TIMING_BEFORE_AFTER.md及原始报告。
- 本次没有上板A/B错误触发CSV，不能声称已安全独立触发两类错误，也不能据此断言TDL漏检或FSM有误。

## 尚不能观测或确认的内容

确认前pack是TDL编码/范围筛选后的候选，不是thermo_q；aux ordered_samples是原有跨相位传输后的真实采样记录，不是各相第一层亚稳寄存器的直接观测。没有跨域近似值冒充原相位信号。若候选为空，后续仍可能需要原相位编码器观测；输入毛刺还需要AD23端模拟波形。

若Debug路由时序不通过，停止BIT生成与烧录，保留当前失败实现用于审查。下一步只能缩减/隔离调试负载或设计独立历史快照，不能修改测量规则来得到PASS。本次不据此尝试修复原上板问题。

## 复现与使用

1. 阅读inputs/SOURCE.json、RTL.diff、ILA_SIGNAL_MAP.md、TRIGGER_CONDITIONS.md。
2. 本地本次运行目录为`{WORK.as_posix()}`；它是实际目录，不是subst映射。运行缓存与重复仿真CSV保留在此，不上传大量中间文件；其SHA256比较证据已归档。
3. 独立复现：`python scripts/prepare_review_workspace.py {ROOT.as_posix()}/codex_generate/.vivado_work/tdc_edge_review_02`（需新建且不存在的ASCII目录）。在该目录运行Vivado2022.2：`vivado -mode batch -source build_debug.tcl`。同配置IP若无缓存会重新生成，不要覆盖本轮冻结结果。
4. 功能检查：`python scripts/validate_debug.py`；3512全链验证脚本引用当前工程的05任务冻结测试平台和激励，见脚本路径。已有验证输出不覆盖。
5. 只有最终BIT及配套LTX通过门槛后，才运行scripts/capture_errors.tcl按A/B分别arm。触发位置768，保留前后历史。没有BIT时脚本会明确拒绝烧录。

## Git归档

分支：`codex/2026-11-07-01-edge-pairing-ila-debug`。提交说明：`2026-11-07-01-上板边沿配对错误ILA定位`。最终Commit和实际推送状态在执行反馈及本地GIT_DELIVERY.json中记录，不合并main、不强推、不更改旧归档。

采用新增/修改ILA后的增量实现方式，流程依据[AMD UG908 2022.2](https://www.xilinx.com/support/documents/sw_manuals/xilinx2022_2/ug908-vivado-programming-debugging.pdf)。没有在已路由实现里强行修改探针宽度后直接生成BIT。
'''
    (TASK/'RESULTS.md').write_text(result,encoding='utf-8')
    # 摘要只对本次交付文件计算，不递归复制Git worktree或工具缓存。
    excluded={'SHA256SUMS.txt','FILE_LIST.txt','GIT_DELIVERY.json'}
    files=sorted(p for p in TASK.rglob('*') if p.is_file() and 'github' not in p.relative_to(TASK).parts and '__pycache__' not in p.parts and p.name not in excluded)
    (TASK/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(TASK).as_posix()}\n' for p in files),encoding='utf-8')
    (TASK/'FILE_LIST.txt').write_text(''.join(f'{p.stat().st_size:>10}  {p.relative_to(TASK).as_posix()}\n' for p in files),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
