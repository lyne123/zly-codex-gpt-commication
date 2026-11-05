"""逐条审查实际DCP导出的路径属性，不根据源码复杂度猜测违例。"""
from pathlib import Path
import csv
import re
from collections import Counter

ROOT = Path(__file__).resolve().parents[1]
rows=[]
for variant in ('baseline','compensated'):
    folder=ROOT/'results/original_inspection'/variant
    blocks=(folder/'setup_top50.rpt').read_text().split('Slack (')[1:]
    properties=(folder/'path_properties.txt').read_text().split('END_PATH')
    for rank,chunk in enumerate(properties,1):
        d=dict(line.split('\t',1) for line in chunk.strip().splitlines() if '\t' in line)
        if not d:continue
        start,end=d['STARTPOINT_PIN'],d['ENDPOINT_PIN']
        if 'u_ila' in start+end:
            module='厂商ILA IP'
            suggestion='保留ILA功能，优先针对实际内部路径进行物理/布线优化'
        elif 'u_tdc_fine_layer' in start+end:
            module='tdc_fine_layer.v'
            suggestion='在编码器本相位寄存范围判定，code/type/ready和辅助门控同步增加一拍'
        elif 'u_tdc_time_locate' in start+end:
            module='tdc_time_locate.v'
            suggestion='将中测常量减参数在展开时计算，Stage2选择，Stage3只做一次减法'
        elif 'u_tdc_time_candicate' in start+end:
            module='tdc_time_candicate.v';suggestion='按实际裕量评估，不改变候选优先级或冲突规则'
        elif 'u_tdc_time_merge' in start+end:
            module='tdc_time_merge.v';suggestion='按实际裕量评估，保留配对和错误标志'
        elif 'u_fifo_tdc' in start+end:
            module='厂商FIFO IP';suggestion='500MHz写指针至full标志路径，先评估物理/布线优化，不能按CDC豁免'
        else:
            module='FIFO/IP/顶层';suggestion='保留厂商CDC约束，检查端点和扇出'
        if float(d['SLACK'])>=0:suggestion='本路径没有违例；保留结构并在新实现中复核'
        block=blocks[rank-1] if rank<=len(blocks) else ''
        logic=re.search(r'Logic Levels:\s*\d+\s*\(([^\n]+)\)',block)
        rows.append(dict(variant=variant,rank=rank,startpoint=start,endpoint=end,
            launch_clock=d['STARTPOINT_CLOCK'],capture_clock=d['ENDPOINT_CLOCK'],
            requirement_ns=d['REQUIREMENT'],required_ns=d['REQUIRED_TIME'],arrival_ns=d['ARRIVAL_TIME'],
            slack_ns=d['SLACK'],logic_delay_ns=d['DATAPATH_LOGIC_DELAY'],net_delay_ns=d['DATAPATH_NET_DELAY'],
            logic_levels=d['LOGIC_LEVELS'],main_logic=logic.group(1) if logic else '见完整路径报告',rtl_module=module,recommendation=suggestion))
    assert sum(r['variant']==variant for r in rows)==50
out=ROOT/'results/SETUP_TOP50_REVIEW.csv'
with out.open('w',encoding='utf-8-sig',newline='') as f:
    w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
text=['# 原始时序根因审查','','版本先验核对通过：本地完整工程的五份RTL、两套BIT/DCP/SDF与上一轮Commit `fa5fd072d015dbcd03a2f7d2c895dc93bd72fca1`对应。没有用归档工程覆盖可运行工程。','','两版各提取50条最差Setup路径及50条Hold路径，并执行report_design_analysis、check_timing、report_cdc、时钟交互与例外检查。Vivado 2022.2不支持本次首次尝试的redirect命令，按本地help改为check_timing自身的-file，完整重新提取；首次失败日志也保留。','','## 已确认的物理瓶颈','','- Baseline最差为90°计1树最终寄存器→组合范围/极性判定→0°pack90_d1，预算1.500 ns；数据1.241 ns，其中逻辑0.309、布线0.932，跨相位时钟偏斜-0.276和不确定度0.180后Slack=-0.163 ns。不是候选排序器本身。','- Compensated最差为同类路径，Slack=-0.173 ns，逻辑0.380/布线0.896 ns；还存在locate Stage2→Stage3的mid−fine−offset串联减法，最差Slack=-0.080 ns、逻辑1.252 ns。','- 两版500 MHz ILA内部计数比较/触发路径存在真实同步Setup违例，不能删除ILA或添加例外来隐去。','- candidate、merge、FIFO是否需要修改，以逐条实际路径为依据；本轮不机械增加它们的流水级。','','## 最小优化方案（实施前记录）','','1. 四相编码器的最终code/type/ready增加同相位寄存级，把组合范围判定从1.5 ns跨相位路径移入2 ns同相位路径；辅助门控延迟同步+1。不改PWM树、CARRY4、采样FF、码值窗口、候选规则或粗计数机制。新增公共延迟需重新校准。','2. 保留locate原5级，把每个mid−offset的常量在综合展开时计算，Stage2按index/type选择，Stage3只减fine；8参数、符号位和模回卷算法保持等价。','3. ILA先使用合理的时序驱动物理/布线策略，保留全部探针和异常检测。无新false path/multicycle，无降频。','','## 约束与因果边界','','原始所有内部端点均有时钟/时序约束，PWM输入和外部复位2个输入未指定板级input delay；这些是原工程已知边界，本次不伪造板级预算。四相是相关时钟，不能按异步CDC豁免；500→100 MHz使用原独立时钟FIFO与厂商约束。板级IO签核与同步数字逻辑时序分别报告。','','已有物理报告只能解释Setup违例来源，不能证明20 MHz丢沿由这些违例导致。将实际运行原始/优化RTL与SDF四组对照，继续保留混合极性整帧丢弃规则。','','## 逐路径审查索引','','完整Startpoint/Endpoint、时钟、Required/Arrival、Logic/Net delay、Logic levels及建议见[SETUP_TOP50_REVIEW.csv](results/SETUP_TOP50_REVIEW.csv)。下面逐条列出模块、Slack与结论，原始完整时钟展开路径位于results/original_inspection。','','| 版本 | 序号 | 模块 | Slack ns | 主要逻辑 | 建议 |','|---|---:|---|---:|---|---|']
for r in rows:text.append(f"| {r['variant']} | {r['rank']} | {r['rtl_module']} | {r['slack_ns']} | {r['main_logic']} | {r['recommendation']} |")
(ROOT/'TIMING_ROOT_CAUSE.md').write_text('\n'.join(text)+'\n',encoding='utf-8')
print(Counter((r['variant'],r['rtl_module']) for r in rows if float(r['slack_ns'])<0))
