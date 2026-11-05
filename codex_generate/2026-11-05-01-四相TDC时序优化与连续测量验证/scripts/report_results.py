"""从实际完成的八组对照、路由报告和独立校准生成交付文档。"""
from pathlib import Path
import json
import re
import statistics
import experiment as e

ROOT=Path(__file__).resolve().parents[1]

def write(name,lines):
    (ROOT/name).write_text('\n'.join(lines)+'\n',encoding='utf-8')

def fmt(value):
    return f'{value:.3f}' if isinstance(value,(int,float)) and not isinstance(value,bool) else str(value)

def main():
    state=json.loads((ROOT/'results/analysis_summary.json').read_text(encoding='utf-8'))
    assert state['completed_cases']==8,'所有八组主对照完成后才能生成最终报告'
    cases={(c['phase'],c['variant'],c['level']):c for c in state['cases']}
    old=e.read_csv(ROOT/'inputs/old_tdc_skew_calibration.csv');new=e.read_csv(ROOT/'results/tdc_skew_calibration.csv')
    comp_meta=json.loads((ROOT/'results/calibration/optimized/compensated/gate/metadata.json').read_text(encoding='utf-8'))
    fitted={(r['sel_index'],r['polarity']):r for r in comp_meta['fitted_parameters']}
    oldmap={(int(r['sel_index']),r['polarity']):r for r in old}
    newmap={(int(r['sel_index']),r['polarity']):r for r in new}
    rows=[]
    for key,r in newmap.items():
        before=oldmap[key];f=fitted[key]
        zero_old=float(oldmap[3,key[1]]['bias_ps']);zero_new=float(newmap[3,key[1]]['bias_ps'])
        rows.append(dict(sel_index=key[0],phase=r['tdl_phase'],polarity=key[1],old_offset_ps=int(before['offset_ps']),
            new_baseline_fitted_offset_ps=int(r['offset_ps']),new_compensated_applied_offset_ps=int(r['offset_ps']),new_compensated_own_fitted_offset_ps=f['offset_ps'],
            delta_applied_ps=int(r['offset_ps'])-int(before['offset_ps']),old_mean_ps=before['bias_ps'],new_baseline_mean_ps=r['bias_ps'],new_compensated_mean_ps=f['bias_ps'],
            old_relative_to_0_ps=float(before['bias_ps'])-zero_old,new_relative_to_0_ps=float(r['bias_ps'])-zero_new,
            new_baseline_n=r['n'],new_compensated_n=f['n'],own_implementation_match=int(r['offset_ps'])==f['offset_ps']))
    e.write_csv(ROOT/'OLD_VS_NEW_CALIBRATION.csv',rows)
    calibration_lines=['# 独立物理校准报告','','固定校准文件为sim/stimuli/calibration.txt及对应真实边沿CSV，800脉冲；主验证3512脉冲完全独立，未参与拟合。上升沿、下降沿各自拟合四条通道。RTL扫描仅用于建立事件关联，不作为物理补偿参数。','','对raw.csv中mask有效的通道记录：`Traw = ((Craw+6) mod 1024)*2000 + mid[index] - fine`，按2048000 ps取模；mid按sel_index0/1/2/3为500/1000/1500/2000 ps，对应90/180/270/下一周期0°。Rise的fine=code*10 ps，Fall的fine=(64-code)*10 ps。','每个raw帧使用同极性最近的真实边沿，计算带符号模回卷误差`error = circular(Traw - ((Ttrue-epoch) mod 2048000))`。按通道及极性取均值，`offset_ps=round(mean(error))`，Python round在恰好半整数时取最近偶数。未另行剔除离群样本，mask无效帧不属于该通道测量。','原始观察记录、每相位覆盖和样本数量分别在results/calibration/*/*/gate/observations.csv、phase_coverage.csv、fitted_parameters.csv。一个输入事件可产生多个相位有效帧，raw样本数量之和可大于选中输出的1600个边沿。','','参数包含公共流水线、输入分发及本实现粗时间参考epoch下的绝对偏移。结构新增一拍为2 ns，但两版绝对参数之差还包含物理路径/clock epoch变化，不能全部解释为公共流水线增量。OLD_VS_NEW_CALIBRATION.csv同时给出相对0°通道偏差，用于分离公共项与相对固定延迟。','','| 通道 | 极性 | 新Baseline均值(ps) | 应用参数(ps) | 补偿实现自身拟合(ps) | 样本n(B/C) | 一致 |','|---|---|---:|---:|---:|---:|---|']
    for r in rows:calibration_lines.append(f"| {r['phase']}° | {r['polarity']} | {float(r['new_baseline_mean_ps']):.6f} | {r['new_compensated_applied_offset_ps']} | {r['new_compensated_own_fitted_offset_ps']} | {r['new_baseline_n']}/{r['new_compensated_n']} | {r['own_implementation_match']} |")
    calibration_lines+=['','先冻结新Baseline的DCP/网表/SDF，再由该实现的独立扫描冻结8参数，随后独立综合Compensated；最后使用补偿实现自身网表/SDF再次扫描，检查与应用参数逐项一致。主验证不反向调整参数。对应SHA在每批input_sha256.json、最终SOURCE_PROVENANCE.json及交付清单中。',f"补偿实现自身拟合与应用值全部一致：**{comp_meta['fitted_matches_applied']}**。若为False，Compensation必须FAIL，不把不同实现的偏移混称为同一校准。"]
    calibration_lines+=['','10 ps/tap是当前RTL的时间换算系数，校准没有重新拟合bin宽；这不表示每个物理tap的SDF延迟恰好为10 ps。']
    write('CALIBRATION_REPORT.md',calibration_lines)
    static=state['static'];timing_ok=all(static['optimized_'+v]['timing']['synchronous_timing_pass'] for v in ['baseline','compensated'])
    def functional(c):
        s=c['summary'];f=c['fifo']
        return s['valid_matched_pulses']==s['expected_pulses'] and not s['missing_rise_ids'] and not s['missing_fall_ids'] and not s['duplicate_rise_ids'] and not s['duplicate_fall_ids'] and not s['faults'] and not s['business_errors'] and f['result_sequence_equal'] and f['error_sequence_equal'] and not f['overflow_observation_cycles'] and not f['unknown_observation_rows']
    functional_ok=all(functional(cases['optimized',v,'gate']) for v in ['baseline','compensated'])
    base=cases['optimized','baseline','gate']['summary'];comp=cases['optimized','compensated','gate']['summary']
    comp_ok=comp_meta['fitted_matches_applied'] and base['stimulus_sha256']==comp['stimulus_sha256'] and base['missing_rise_ids']==comp['missing_rise_ids'] and base['missing_fall_ids']==comp['missing_fall_ids'] and all(f['kind']=='mispair' for f in comp['faults']) and len(comp['faults'])<=len(base['faults'])
    cf=cases['optimized','compensated','gate']['fifo']
    comp_ok=comp_ok and not comp['duplicate_rise_ids'] and not comp['duplicate_fall_ids'] and cf['result_sequence_equal'] and cf['error_sequence_equal'] and not cf['overflow_observation_cycles'] and not cf['unknown_observation_rows']
    acceptance=dict(timing_pass=timing_ok,functional_pass=functional_ok,compensation_pass=comp_ok,overall='PASS' if timing_ok and functional_ok and comp_ok else 'FAIL')
    (ROOT/'results/final_acceptance.json').write_text(json.dumps(acceptance,indent=2),encoding='utf-8')
    timing_lines=['# 时序与资源前后对照','','500 MHz保持不变；没有新增false path/multicycle，也没有关闭任何timing check。重要内部端点时钟约束完整；PWM和复位2个外部异步输入仍缺板级input delay，板级IO签核另列为未执行。','','| 指标 | 原Baseline | 优化Baseline | 原Compensated | 优化Compensated |','|---|---:|---:|---:|---:|']
    tags=['original_baseline','optimized_baseline','original_compensated','optimized_compensated']
    for key in ['wns_ns','tns_ns','whs_ns','ths_ns','wpws_ns','tpws_ns','setup_failing','hold_failing','pulse_width_failing','setup_endpoints','hold_endpoints','bus_skew_min_slack_ns']:
        timing_lines.append('| '+key+' | '+' | '.join(fmt(static[t]['timing'][key]) for t in tags)+' |')
    timing_lines+=['','## 实际资源','','| 资源 | 原Baseline | 优化Baseline | 原Compensated | 优化Compensated |','|---|---:|---:|---:|---:|']
    for key in ['Slice LUTs','Slice Registers','Block RAM Tile','CARRY4']:
        timing_lines.append('| '+key+' | '+' | '.join(str(static[t]['resources'][key]) for t in tags)+' |')
    timing_lines+=['','优化包含RTL及映射/物理策略变化，资源差异不能全部归因于新增寄存级。编码器code/type/ready与辅助门控共同+1周期（2 ns）；候选器5级、locate5级、merge和FIFO逻辑规则保持。','',f'500 MHz同步STA：**{"PASS" if timing_ok else "FAIL"}**。各版本完整Setup/Hold、check_timing、时钟交互、例外、CDC和路由报告在results/original_inspection与results/optimized。']
    write('TIMING_BEFORE_AFTER.md',timing_lines)
    continuous=['# 连续PWM测量验证','','主激励SHA256：`451a2cb59cc0704a9e5ac8454bb983237543705f2c4782789b3067be4d9fa76f`。所有组使用同一文件、事件编号、真实边沿时间；没有重随机生成或改变异常处输入。RTL模型为理想原语功能模型，SDF为真实路由后slow/MAX。','','| 阶段 | 版本 | 模型 | 正确配对/3512 | 丢R | 丢F | 重复R/F | 错配 | 结果/错误FIFO序列 |','|---|---|---|---:|---:|---:|---|---:|---|']
    for key,c in cases.items():
        s=c['summary'];f=c['fifo'];n=sum(x['kind']=='mispair' for x in s['faults'])
        continuous.append(f"| {key[0]} | {key[1]} | {key[2]} | {s['valid_matched_pulses']}/3512 | {len(s['missing_rise_ids'])} | {len(s['missing_fall_ids'])} | {len(s['duplicate_rise_ids'])}/{len(s['duplicate_fall_ids'])} | {n} | {f['result_sequence_equal']}/{f['error_sequence_equal']} |")
    continuous+=['','每个测试项目的预期/实际升降沿、重复边沿、配对/错配、RMSE/Bias/STD/MaxAbs和有效率见[ALL_CASE_METRICS.csv](results/ALL_CASE_METRICS.csv)。错配归属按下降沿参考ID记录；所有异常输出仍保存在measurements.csv，不用行号强行对齐。','完整性失败时全量指标N/A，成功子集conditional指标单列；没有删除异常后宣称整体通过。ATC帧仍是16×(64+2)=1056的暂定协议，不等同真实芯片协议验收。','','## 因果对照','', '原Baseline本轮SDF全量7份关键CSV与上一轮逐字节一致。独立raw→候选器重放7019个输出及3个冲突时间完全一致，见candidate_replay_verification.json；混合极性整帧丢弃是确定性规则，暂未改为多事件队列。']
    old_s=cases['original','baseline','gate']['summary']
    if timing_ok and (base['missing_rise_ids'] or base['missing_fall_ids']):
        continuous.append('优化后同步STA已满足500 MHz而SDF仍漏沿：属于对照D，不能仅靠Setup收敛解决。给定真实混合极性四相帧，原算法必然丢帧；前端异步采样、辅助门控与帧边界形成这些候选的关系需继续审查。')
    elif functional_ok:
        continuous.append('本批优化SDF中异常消失，属于对照C。时序与物理布局/SDF采样窗口同时改变，现有数据不能把消失唯一归因于Setup修复；同一旧raw输入仍会触发原候选规则。')
    else:
        continuous.append('尚未建立两个版本都无同步Setup违例的最终对照，不能排除同步时序影响。raw重放只证明给定四相帧时的算法响应，不单独证明物理成因。')
    for phase in ['original','optimized']:
        for v in ['baseline','compensated']:
            s=cases[phase,v,'gate']['summary']
            continuous.append(f"- {phase}/{v}：丢R `{s['missing_rise_ids']}`，丢F `{s['missing_fall_ids']}`；事件级错误及逐周期接口轨迹在该批次目录。")
    old_ids=set(old_s['missing'])
    still=old_ids & (set(base['missing']) | set(comp['missing']) | set(base['duplicate']) | set(comp['duplicate']))
    continuous+=['',f'原五个错误脉冲ID为{sorted(old_ids)}；其中在新两版仍未得到唯一正确脉宽的ID为{sorted(still)}。不能用旧ID修复掩盖其他位置的新异常。',
        '冷打开两份最终DCP并update_timing -full的fresh_*报告已核对原导出结果。Base剩余14条Setup均在ILA2，失败寄存器扇出不返回TDC/FIFO；Comp另有locate回卷/选择到timestamp的−0.019 ns路径，向后可到13个merge端点。详见negative_setup_reachability.csv和module_worst_setup.csv。ILA隔离证据不能替代剩余测量路径STA签核。',
        'SDF为标称时钟的确定性slow/MAX仿真，STA还包含clock uncertainty等预算；没有动态同步setuphold告警不能据此宣布STA通过。']
    continuous+=['','候选冲突/repeat标志由TB独立记录，原工程没有把它们全部接入错误FIFO；错误FIFO只核对实际merge错误入队序列。TDL异步setup/hold、同步数字逻辑、复位和MMCM未用输出的模型告警分别统计，不全局豁免。']
    continuous+=['','## 新版本的直接机制与旧版不同','','新两版errors.csv均无polarity_conflict、repeat或merge错误，但仍有3R/3F缺失和3错配。三份前端原始数据raw.csv、candidate.csv、sampled_taps.csv在新Base/Comp之间逐字节一致。未修改的理想候选RTL重放新raw，7018个输出的时间、极性、索引和码值全部精确重现，冲突数量为0，见optimized_candidate_replay_verification.json。因此不能把新漏沿直接套用旧版的3次混合极性冲突解释。',
        'MISSING_RAW_EDGE_REVIEW.csv进一步检查真值后12–32 ns的原始有效通道（独立校准观察延迟约21–23 ns）：三个缺失Rise窗口内没有有效Rise通道；三个缺失Fall窗口内的有效Fall信息更吻合后一帧头下降沿，距离前一真实Fall仍有3.7–4.3 ns误差，远超校准残差131 ps范围。该表仅用于定位，不筛除或修改RMS样本。',
        '现有证据把新异常定位到候选输入的有效样本形成/保留之前；还不能在TDL编码、异步辅助检测及confirm_edge门控之间确定唯一成因。Base测量数字路径STA为正且剩余ILA失败不回馈测量通路，进一步说明不能只用同步Setup违例解释这些新漏沿。Comp仍有−0.019 ns测量路径预算违例，整体验收继续FAIL。下一轮需要增加前端内部观察，未在本轮改候选规则或引入多事件队列。']
    write('CONTINUOUS_PWM_VALIDATION.md',continuous)
    sdf_lines=['# 实现后SDF验证','','Vivado2022.2、xc7k325tffg900-2、simprims_ver/7系列器件模型，slow/MAX、1 ps。每版DCP、实际导出网表、SDF及运行输入均有SHA256；静态$sdf_annotate文件和xelab --maxdelay对应，原文件未编辑。','','| 阶段 | 版本 | SDF单元数 | 关键单元 | 主验证注释成功 | 主验证时序告警 |','|---|---|---:|---|---|---:|']
    for phase in ['original','optimized']:
        for v in ['baseline','compensated']:
            audit=json.loads((ROOT/'results'/phase/v/'sdf_audit.json').read_text(encoding='utf-8'))
            main_case=next(x for x in audit['cases'] if x['case']=='gate_validation')
            sdf_lines.append(f"| {phase} | {v} | {audit['total_sdf_cells']} | 64 CARRY4 / 256 FF / 7 LUT1 | {main_case['annotation_success']} | {main_case['total_timing_warnings']} |")
    sdf_lines+=['','完整scope分类、5us前/后统计及原异常窗口告警在各批次timing_violation_counts/scopes.csv和原simulation.log。关键单元清单覆盖不是全局逐路径注释百分比；没有虚构工具未提供的成功率。','原Baseline的109条ILA告警来自ILA3异步PWM探针（bit27和G_NMU[4]），DCP扇入追踪见original_ila_pwm_warning_fanin.txt；不能当作ILA2同步计数器违例。TDL85,549条、PWM同步器383条、启动复位2条独立分类；MMCM未用CLKOUT5/6 period告警原因仍未获确认。','原Baseline本轮使用已有O2/typical快照，新编译采用官方O3/debug off加速计算，MAX SDF、timing checks及transport/pulse参数保持；原Compensated全量O3与原冻结O2的逐事件一致性记录作为编译优化对照。','上板、PVT/其他动态时序角及完整板级IO预算未执行。数值可输出不能代替亚稳态或硅片精度签核。']
    write('SDF_VALIDATION.md',sdf_lines)
    review=['# RTL修改审查','','本次正式源码与归档副本仅修改两份Verilog：','','- `tdc_fine_layer.v`：四个编码器在本相位寄存code/type/ready，将范围判定从1.5 ns跨相位路径移到2 ns同相位路径；aux门控INDEX从5到6，窗口宽度保持两拍。','- `tdc_time_locate.v`：8个mid−offset在展开时计算，Stage2选择并寄存，Stage3只减fine；保持18位signed参数、19位relative、模回卷、显式旁路和原5级valid/type。','','PWM分发7个LUT1、64个CARRY4、256个采样FF、tap数/意义、采样极性、粗计数机制、候选选择/混合极性规则、merge配对和错误标志均保留。候选器、merge、顶层未修改。原版本在original/{baseline,compensated}/rtl，后版本在rtl，差异在RTL_CHANGES.patch。','','自动化验证：完整冻结激励134238周期/7270有效四相帧逐拍等价原版延后一拍；CW=2/10各5044次补偿测试，覆盖8映射、signed极值、复位、连续valid、零参数、旁路和多次回卷。硬件新增延迟只有前端1拍；绝对偏移重新校准，未沿用旧参数冒充新实现。']
    review+=['','## 物理实现分支','','BRAM优化在重布局前执行，将工具确认不需要READ_FIRST的ILA trace端改为NO_CHANGE，修复最小周期违规；路由后执行会被跳过的失败尝试亦保留。依据实际ILA计数/复位路径的布线瓶颈尝试驱动复制与局部布局；54 Slice试验容量不足，扩展为80 Slice后再验证。没有对TDL添加新Pblock或改变其LOC。完整实际试验及参数见PHYSICAL_TRIALS.csv、SOURCE_PROVENANCE.json和执行日志。','测试平台按网表真实粗计数总线名选择观察点宏；这是只读观察适配，不修改网表或测量算法。首次名称不匹配的失败展开日志保留。']
    review+=['','AUX_GATE_INDEX旁的旧bit4说明为遗留注释，旧实现实际常量为5，新实现为6；以代码及完整激励逐拍对齐断言为准。冻结后未再修改RTL注释或源码，相关SHA保持一致。']
    write('RTL_CHANGE_REVIEW.md',review)
    final=['# 最终实验报告','',f"**整体验收：{acceptance['overall']}。**",'',f"Timing（500 MHz同步STA）：{'PASS' if timing_ok else 'FAIL'}；Functional：{'PASS' if functional_ok else 'FAIL'}；Compensation：{'PASS' if comp_ok else 'FAIL'}。",'', '本次基于上一轮完整本地工程和Commit fa5fd072d015dbcd03a2f7d2c895dc93bd72fca1，经版本核对后独立构建，没有覆盖旧BIT/DCP或原数据。', '', '## 修改与时序根因','','仅fine_layer与locate两份RTL修改。实际原始违例包括跨相位范围判定、补偿串联减法、ILA内部和错误FIFO写指针/full路径，详见TIMING_ROOT_CAUSE.md及100条路径CSV。前端增加1拍并整体对齐，补偿常量折叠，结合PerfOptimized_high/Explore/post-route AggressiveExplore；没有降频或新增时序例外。','','完整时序和资源对照见[TIMING_BEFORE_AFTER.md](TIMING_BEFORE_AFTER.md)，连续测量及因果边界见[CONTINUOUS_PWM_VALIDATION.md](CONTINUOUS_PWM_VALIDATION.md)。','','## 新参数（ps）','','| 相位 | Rise | Fall |','|---|---:|---:|']
    for phase,i in [(0,3),(90,0),(180,1),(270,2)]:final.append(f"| {phase}° | {newmap[i,'rise']['offset_ps']} | {newmap[i,'fall']['offset_ps']} |")
    final+=['','这些绝对值包含公共流水线与输入分发延迟；结构新增公共延迟2 ns。OLD_VS_NEW_CALIBRATION.csv同时给出相对0°通道差、R/F独立统计、最终补偿实现自己的拟合值及一致性。硬件参数只来自独立post-route校准，验证数据未参与拟合。','','## 精度与文件','','全部RMSE/Bias/STD/MaxAbs和样本数量在RMS_COMPARISON.csv及逐事件CSV。RMSE=sqrt(mean(error²))，Bias=mean(error)，STD为总体去均值标准差；漏沿/错配时全量N/A，条件统计明确区分。','10 MHz完整暂定帧与10 MHz/50%是两个不同项目；原135.602→53.147、143.269→69.735、125.406→66.700 ps的证据保留在原始对照。','','- 新Baseline BIT：results/optimized/baseline/Baseline_Optimized.bit','- 新Compensated BIT：results/optimized/compensated/Compensated_Optimized.bit','- 对应DCP、SDF、网表及Setup/Hold在各版本同目录。','- 原始CSV、正常/失败日志、真实边沿、编译TB快照和SHA均保留。','','## 限制与下一步','','500 MHz已收敛与否以实际表格为准，不能用RMSE改善代替时序或功能通过。若混合极性丢帧仍在，后续单独审查帧边界、辅助同步窗口及多事件处理能力，本轮没有引入多事件队列。','MMCM未用输出模型警告、异步TDL模型与硅片亚稳态差异、真实ATC协议、板级IO延迟和PVT仍需独立确认。','首轮并行IP内存不足、Debug Hub嵌套库加载及中文工作目录TclStackFree等工具失败均保留，采用串行、独立官方生成脚本和U盘原生工作目录恢复。','Git以独立分支codex/2026-11-05-01-tdc-timing-optimization归档；每个版本由本目录所属Git提交及文件SHA追溯，实际推送Commit ID在执行反馈给出。']
    final+=['','## 证据保留边界','','首轮Vivado原生run目录的部分中间报告/检查点随reset_run被工具清理；该轮61份最终导出证据已冻结并记录SHA，原始旧实验及主仿真CSV均保持。详见[EVIDENCE_LIMITATIONS.md](EVIDENCE_LIMITATIONS.md)。后续从独立DCP分支继续，不用重生成文件冒充已遗失的原文件。']
    final+=['',f"补偿实现自身相位扫描与实际应用8参数逐项一致：**{comp_meta['fitted_matches_applied']}**。不一致时Compensation必须FAIL，不能把Baseline拟合值称为补偿实现自身拟合值。",'', '按事件ID连接的八组全量对照见results/EVENT_COMPARISON.csv；原异常及新异常重点审查表见results/ANOMALY_EVENT_REVIEW.csv，完整逐周期接口轨迹仍保留在各批次目录。', '',
        '实际补偿顶层采用独立非工程综合；增量RuntimeOptimized自动覆盖了请求的place/phys/route策略。SOURCE_PROVENANCE.json和原始日志给出实际生效策略。冷打开DCP并完整更新时序后的fresh_*报告与正式导出指标一致，未用瞬态优化估计代替最终结果。', '',
        '追加发现ILA2原始生成OOC约束为10 ns（100 MHz），集成约束仍为2 ns（500 MHz）。这是需优先核查的IP综合目标差异，不是本轮已证明的唯一根因。本轮未执行2 ns OOC映射对照；下一轮应独立建立正确IP综合目标并验证合法性/映射，再处理locate Stage5回卷与选择路径，重新做物理校准和完整SDF。原XDC证据在inputs/ILA_OOC_TIMING_EVIDENCE，未修改厂商生成文件。']
    final+=['','## 实测结果摘要','','| 版本 | WNS ns | TNS ns | WHS ns | THS ns | Setup失败数 |','|---|---:|---:|---:|---:|---:|']
    for v in ['baseline','compensated']:
        t=static['optimized_'+v]['timing']
        final.append(f"| {v} | {t['wns_ns']:.3f} | {t['tns_ns']:.3f} | {t['whs_ns']:.3f} | {t['ths_ns']:.3f} | {t['setup_failing']} |")
    final+=['',f"新两版均正确配对{base['valid_matched_pulses']}/{base['expected_pulses']}（{base['valid_rate']*100:.4f}%），丢Rise {len(base['missing_rise_ids'])}、Fall {len(base['missing_fall_ids'])}，错配3。与原版3R/2F/2错配相比，多丢Fall事件3049并增加1次错配；没有重复事件或FIFO溢出。",'',
        '新版本polarity_conflict、repeat、merge错误均为0，仍不能通过功能验收。理想候选RTL重放新raw精确得到7018个输出且0冲突；旧版3次混合极性冲突的机制不能直接套用到新漏沿。前端有效样本缺失/失真与辅助确认门控需要进一步内部观察，详见CONTINUOUS_PWM_VALIDATION.md。', '',
        '| 测试 | 原Base RMSE ps | 原Comp RMSE ps | 新Base RMSE ps | 新Comp RMSE ps | 样本数 |','|---|---:|---:|---:|---:|---:|']
    for test,label in [('fixed_25300','25.3 ns'),('20MHz_50','20 MHz / 50%'),('ATC_10MHz','10 MHz暂定帧'),('10MHz_50','10 MHz / 50%')]:
        gs=[cases[p,v,'gate']['summary']['groups'][test] for p,v in [('original','baseline'),('original','compensated'),('optimized','baseline'),('optimized','compensated')]]
        final.append('| '+label+' | '+' | '.join(f"{g['rmse_ps']:.3f}" if g['complete'] else 'N/A' for g in gs)+f" | {gs[0]['expected_n']} |")
    final+=['','新补偿相对新Base能减少固定延迟偏差，但相对原Comp的上述三个非零RMSE均有退化。完整帧丢沿/错配项目的全量RMSE标N/A；成功子集指标仅作条件统计，不替代完整验收。']
    write('FINAL_REPORT.md',final)
    status=['# 测试执行状态','','以下PASS指该项脉冲/边沿完整性及配对检查，不等同500 MHz Timing PASS，也不另设未约定的精度门槛。精度数值见RMS_COMPARISON.csv。','','| 测试 | 新Base正确/预期 | 新Comp正确/预期 | 完整性状态 |','|---|---:|---:|---|']
    for test in ['fixed_25300','10MHz_50','20MHz_50','10MHz_5','10MHz_95','20MHz_5','20MHz_95','ATC_10MHz','ATC_20MHz','header_5','header_95','spwm_data']:
        b=base['groups'][test];c=comp['groups'][test]
        status.append(f"| {test} | {b['matched_unique_n']}/{b['expected_n']} | {c['matched_unique_n']}/{c['expected_n']} | {'PASS' if b['complete'] and c['complete'] else 'FAIL'} |")
    status+=['','四组RTL主验证各3512/3512正确；原两组SDF各3507/3512，新两组SDF各3506/3512。八组主验证全部正常结束。','独立800脉冲物理相位扫描、补偿signed/零值/旁路/回卷测试及前端完整激励逐拍对齐均已执行。','500 MHz整体STA：FAIL；两份新BIT已生成，不能把BIT成功生成当作时序通过。','未执行：2 ns ILA OOC映射对照、板级IO完整预算、上板、其他PVT动态角、真实ATC协议验收，以及前端内部编码/辅助确认门控的分离观察。']
    write('TEST_STATUS.md',status)
    write('README.md',['# 四相TDC时序优化与连续测量验证','',f"本次整体验收 **{acceptance['overall']}**；Timing={acceptance['timing_pass']}，Functional={acceptance['functional_pass']}，Compensation={acceptance['compensation_pass']}。",'',
        '- [完整结论](FINAL_REPORT.md)、[真实原始根因](TIMING_ROOT_CAUSE.md)、[RTL修改与对齐](RTL_CHANGE_REVIEW.md)。',
        '- [时序/资源对比](TIMING_BEFORE_AFTER.md)、[连续PWM与因果边界](CONTINUOUS_PWM_VALIDATION.md)、[SDF核对](SDF_VALIDATION.md)。',
        '- [独立物理校准](CALIBRATION_REPORT.md)、[8参数前后及自身拟合](OLD_VS_NEW_CALIBRATION.csv)、[全部RMSE/Bias/STD/MaxAbs](RMS_COMPARISON.csv)。',
        '- [测试执行状态](TEST_STATUS.md)、[复现说明](REPRODUCE.md)、[物理试验清单](PHYSICAL_TRIALS.csv)、[已知证据保留缺口](EVIDENCE_LIMITATIONS.md)。',
        '- results/optimized/{baseline,compensated}：两份新BIT、DCP、实际网表/SDF及完整冷重算Setup/Hold报告。',
        '- original/{baseline,compensated}/rtl与rtl：优化前后完整5份RTL；RTL_CHANGES.patch只改两文件。',
        '- results/EVENT_COMPARISON.csv为八组3512事件完整连接，ANOMALY_EVENT_REVIEW.csv为重点事件审查；原始测量不被这些派生表替换。',
        '- 原始激励/真值、CSV、正常/失败日志均保留。大log/jou采用gzip无损压缩，ARCHIVE_MAPPING.csv记录原SHA，SHA256_MANIFEST.json和FILE_LIST.csv给出交付清单。', '',
        '根目录少量仅含表头的CSV来自最初启动诊断；主实验CSV以results各批次目录为准。scripts/legacy_*为历史参考，主复现入口见REPRODUCE.md，不重新生成或替换冻结激励。',
        '归档保留必要工程配置、XDC/XCI、实际IP产品和失败小型dump；未加入批量编译对象、可再生运行程序、波形缓存及.Xil。完整本地任务目录仍保留。没有用这些可再生缓存替代关键原始CSV、SDF、BIT、DCP或失败日志。',
        '实际请求策略和生效策略可能不同：补偿顶层最终采用独立非工程综合，增量默认RuntimeOptimized覆盖了请求的place/phys/route指令；SOURCE_PROVENANCE.json与日志给出实际情况。TimingClosure试验的瞬态估计不作最终结果。'])
    print(json.dumps(acceptance))

if __name__=='__main__':main()
