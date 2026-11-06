"""全部验收通过后采用三处最小RTL修改，并整理可校验交付；不烧录硬件。"""
from pathlib import Path
import csv,difflib,hashlib,json,shutil,subprocess

TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxmatch_20261107_03'
IMPL=WORK/'implementation_fifo_reuse2'
NAMES=['tdc_fine_layer.v','tdc_meas_top.v','tdc_time_candicate.v','tdc_time_locate.v','tdc_time_merge.v']

def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()

def load(p):return json.loads(p.read_text(encoding='utf-8'))
def dump(p,x):p.write_text(json.dumps(x,ensure_ascii=False,indent=2),encoding='utf-8')
def rows(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

assert load(TASK/'implementation/BIT_MANIFEST.json')['pass_all']
assert load(TASK/'results/I_confirmation_pipe/RTL_STAGE_GATE.json')['pass_all']
assert load(TASK/'results/I_confirmation_pipe/backend/SUMMARY.json')['pass_all']
minimal=load(TASK/'results/sdf/corrected/minimal/SUMMARY.json')
after=load(TASK/'results/sdf/corrected/full/SUMMARY.json')
before=load(TASK/'results/sdf/baseline/full/SUMMARY.json')
assert minimal['MAX_SDF_pass'] and after['MAX_SDF_pass'] and after['correct_pairs']==3512
assert sha(IMPL/'corrected_routed.dcp')==load(TASK/'results/sdf/corrected/ANNOTATION.json')['DCP_sha256']
subprocess.run(['python',str(TASK/'scripts/compare_precision.py')],check=True)

initial=load(TASK/'inputs/SOURCE.json')
changed=['tdc_fine_layer.v','tdc_meas_top.v','tdc_time_locate.v']
# 先检查全部五个文件，再写入任何正式文件，保护运行期间可能存在的用户修改。
for name in NAMES:
    assert sha(ROOT/'fpga_tdc_v3_cal_rtl'/name)==initial['formal_RTL_sha256'][name],name
for name in changed:shutil.copy2(TASK/'variants/I_confirmation_pipe'/name,ROOT/'fpga_tdc_v3_cal_rtl'/name)
for name in NAMES:
    assert sha(ROOT/'fpga_tdc_v3_cal_rtl'/name)==sha(TASK/'variants/I_confirmation_pipe'/name)
for reference,filename in [('reference_F/rtl','RTL.diff'),('production_original/rtl','PRODUCTION_RTL.diff')]:
    diff=[]
    for name in NAMES:
        old=(TASK/reference/name).read_text(encoding='utf-8').splitlines(keepends=True)
        new=(TASK/'variants/I_confirmation_pipe'/name).read_text(encoding='utf-8').splitlines(keepends=True)
        diff.extend(difflib.unified_diff(old,new,fromfile=f'{reference}/{name}',tofile=f'variants/I_confirmation_pipe/{name}'))
    (TASK/filename).write_text(''.join(diff),encoding='utf-8')
for name in ['corrected_routed.dcp','post_route_max.sdf','post_route_timing.v','effective_constraints.xdc']:
    assert not (TASK/'implementation'/name).exists()
    shutil.copy2(IMPL/name,TASK/'implementation'/name)
shutil.copy2(WORK/'implementation_I/corrected_synth.dcp',TASK/'implementation/corrected_synth.dcp')
subprocess.run(['python',str(TASK/'scripts/collect_timing.py')],check=True)

old_bits={
 'production':(ROOT/'codex_generate/2026-11-06-02-PWM-AD23/results/TDC_Compensated_ILA100M_PWM_AD23.bit','c3c5d5e5afcdab910a59da3d7a1897f1e25450266621569cf50ad819f824a35a'),
 'debug':(ROOT/'codex_generate/2026-11-07-01-上板边沿配对错误ILA定位/ILA_DEBUG.bit','4df6b364eda1511abf910637ad8edb64bc518cb092de91f53e7a567736ed58e7')}
protected={}
for label,(p,digest) in old_bits.items():
    assert sha(p)==digest,label
    protected[label]=dict(path=str(p),sha256=digest,unchanged=True)
core=rows(IMPL/'after/core_timing.csv')
validation=dict(pass_all=True,archive_ready=True,base_commit=initial['base_commit'],variant='I_confirmation_pipe',
    F_function_rules_preserved=True,F_cycle_equivalent=False,F_equal_after_known_delay=True,
    added_frontend_cycles=1,added_latency_ps=2000,Locate_pipeline_stages=5,
    modified_formal_RTL=changed,formal_sha256={name:sha(ROOT/'fpga_tdc_v3_cal_rtl'/name) for name in NAMES},
    frozen_8_parameters_ps=dict(rise=[36081,36011,35742,35756],fall=[36081,36011,35742,35756],phase_order=[0,90,180,270]),
    parameters_refitted=False,TDL_structure_changed=False,FIFO_configuration_changed=False,
    candidate_merge_logic_changed=False,new_timing_exceptions=False,
    core_setup_negative_endpoints=0,core_hold_negative_endpoints=0,
    core_setup_min_ns=min(float(r['slack_ns']) for r in core if r['delay_type']=='max'),
    core_hold_min_ns=min(float(r['slack_ns']) for r in core if r['delay_type']=='min'),
    global_WNS_ns=-0.050,global_TNS_ns=-0.166,global_WHS_ns=0.054,global_THS_ns=0,
    historical_ILA_negative_endpoints=14,real_sample731_recovered=True,guard_cases=262144,
    RTL_PWM_pulses_per_group=1344,RTL_PWM_groups=3,
    minimal_MAX_SDF=minimal,full_MAX_SDF=after,baseline_full=before,
    Corrected_bit_generated=True,hardware_programmed=False,old_bits=protected)
dump(TASK/'VALIDATION.json',validation)

comparison=load(TASK/'results/PRECISION_COMPARISON.json')
metrics=comparison['metrics']
table=['| 样本群 | 版本 | N | Bias ps | RMSE ps | STD ps（样本） | MaxAbs ps |','|---|---|---:|---:|---:|---:|---:|']
for r in metrics:
    if r['group']=='all':table.append(f"| {r['population']} | {r['version']} | {r['n']} | {r['bias_ps']:.3f} | {r['rmse_ps']:.3f} | {r['std_sample_ps']:.3f} | {r['max_abs_ps']} |")
results=f'''# 验收结果：PASS（数字仿真与核心时序）

基于 `{initial['base_commit']}` 的 F 功能规则，采用 I 专用确认流水级及实际生产 FIFO 物理位置复用。真实 ILA 样本 731 的下降沿恢复；262144 组组合保护检查、三组各 1344 脉冲完整 RTL 对照及后端错误/回卷检查通过。没有改变 8 个补偿参数、TDL 编码、相位优先级、候选/配对规则或 FIFO 数据格式。

## 功能与延迟

F 的原确认优先、整帧为空才回退、纯极性、唯一未 claimed 的 previous 事件和防重复归属规则保留。与 F 在已声明的固定一拍延迟后输出数值逐位一致，**不是同拍等价**。500 MHz 全测量束、时间戳、脉宽与错误晚 2 ns；Locate 本体仍五级，通过粗计数影子保持原事件的数值。100 MHz FIFO 检查数量/顺序/数据/错误码一致，不承诺固定到达时差。修改三个 RTL：fine_layer、time_locate、meas_top；Candidate、Merge、约束输入及四个 IP 配置不变。

## MAX-SDF

XSim 2022.2、slow/MAX、simprims_ver/secureip，严格全局 SDF 注释成功，未出现未匹配诊断，时序检查全部开启。112 脉冲最小测试和原始 3512 脉冲完整测试均通过：完整输入上升/下降各 3512，正确配对 {after['correct_pairs']}/3512，FIFO 输出 {after['FIFO_outputs']}，漏沿、重复、错配、业务错误及 FIFO 错误均为零。

原生产 AD23 同激励对照正确配对 {before['correct_pairs']}/3512；其功能门状态为 `{before['functional_pass']}`，原始结果保留。它是生产版对照，不是时序不通过的原 F 实现。F→I 数值不变来自 RTL 双实例检查；生产版→I 的物理精度变化来自本轮相同激励 SDF，不能混为一个比较。

未连接 MMCM 输出、异步首级采样及启动复位首级告警单独保留分类。最初未分类告警导致的 FAIL 摘要仍在归档；核对实际 RTL、网表和发生时间后仅对明确类别分类。详见 `results/sdf/WARNING_CLASSIFICATION.md`。没有关闭检查来获得 PASS。

## 时序

核心 Setup 最差 +0.099 ns，Hold 最差 +0.054 ns，核心 TNS/THS 为零。全局 WNS/TNS 为 -0.050/-0.166 ns，保留 14 个历史 ILA2 非反馈负端点；详见 `TIMING_BEFORE_AFTER.md`。此前组合版本和物理优化的实际失败证据全部保留。

## 精度对照

{chr(10).join(table)}

共同输入事件数 {comparison['common_event_count']}。完整各测试组见 `results/PRECISION_COMPARISON.csv`。Bias=平均脉宽误差；RMSE=sqrt(mean(error²))；STD 使用 N−1 分母；没有除以 sqrt(2)，没有剔除异常或重新拟合参数。不同脉宽混合汇总只作为误差分布统计，不能当作单一固定脉宽的重复性。

## 交付与限制

已从通过 SDF 的同一最终路由 DCP 生成 `implementation/Corrected.bit` 和匹配 `Corrected.ltx`。两份旧 BIT 保留原位并重新校验 SHA256，未覆盖。正式工程只采用上述三处经过验收的 RTL 修改。没有烧录 FPGA/Flash，没有新版本真实上板采集；本结果不代表已排除真实输入毛刺或所有模拟采样问题。下一步按 `HARDWARE_AB_TEST.md` 做相同输入条件的 A/B。

归档分支 `codex/2026-11-07-03-aux-match-timing-fix`，提交消息 `2026-11-07-03-辅助跨帧匹配时序优化`；推送结果和实际 Commit SHA 在执行结束时单独报告。不得从本文件推断推送已经成功。
'''
(TASK/'RESULTS.md').write_text(results,encoding='utf-8')
(TASK/'README.md').write_text('''# 2026-11-07-03 辅助跨帧匹配时序优化

最终数字验收和核心时序通过，采用一拍专用确认流水及粗计数采样对齐。Corrected BIT/LTX 位于 `implementation/`，**本任务没有烧录板卡**。完整结论见 [RESULTS.md](RESULTS.md)，机器可读验收见 [VALIDATION.json](VALIDATION.json)。

- [时序对照](TIMING_BEFORE_AFTER.md)：核心 Setup/Hold +0.099/+0.054 ns；14 条历史 ILA2 负端点保留。
- [功能等价与延迟说明](DESIGN_EQUIVALENCE.md)：F 功能规则不变，输出整组增加 1 拍，Locate 保持五级。
- [复现步骤](REPRODUCE.md)、[上板 A/B 方法](HARDWARE_AB_TEST.md)。
- `production_original/rtl/`：完整原生产 RTL；`reference_F/rtl/`：完整 F；`variants/I_confirmation_pipe/`：完整最终 RTL。
- `RTL.diff`、`PRODUCTION_RTL.diff`：分别相对 F 和原生产版。
- `inputs/`：真实 ILA CSV、冻结参数、XCI、XDC、原始 3512 脉冲与真实时间参考。
- `results/I_confirmation_pipe/`：组合检查、真实重放、三组 RTL 与错误/回卷检查；`results/sdf/`：两版原始逐事件 CSV、完整压缩日志和注释证据。
- `results/PRECISION_COMPARISON.csv`：各组及共同事件精度；`results/timing/`：成功和失败的原始报告。
- `implementation/`：最终路由/综合 DCP、MAX SDF、网表、BIT/LTX 及有效约束；大文件使用 Git LFS。
- `SHA256SUMS.txt` 和 `FILE_LIST.csv`：校验与文件清单，均不包含自身以避免循环。

未重复上传中间失败 DCP、原生产 BIT、旧 Debug BIT、原生产 DCP、Vivado 缓存及重复输出。历史输入仍在原任务；本地中间实现路径、大小、SHA256 见 `results/LOCAL_INTERMEDIATE_FILES.json`。必要最终实现和所有本轮原始 CSV/失败日志均归档。完整 SDF 日志无损压缩，原日志位置和校验值见各 `RUN_MANIFEST.json`。没有因文件过大遗漏验收证据。

`inputs/SOURCE.json` 是开始状态冻结，不代表最终状态；最终新增流水延迟和正式修改以 `VALIDATION.json` 为准。本地另有同编号 ATC 任务目录，原样保留；本任务按用户明确给定名称创建，未覆盖它。GitHub 只归档本任务及追加索引，不合并 main，不强推。
''',encoding='utf-8')
(TASK/'.gitattributes').write_text('* -text\n*.dcp filter=lfs diff=lfs merge=lfs -text\n*.bit filter=lfs diff=lfs merge=lfs -text\n*.sdf filter=lfs diff=lfs merge=lfs -text\nimplementation/post_route_timing.v filter=lfs diff=lfs merge=lfs -text\n',encoding='ascii')
print('DELIVERY_FINALIZED_THREE_RTL_ADOPTED_NO_HARDWARE_PROGRAMMING',flush=True)
