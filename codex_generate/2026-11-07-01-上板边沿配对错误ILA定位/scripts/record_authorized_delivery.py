"""记录用户接受ILA内部违例后的同DCP导出和真实上板结果，保留原失败证据。"""
from pathlib import Path
import csv,hashlib,json,re,shutil
TASK=Path(__file__).resolve().parents[1]; ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_edge_20261107_01'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    source=json.loads((TASK/'inputs/SOURCE.json').read_text(encoding='utf-8'))
    for name,digest in source['formal_RTL_sha256'].items():assert sha(ROOT/'fpga_tdc_v3_cal_rtl'/name)==digest
    assert sha(Path(source['production_bit']))==source['production_bit_sha256']
    assert sha(TASK/'results/debug_routed.dcp')=='017bd5bd1e4ffdeb9a3dc839ae07a9b1184c8ed03d56c84a0493143298e3fb60'
    assert sha(TASK/'ILA_DEBUG.bit')=='4df6b364eda1511abf910637ad8edb64bc518cb092de91f53e7a567736ed58e7'
    captures=sorted(p for p in WORK.glob('hardware_debug_*') if re.fullmatch(r'hardware_debug_\d+',p.name))
    assert captures,'尚无Debug上板尝试'
    last=captures[-1]
    raw_status=(last/'HARDWARE_STATUS.txt').read_text(encoding='utf-8')
    assert 'attempt_status=' in raw_status,'硬件尝试尚未结束，不能提前记录结果'
    for p in sorted(WORK.glob('board_attempt_*'))+captures+sorted(WORK.glob('hardware_debug_activity_*')):
        if p.is_dir():shutil.copytree(p,TASK/'results'/p.name,dirs_exist_ok=True)
        elif p.suffix in ['.log','.jou']:shutil.copy2(p,TASK/'logs'/p.name)
    for pattern in ['authorized_debug_*.log','authorized_debug_*.jou','debug_activity_*.log','debug_activity_*.jou','hw_*stdout.log','hw_*stderr.log','cs_*stdout.log','cs_*stderr.log']:
        for p in WORK.glob(pattern):shutil.copy2(p,TASK/'logs'/p.name)
    for p in (WORK/'authorized_debug_01').iterdir():
        if p.is_file() and p.name not in ['ILA_DEBUG.bit','ILA_DEBUG.ltx']:
            shutil.copy2(p,TASK/'results/authorized_debug_export'/p.name)
    # 导出目录中此前创建的重复副本只留一份正式交付，不删除运行目录或生产文件。
    duplicate=TASK/'results/authorized_debug_export/ILA_DEBUG.bit'
    assert duplicate.resolve().is_relative_to(TASK.resolve())
    if duplicate.exists():
        assert sha(duplicate)==sha(TASK/'ILA_DEBUG.bit');duplicate.unlink()
    programmed='programming_completed=1' in raw_status
    trigger_results={}
    for event,mask in [('A',1),('B',2)]:
        p=last/f'TRIGGER_{event}.csv'
        info=dict(saved=p.exists(),event_flag_observed=False,sample_count=0)
        if p.exists():
            with p.open(encoding='utf-8-sig',newline='') as f:
                reader=csv.DictReader(f)
                col=next((k for k in reader.fieldnames if k.startswith('debug_control_q')),None)
                assert col,p
                radix=next(reader)
                base={'HEX':16,'UNSIGNED':10,'SIGNED':10,'BIN':2,'BINARY':2}.get(radix[col],10)
                rows=[r for r in reader if r['Sample in Buffer'].isdigit()]
            info.update(sample_count=len(rows),event_flag_observed=any(int(r[col],base)&mask for r in rows),sha256=sha(p))
        info['confirmed_capture']=info['sample_count']==1024 and info['event_flag_observed']
        trigger_results[event]=info
    status=dict(status='DEBUG_PROGRAMMED' if programmed else 'DEBUG_PROGRAMMING_FAILED' if 'programming_started=1' in raw_status else 'JTAG_CONNECTION_BLOCKED',
        source_commit=source['source_commit'],formal_RTL_modified=False,production_bit_unchanged=True,
        debug_bit_generated=True,debug_bit_sha256=sha(TASK/'ILA_DEBUG.bit'),debug_ltx_sha256=sha(TASK/'ILA_DEBUG.ltx'),
        source_DCP_sha256=sha(TASK/'results/debug_routed.dcp'),core_timing_pass=True,
        global_timing_converged=False,user_accepted_ILA_internal_setup_violations=True,accepted_ILA_setup_paths=7,
        WNS_ns=-0.164,TNS_ns=-0.653,WHS_ns=0.054,THS_ns=0.0,
        hardware_programmed=programmed,flash_programmed=False,latest_hardware_attempt=last.name,
        triggers=trigger_results,hardware_reason=raw_status.split('reason=')[-1].strip())
    (TASK/'results/STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    (TASK/'results/BOARD_ATTEMPT_STATUS.json').write_text(json.dumps(status,ensure_ascii=False,indent=2),encoding='utf-8')
    (TASK/'results'/last.name/'VALIDATED_TRIGGER_STATUS.json').write_text(json.dumps(trigger_results,indent=2),encoding='utf-8')
    result=f'''# 上板边沿配对错误ILA定位

本轮最新状态：**{status['status']}**。上一轮Debug结果的BIT已导出：**是**；上板配置完成：**{'是' if programmed else '否'}**。具体硬件记录见`results/{last.name}/HARDWARE_STATUS.txt`。

## 用户后续明确指令

用户明确要求“上次时序没通过是ila的原因就不用管了”“就是要烧录上一轮结果的bit”。因此从原冻结Debug路由DCP直接导出BIT/LTX，没有重新综合、布局布线、修改RTL或补偿参数。原来因时序门槛未导出BIT的记录保留在logs，未将原违例改写成时序收敛。

## 来源

源Commit：`{source['source_commit']}`，Git归档基点`31090be88d0fef94835f69a6edcff4e447328220`。实际生产来源为AD23版，顶层`tdc_meas_top`、器件`xc7k325tffg900-2`。原正式5个RTL及生产BIT再次核对SHA256未变。

- 冻结Debug DCP SHA256：`{status['source_DCP_sha256']}`。
- 本轮`ILA_DEBUG.bit` SHA256：`{status['debug_bit_sha256']}`，大小{(TASK/'ILA_DEBUG.bit').stat().st_size}字节。
- 配套`ILA_DEBUG.ltx` SHA256：`{status['debug_ltx_sha256']}`。
- Debug ILA UUID：`A912571AD1ED54D397583B5696DB5C21`；原100MHz ILA UUID仍为`005AAA8F6BEB5365914C104C10152EC8`。

## 逻辑和时序

正式测量算法修改：**否**。独立Debug副本仅导出已有候选/辅助/配对状态，增加影子寄存器、只读状态记录、两个32位错误计数器和ILA；candidate/Locate、TDL结构、辅助判断规则、FIFO格式、五级Locate、valid时序全部保持。

8个固定补偿参数ps保持：0° rise/fall=36081，90°=36011，180°=35742，270°=35756。ENABLE_SKEW_COMP=1。未重新校准。

原3512脉冲单次Debug理想RTL验证3512/3512，10类CSV逐字节一致；另有12017周期配对/触发检查，覆盖2097次A和2281次B事件。见results/FULL_RTL_EQUIVALENCE.json、RTL_VALIDATION.json。

生产全局WNS/TNS=-0.050/-0.166ns；Debug=-0.164/-0.653ns，WHS/THS=+0.054/0ns。核心和影子采集没有负裕量，7条ILA内部Setup路径按本轮用户要求接受。未关闭timing check、未添加false path、未重新实现。详细路径见TIMING_BEFORE_AFTER.md和results/authorized_debug_export/ACCEPTED_TIMING_EXCEPTIONS.csv。

## 探针和触发

`u_ila_edge_debug`使用0°500MHz，8个探针314位，1024深度、768触发位置、四拍ILA输入流水。包含确认前四相type/code、辅助ordered_samples/slots/match/claimed、确认结果、最终选择、timestamp、原rise_pending状态、最近配对记录和错误计数。所有影子寄存器只读，不反馈测量。

Trigger A=`error_event_valid && error_event_code==1`，probe0位0；Trigger B=`error_event_valid && error_event_code==2`，probe0位1。原100MHz `u_ila3`五探针保留，不用它近似替代500MHz瞬态。操作及精确位图见ILA_SIGNAL_MAP.md、TRIGGER_CONDITIONS.md。

硬件A/B结果：`{json.dumps(trigger_results,ensure_ascii=False)}`。只在原始CSV存在并观测到对应事件标志时确认捕获；不以超时或trigger_now冒充错误触发。

首次A/B等待各15秒超时，导出CSV只有表头、0采样行。旧脚本因Vivado超时未抛异常而在原日志误标CAPTURED，原日志原样保留；核验结果见results/{last.name}/VALIDATED_TRIGGER_STATUS.json，两类均不能确认捕获。脚本已加入1024行和实际事件位校验。随后普通活动快照在刷新阶段内存不足，没有获得普通活动CSV，不据此判断当前有无PWM输入或错误。

## 限制和保留记录

确认前pack是编码/范围筛选后的TDL候选，不是thermo_q；辅助ordered_samples是原有跨相位流水之后的真实电平记录，不是原相位第一层寄存器。仅凭这些ILA不能排除输入模拟毛刺。没有找到根因前不声称修复。

前期生产版重试遇到数据服务/目标占用及一次End of startup status LOW；相关失败日志和目录单独保留。用户澄清后不再用生产BIT替代，Debug硬件尝试只使用本轮4df6开头的BIT。用户重插C306 JTAG USB后执行新的硬件尝试；未自动烧写Flash。

## 文件和复现

生产来源与RTL副本在inputs，独立Debug源码在rtl，差异见RTL.diff；只读导出脚本为scripts/export_authorized_debug_bit.tcl，硬件脚本为scripts/capture_errors.tcl。真实ASCII运行目录：`{WORK.as_posix()}`，没有创建虚拟盘符。

保留原失败构建日志、正式参数及约束、前后时序报告、DCP、BIT/LTX、真实采集CSV/ILA（若有）。不大量上传IP缓存和重复仿真输出，3512对照的逐文件SHA证据已归档。文件清单见FILE_LIST.txt，重要文件SHA见SHA256SUMS.txt。

Git分支：`codex/2026-11-07-01-edge-pairing-ila-debug`，提交说明：`2026-11-07-01-上板边沿配对错误ILA定位`。后续实际Commit及推送核验在本地GIT_DELIVERY.json和执行反馈中记录。未合并main、未强推。
'''
    (TASK/'RESULTS.md').write_text(result,encoding='utf-8')
    timing=TASK/'TIMING_BEFORE_AFTER.md'
    content=timing.read_text(encoding='utf-8')
    content=re.sub(r'最终状态：TIMING_GATE_FAIL。[^\n]*',
        '初次门槛状态：TIMING_GATE_FAIL。后续用户明确接受7条ILA内部Setup违例，已从同一DCP导出Debug BIT；时序数值及违例本身未改变。',content)
    content=content.replace('BIT门槛：任何测量核心、影子采集、ILA或Hub路径有负Setup/Hold均停止BIT生成。',
        '初次BIT门槛包含ILA内部路径。后续按用户指令，仅接受已存在的7条ILA内部Setup路径，核心、影子采集及所有Hold仍保持无负裕量。')
    timing.write_text(content,encoding='utf-8')
    for name in ['ILA_SIGNAL_MAP.md','TRIGGER_CONDITIONS.md']:
        p=TASK/name;s=p.read_text(encoding='utf-8')
        note='\n最新状态：用户已明确接受原7条ILA内部Setup违例，本轮已导出同一Debug DCP的BIT/LTX；真实上板状态以RESULTS.md和results/STATUS.json为准。\n'
        if note not in s:s=s.replace('\n','\n'+note,1)
        s=s.replace('本表对应独立Debug源码。只有本次BIT通过路由及时序门槛后，才能用于上板定位；未生成BIT时不能据此声称已捕获硬件信号。',
            '本表对应本次已导出的独立Debug BIT。用户已明确接受原7条ILA内部Setup违例；测量核心和影子采集路径没有负裕量。实际错误触发是否取得波形须以原始采样行和事件位核验。')
        s=s.replace('采集脚本尚未上板执行。每种触发等待15秒；',
            '采集脚本已上板执行，Debug BIT配置成功，但首次A/B等待后CSV均为0采样行，不确认捕获。每种触发等待15秒；')
        p.write_text(s,encoding='utf-8')
    exclude={'SHA256SUMS.txt','FILE_LIST.txt','GIT_DELIVERY.json'}
    files=sorted(p for p in TASK.rglob('*') if p.is_file() and 'github' not in p.relative_to(TASK).parts and '__pycache__' not in p.parts and p.name not in exclude)
    (TASK/'SHA256SUMS.txt').write_text(''.join(f'{sha(p)}  {p.relative_to(TASK).as_posix()}\n' for p in files),encoding='utf-8')
    (TASK/'FILE_LIST.txt').write_text(''.join(f'{p.stat().st_size:>10}  {p.relative_to(TASK).as_posix()}\n' for p in files),encoding='utf-8')
    print(json.dumps(status,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
