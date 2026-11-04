"""只复制既有证据、生成索引与压缩包；不调用实验脚本。"""
from pathlib import Path
import csv
import gzip
import hashlib
import json
import re
import shutil
import zipfile

TASK = Path(__file__).resolve().parent
SRC = TASK.parent / '2026-11-04-02-四相TDC固定延迟补偿验证'
OUT = TASK / 'review_package'
# Windows 长路径前缀只用于隔离仓库的文件复制，不改变归档相对路径。
REPO = Path('\\\\?\\' + str(TASK / 'github'))
REMOTE_TASK = REPO / 'codex_generate' / TASK.name

def sha(path):
    with path.open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()

def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding='utf-8', newline='\n')

def table(path, rows, fields):
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

def target(rel):
    p = Path(rel)
    if rel.startswith('baseline/'):
        return '01_RTL/before/' + rel.removeprefix('baseline/')
    if rel.startswith('rtl/'):
        return '01_RTL/after/' + rel.removeprefix('rtl/')
    if p.suffix == '.patch' or rel == 'build/tdc_time_locate_original.v':
        return '01_RTL/' + rel
    if rel.startswith('inputs/stimulus_v1/') or rel.startswith('sim/'):
        return '04_Testbench/' + rel
    if rel.startswith('inputs/') or rel.startswith('scripts/'):
        return '02_Project/' + rel
    if p.suffix in {'.bit', '.dcp'}:
        if rel == 'results/baseline/tdc_baseline.bit':
            return '07_Bitstream/Baseline.bit'
        if rel == 'results/compensated/tdc_compensated.bit':
            return '07_Bitstream/Compensated.bit'
        return '07_Bitstream/' + rel
    if p.suffix in {'.sdf', '.rpt', '.v'} or p.name in {'sdf_audit.json', 'build_metadata.txt', 'version_manifest.json'}:
        return '06_Timing/' + rel
    if rel.startswith('build/') and p.suffix in {'.xpr', '.xci', '.xdc', '.tcl', '.bat', '.sh', '.ini', '.prj', '.mem'}:
        return '02_Project/' + rel
    if p.suffix in {'.log', '.jou', '.vds'}:
        return '05_Results/' + rel
    if rel.startswith('results/'):
        if p.name.startswith('calibration') or p.name == 'tdc_skew_calibration.csv':
            return '03_Calibration/' + rel
        if p.name == 'input_tb.sv':
            return '04_Testbench/' + rel
        return '05_Results/' + rel
    return '08_Reports/original/' + rel

def selected(p):
    r = p.relative_to(SRC).as_posix()
    if '__pycache__' in p.parts or p.suffix == '.pyc':
        return False
    if not r.startswith('build/'):
        return True
    if 'xsim.dir' in p.parts and p.suffix == '.mem':
        return False
    if p.suffix in {'.csv', '.log', '.jou', '.vds', '.rpt', '.xdc', '.xci', '.xpr', '.sdf', '.mem'}:
        return True
    if p.suffix in {'.tcl', '.bat', '.sh', '.prj', '.ini'}:
        return '.runs/' in r or '/impl/timing/xsim/' in r
    if p.suffix == '.dcp':
        return '.gen/' in r or '/synth_1/' in r or p.name.endswith('_routed.dcp')
    return r == 'build/tdc_time_locate_original.v' or (p.suffix == '.v' and '/impl/timing/xsim/' in r)

def main():
    assert not OUT.exists(), '交付目录已存在，禁止覆盖'
    assert not REMOTE_TASK.exists(), '远程任务目录已存在，禁止覆盖'
    OUT.mkdir()
    for name in ['01_RTL','02_Project','03_Calibration','04_Testbench','05_Results','06_Timing','07_Bitstream','08_Reports']:
        (OUT/name).mkdir()
    sources = sorted(p for p in SRC.rglob('*') if p.is_file())
    candidates = [p for p in sources if selected(p)]
    # 优先保留正式结果路径，再用内容哈希合并完全相同的副本。
    candidates.sort(key=lambda p: (p.relative_to(SRC).parts[0] in {'build','logs'}, p.as_posix()))
    records, seen = [], {}
    for p in candidates:
        rel = p.relative_to(SRC).as_posix()
        h = sha(p)
        dest = target(rel)
        keep_rtl = rel.startswith(('baseline/', 'rtl/'))
        if h in seen and not keep_rtl:
            dest = seen[h]
            mode = 'exact_duplicate_reference'
        else:
            d = OUT/dest
            d.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(p, d)
            seen.setdefault(h, dest)
            mode = 'byte_identical_copy'
        records.append(dict(source=rel, packaged=dest, bytes=p.stat().st_size, sha256=h, storage=mode))
    table(OUT/'FILE_INDEX.csv', records, ['source','packaged','bytes','sha256','storage'])
    write(OUT/'FILE_INDEX.json', json.dumps(records, ensure_ascii=False, indent=2)+'\n')
    excluded = [dict(source=p.relative_to(SRC).as_posix(),bytes=p.stat().st_size,reason='构建缓存、可再生中间文件或工具二进制；原始文件未删除') for p in sources if not selected(p)]
    table(OUT/'EXCLUDED_CACHE_FILES.csv', excluded, ['source','bytes','reason'])
    docs(OUT)
    shutil.copyfile(Path(__file__), OUT/'08_Reports/package_review.py')
    # 每个原始 CSV 和日志路径都必须能解析到未改变的字节。
    indexed = {r['source']:r for r in records}
    required = [p for p in sources if p.suffix.lower() in {'.csv','.log','.jou','.vds'}]
    assert all(p.relative_to(SRC).as_posix() in indexed for p in required)
    for r in records:
        assert sha(SRC/r['source']) == r['sha256'], r['source']
        assert sha(OUT/r['packaged']) == r['sha256'], r['packaged']
    for kind, folder in [('before', 'baseline/rtl'), ('after', 'rtl')]:
        actual = [r for r in records if r['source'].startswith(folder+'/')]
        assert len(actual) == 5
        assert all((OUT/r['packaged']).is_file() for r in actual)
    acceptance = json.loads((SRC/'results/acceptance.json').read_text(encoding='utf-8'))
    assert acceptance['status'] == 'FAIL'
    check = dict(archive_integrity='PASS', experiment_acceptance='FAIL', source_files_indexed=len(records),
                 original_csv_paths=sum(p.suffix.lower()=='.csv' for p in required),
                 original_log_paths=sum(p.suffix.lower()=='.log' for p in required),
                 all_original_csv_and_logs_preserved=True, both_rtl_sets_complete=True,
                 originals_rehashed_unchanged=True, excluded_cache_files=len(excluded))
    write(OUT/'ARCHIVE_VERIFICATION.json', json.dumps(check, ensure_ascii=False, indent=2)+'\n')
    manifest(OUT)
    # 两个 ZIP 可以解压到同一目录；全部报告和索引均随两包附带。
    ziprows = []
    for kind in ['Source_Results','Implementation']:
        zpath = TASK/f'TDC_Review_{kind}.zip'
        assert not zpath.exists()
        members=[]
        with zipfile.ZipFile(zpath,'w',zipfile.ZIP_DEFLATED,compresslevel=6,allowZip64=True) as z:
            for p in sorted(OUT.rglob('*')):
                if not p.is_file(): continue
                rel=p.relative_to(OUT).as_posix()
                common = '/' not in rel or rel.startswith('08_Reports/')
                impl = rel.startswith(('06_Timing/','07_Bitstream/'))
                # 源码包也包含所有时序文本报告，二进制实现证据只进入实现包。
                report = rel.startswith('06_Timing/') and p.suffix in {'.rpt','.json','.txt'}
                impl_log = p.suffix.lower() in {'.log','.jou','.vds'}
                if common or (kind=='Implementation' and (impl or impl_log)) or (kind=='Source_Results' and (not impl or report)):
                    z.write(p,'review_package/'+rel)
                    members.append((p,'review_package/'+rel))
        with zipfile.ZipFile(zpath) as z:
            for p,name in members:
                with z.open(name) as f:
                    assert hashlib.file_digest(f,'sha256').hexdigest()==sha(p), name
        ziprows.append(dict(file=zpath.name,bytes=zpath.stat().st_size,sha256=sha(zpath),members=len(members),roundtrip='PASS'))
    write(TASK/'ZIP_MANIFEST.json',json.dumps(ziprows,ensure_ascii=False,indent=2)+'\n')
    publish(records)
    print(json.dumps(dict(verification=check,zips=ziprows,git_task=str(REMOTE_TASK)),ensure_ascii=False,indent=2),flush=True)

def manifest(root):
    rows=[]
    for p in sorted(root.rglob('*')):
        if p.is_file() and p.name not in {'SHA256SUMS.txt','FILE_LIST.md'}:
            rows.append((p.relative_to(root).as_posix(),p.stat().st_size,sha(p)))
    write(root/'SHA256SUMS.txt',''.join(f'{h}  {r}\n' for r,n,h in rows))
    write(root/'FILE_LIST.md','# 文件清单\n\n| 文件 | 字节数 |\n|---|---:|\n'+''.join(f'| [{r}]({r}) | {n} |\n' for r,n,h in rows))

def publish(records):
    REMOTE_TASK.mkdir(parents=True, exist_ok=True)
    mapping=[]
    for p in sorted(OUT.rglob('*')):
        if not p.is_file(): continue
        rel=p.relative_to(OUT).as_posix()
        # Git 版本仅改变大日志的容器形式，解压字节必须与本地原始副本相等。
        compress=p.suffix.lower() in {'.log','.jou','.vds'} and p.stat().st_size>5_000_000
        d=REMOTE_TASK/'review_package'/(rel+'.gz' if compress else rel)
        d.parent.mkdir(parents=True,exist_ok=True)
        if compress:
            with p.open('rb') as f,d.open('wb') as raw:
                with gzip.GzipFile(filename='',fileobj=raw,mode='wb',compresslevel=6,mtime=0) as g:
                    shutil.copyfileobj(f,g)
            with gzip.open(d,'rb') as f:
                assert hashlib.file_digest(f,'sha256').hexdigest()==sha(p)
        else:
            shutil.copyfile(p,d)
        mapping.append(dict(local='review_package/'+rel,published=d.relative_to(REMOTE_TASK).as_posix(),
                            original_bytes=p.stat().st_size,original_sha256=sha(p),published_bytes=d.stat().st_size,
                            published_sha256=sha(d),encoding='gzip' if compress else 'identity'))
    table(REMOTE_TASK/'PUBLICATION_INDEX.csv',mapping,list(mapping[0]))
    shutil.copyfile(TASK/'ZIP_MANIFEST.json',REMOTE_TASK/'ZIP_MANIFEST.json')
    write(REMOTE_TASK/'README.md',PUBLIC_README)
    # 防止 Git 自动换行改变证据，并用 LFS 管理实现文件与大型压缩日志。
    write(REMOTE_TASK/'.gitattributes','* -text\n*.bit filter=lfs diff=lfs merge=lfs -text\n*.dcp filter=lfs diff=lfs merge=lfs -text\n*.sdf filter=lfs diff=lfs merge=lfs -text\n*design.v filter=lfs diff=lfs merge=lfs -text\n*tb_tdc_time_impl.v filter=lfs diff=lfs merge=lfs -text\n*.gz filter=lfs diff=lfs merge=lfs -text\n')
    manifest(REMOTE_TASK)
    idx=REPO/'codex_generate/README.md'
    if not idx.exists():
        write(idx,'# Codex 任务产物索引\n\n| 日期编号 | 任务 |\n|---|---|\n| 2026-11-04-02 | [四相TDC固定延迟补偿](2026-11-04-02-四相TDC固定延迟补偿/README.md) |\n\n本次从空远程仓库建立独立归档分支。原工作目录内的 `2026-11-04-01-产物目录规范` 与完整实验原目录保留原样。\n')

def docs(root):
    write(root/'README_FOR_REVIEW.md',REVIEW_README)
    write(root/'08_Reports/最终验收报告.md', '# 最终验收报告\n\n实验验收：**FAIL**。本次仅归档，没有重新综合、仿真、计算参数或改写数据。\n\n25.3 ns、20 MHz/50%及10 MHz完整暂定帧的既有RMSE改善不能抵消20 MHz完整帧漏沿/错配和500 MHz setup失败。原始验收见 `../05_Results/results/acceptance.json`；全量原始日志、CSV与失败记录均有FILE_INDEX映射。\n\n归档完整性通过仅表示副本与源文件SHA256一致，不代表硬件或实验验收通过。\n')
    write(root/'08_Reports/已知问题及限制.md', '# 已知问题及限制\n\n- 两版静态setup不收敛：WNS -0.163/-0.173 ns，TNS -0.589/-1.083 ns；没有通过归档修改为PASS。\n- 两版20 MHz暂定完整帧1051/1056正确配对；丢3个R、2个F，2次错配。详见原ANOMALIES.md与逐事件CSV。\n- 每版主验证动态告警1,159,787条，全部原文保留。MMCM未用CLKOUT5/6零周期告警原因未确认。\n- TDL异步采样模型存在setup/hold告警，数值输出不能代替硅片亚稳态验证。\n- ATC帧头、bank顺序及SPWM为暂定协议假设；真实芯片协议、上板、温压与其他SDF角未执行。\n- 两版本236条同名前端网路由不同；数字反事实统计不是第三套实现或硅片测试。\n- 原始XPR/Tcl保留历史T:/本地绝对路径；复制没有修改这些文件。复现必须在新副本映射路径，并使用Vivado 2022.2及对应器件库。厂商工具/模型未随包分发。\n- 原报告保持原字节，内部旧相对链接可通过FILE_INDEX.csv定位归档文件。大日志在Git版采用gzip，可逐字节还原。\n')
    write(root/'07_Bitstream/VERSION_MAP.md', '# 位流版本对应\n\n| 版本 | 位流 | DCP | RTL | 参数 |\n|---|---|---|---|---|\n| Baseline | Baseline.bit | results/baseline/design.dcp | ../01_RTL/before/rtl/ 五文件 | 原始无补偿 |\n| Compensated | Compensated.bit | results/compensated/design.dcp | ../01_RTL/after/ 五文件 | ../03_Calibration/results/calibration_params.tcl，ENABLE_SKEW_COMP=1 |\n\n精确哈希、器件、工具与激励版本见 ../06_Timing/results/{baseline,compensated}/version_manifest.json 以及FILE_INDEX。生成日志均映射到05_Results；没有上板烧写。\n')
    write(root/'06_Timing/LOG_LOCATIONS.md', '# 日志位置\n\nSDF注释与警告原文、综合实现和失败尝试日志统一存放05_Results，逐路径定位见根目录FILE_INDEX.csv。关键路径包括 `results/<版本>/gate_validation/{elaboration,simulation}.log`，`logs/` 下控制台日志，以及 `build/` 下runme.log、Vivado日志和journal。\n\n本目录保存路由后报告、注释实际网表/SDF和sdf_audit.json。64个CARRY4、256个采样FF及7个LUT1关键清单齐全；没有工具提供的全局逐路径注释百分比，不虚构该成功率。\n')

REVIEW_README = '''# XC7K325T 四相TDC外部技术审查说明

**实验整体验收：FAIL。** 归档副本的完整性检查与实验是否通过是两个独立结论。本次只复制既有证据和编写说明，不修改RTL、参数、CSV、报告或日志，不重新运行综合、实现、仿真和统计。

原工作目录：`D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/codex_generate/2026-11-04-02-四相TDC固定延迟补偿验证/`。新归档任务：`2026-11-04-02-四相TDC固定延迟补偿`。FILE_INDEX.csv/JSON逐项记录源相对路径、实际归档路径、字节数、SHA256。完全相同的重复内容只保存一份，由索引映射；补偿前后各五份完整RTL单独保留。

## 1. 实际RTL修改与流水线

原实验仅修改 `tdc_meas_top.v`、`tdc_time_locate.v`。归档前版本在01_RTL/before/rtl，后版本在01_RTL/after。三份未修改RTL为tdc_fine_layer.v、tdc_time_candicate.v、tdc_time_merge.v，均包含在两套完整快照中。差异见01_RTL/补偿RTL变更.patch。此次归档没有任何新的RTL修改。

顶层传递ENABLE_SKEW_COMP和8个18位signed参数；locate第2级按候选index/type选择、寄存对应偏移，与coarse/fine对齐；第3级计算mid−fine−offset，第4级合成、第5级模回卷，原5级valid/type流水不变。开关0为显式generate旁路；默认0参数是未校准占位，正式补偿实现由calibration_params.tcl装载以下值。

## 2. 八项参数、计算与公共延迟

单位均为ps，按物理相位与独立极性定义：

| 物理相位 | sel_index | Rise偏移 | Fall偏移 | 原始平均偏差 Rise/Fall | 有效数 每极性 |
|---|---:|---:|---:|---:|---:|
| 下一周期0° | 3 | 34698 | 34698 | 34698.25 | 320 |
| 90° | 0 | 34710 | 34710 | 34710.00 | 328 |
| 180° | 1 | 34861 | 34861 | 34861.25 | 320 |
| 270° | 2 | 34796 | 34796 | 34795.50 | 320 |

独立baseline slow/MAX SDF校准800个25.3 ns脉冲，100个编程相位×8；验证集不参与拟合。公共时间参考coarse epoch=675150 ps，模数M=2048000 ps。每个有效通道/极性独立计算 `error=signed_mod(T_measured−((T_input−epoch) mod M))`，取mean，再按既有提取脚本round得到整数offset。原始四路虚拟时间采用 `((C_raw+6) mod 1024)*2000+mid−fine`；候选对应`((C_candidate+1) mod 1024)*2000+mid−fine`。1600个候选的5拍对齐及算术核对均已通过。

这8项是**包含公共流水线整数周期与输入分发延迟的绝对偏移**。不能把约34.7 ns全解释为四通道偏斜。相对0°通道差为0/11.75/163.00/97.25 ps。Rise/Fall独立拟合、独立参数化；本确定性模型两者相等不代表硅片相等。补偿`T_corrected=(T_measured−offset) mod M`。

参数CSV、逐观测、相位覆盖、JSON及Tcl在03_Calibration/results；提取脚本在02_Project/scripts/experiment.py；完整计算过程见08_Reports/original/CALIBRATION_REPORT.md。旧校准调度与stimulus_v1原样保留，未改变已执行输入。

## 3. RMSE公式、样本与异常规则

误差`e_i=measured_width_i−true_width_i`；RMSE=`sqrt(sum(e_i²)/N)`，Bias=`sum(e_i)/N`，STD=`sqrt(sum((e_i−Bias)²)/N)`（总体STD），MaxAbs=`max(abs(e_i))`。成功率为正确配对事件数/预期输入数。只按真实边沿事件ID关联，不按CSV行号强行配对；漏沿、错配、重复和错误原始记录均保留，无阈值裁剪或删除异常。完整性失败时主表指标N/A，成功子集条件统计明确单列，不能冒充全量精度。

| 既有测试 | N 前/后 | Baseline RMSE ps | Compensated RMSE ps |
|---|---:|---:|---:|
| 25.3 ns | 200/200 | 135.602 | 53.147 |
| 20 MHz/50% | 200/200 | 143.269 | 69.735 |
| 10 MHz完整暂定帧 | 1056/1056 | 125.406 | 66.700 |

上述数值由原始comparison_metrics.csv更高精度值按三位小数展示，未重新计算数据。**10 MHz完整暂定帧与10 MHz/50%单项不同**；后者确定性相位抵消为0→0，不能称为硅片0 ps。两版主验证3512输入、3509输出、3507正确配对，有效率99.857631%；各测试Bias/STD/MaxAbs/改善率见原CSV与FINAL_RMS_COMPARISON.md，所有图的CSV源数据均保留。

## 4. 激励一致性与20 MHz异常事件

两版主SDF验证使用字节完全相同的激励，SHA256：`451a2cb59cc0704a9e5ac8454bb983237543705f2c4782789b3067be4d9fa76f`。实际input_tb.sv、输入stimulus、truth、input_sha256及运行快照均保留；早期RTL与旧stimulus_v1另存，不与主SDF验证混用。

两版缺失R事件2918、2984、3050；缺失F事件2917、2983，重复ID为0。baseline错配为F2918配R2917输出50900 ps、F2984配R2983输出50940 ps（对应帧头预期2500 ps）。关联ID而不是成功子集精度是判断错误的依据。

| 事件ID | 暂定位置 | high ps | 前一low ps |
|---|---|---:|---:|
| 2917 | bank6/ch63 | 47335 | 2669 |
| 2918 | bank7/header0 | 2500 | 1330 |
| 2983 | bank7/ch63 | 47416 | 2581 |
| 2984 | bank8/header0 | 2500 | 1293 |
| 3050 | bank9/header0 | 2500 | 1736 |

冲突238744150/242044150/245344150 ps，repeat245346150 ps，merge孤立下降沿错误2在245358150 ps。候选原始帧有混合极性，被既有门控丢弃。完整证据见ANOMALIES.md与raw/candidate/timestamps/widths/errors/summary CSV及JSON。暂定边沿对齐帧头加中心对齐SPWM带来短低电平，不等价于真实ATC芯片协议已失败。

## 5. 两版本静态时序

单位ns，未经归档重写：

| 版本 | WNS | TNS | WHS | THS | Setup失败端点 | Hold失败端点 |
|---|---:|---:|---:|---:|---:|---:|
| Baseline | -0.163 | -0.589 | +0.058 | 0 | 12 | 0 |
| Compensated | -0.173 | -1.083 | +0.058 | 0 | 19 | 0 |

两个版本500 MHz setup均FAIL。最差路径90°编码树到0°pack90_d1，另有ILA路径。06_Timing包含原timing_summary、setup_paths、hold_paths、post-route报告；07_Bitstream保存版本明确的BIT/DCP，生成日志在05_Results。XDC未设板级PWM/reset输入延迟、dbg_hub频率元数据问题与基线约束使用阶段差异仍保留。两版前端236条同名网路由不同，不能声称完全同布局。

## 6. SDF、器件模型与告警

器件xc7k325tffg900-2，Vivado2022.2，simprims_ver及7-series器件模型，slow/MAX路由后SDF，1 ps分辨率。elaboration日志表明注释成功，实际注释SDF/网表及输入SHA均保留。64个TDL CARRY4、256个采样FF、7个LUT1关键清单齐全；这是关键清单覆盖，不是工具全局逐路径注释百分比，未生成虚假的注释率。

每版主验证1,159,787条动态告警：MMCM未用CLKOUT5/6 period 1,073,744；PWM同步setuphold383；TDL异步采样setuphold85,549；其他recrem2、setuphold109。所有原日志保留，未禁用timing checks/notifier。MMCM零周期检查原因未确认，不能当作已解释的误报。

## 7. PASS、FAIL及未执行

| 状态 | 项目与边界 |
|---|---|
| PASS | 原RTL/显式旁路/零参数及signed/wrap单元检查，COARSE_W=2和10各5044有效检查 |
| PASS | 理想原语RTL完整3512脉冲/7024时间戳功能回归；不代表物理精度 |
| PASS | 25.3 ns、各独立10/20 MHz固定占空比、95%帧头、10 MHz完整暂定帧的事件完整性与既有指标 |
| PASS（限范围） | SDF注释关键清单；结果FIFO序列核对；独立fifo_probe错误码2在500/100 MHz序列一致，非主验证全量错误FIFO审计 |
| FAIL | 两版500 MHz setup；20 MHz完整暂定帧；5%帧头全量；SPWM全量；全部输入全量事件关联；动态时序尚不能签核；整体验收 |
| 未执行 | 上板硅片、PVT/其他动态SDF角、真实ATC协议、板级完整IO时序签核；归档阶段没有重跑任何实验 |

## 8. 目录、压缩包、完整性与复现

01_RTL：完整前后版本与diff；02_Project：原/实际XPR、XDC、四种IP XCI、所有实验脚本及实际运行命令；03_Calibration：原参数与计算证据；04_Testbench：固定/PWM/帧头/SPWM、真实边沿、实际TB快照；05_Results：全部原CSV、图与数据、原始/失败日志；06_Timing：SDF/网表/原时序报告；07_Bitstream：两版BIT/DCP；08_Reports：原报告与新增审查说明。

`TDC_Review_Source_Results.zip`和`TDC_Review_Implementation.zip`位于本review_package的父目录。解压到同一目录可组合全部证据；两个包均附索引/报告，源码结果包也包含时序文本报告，实现包包含BIT/DCP/SDF/网表。没有因大小省略关键证据。

SHA256SUMS覆盖重要文件；FILE_INDEX涵盖全部原始CSV与.log/.jou/.vds路径，完全相同副本按哈希映射。EXCLUDED_CACHE_FILES只列不打包的构建缓存、可再生中间文件/工具二进制，原文件未删除。ARCHIVE_VERIFICATION记录字节一致性。原报告与工程配置中的历史路径保持原样，可由索引查找；原REPRODUCE及脚本也保留，复现须在新工作副本进行，不能在冻结证据上运行会重写输出的脚本。

Git归档版仅把>5 MB日志无损gzip压缩，PUBLICATION_INDEX逐项记录压缩前后路径/大小/SHA。解压所得字节必须与FILE_INDEX的原SHA一致。Git LFS用于BIT/DCP/SDF/大型网表和.gz日志，克隆后需`git lfs pull`获取真实内容。两个ZIP留作本地交付，Git不重复提交ZIP；所有关键证据已逐文件上传，不以外部本地路径代替上传。
'''

PUBLIC_README = '''# 四相TDC固定延迟补偿实验归档

**实验验收：FAIL。** 本分支只归档既有实验，不重新修改RTL或计算数据。20 MHz完整暂定帧漏沿/错配和500 MHz setup失败证据完整保留。

- [外部技术审查说明](review_package/README_FOR_REVIEW.md)
- [全部文件清单](FILE_LIST.md)
- [原始来源→审查包映射](review_package/FILE_INDEX.csv)
- [本地审查包→Git文件映射](PUBLICATION_INDEX.csv)
- [原始最终RMSE报告](review_package/08_Reports/original/FINAL_RMS_COMPARISON.md)
- [归档完整性验证](review_package/ARCHIVE_VERIFICATION.json)

补偿前后各五份完整RTL、全部原CSV与失败日志、两套BIT/DCP/SDF/实现后网表和时序报告均在review_package。>5 MB原日志在Git使用无损gzip；解压SHA必须与PUBLICATION_INDEX的original_sha256相同，未裁剪告警。实现文件与.gz由Git LFS保存，克隆后执行`git lfs pull`。SHA256SUMS校验Git实际文件；review_package内的原SHA清单针对解压后的本地审查包。

既有RMSE（ps）：25.3 ns 135.602→53.147；20 MHz/50% 143.269→69.735；10 MHz**完整暂定帧**125.406→66.700。10 MHz/50%是独立项目，不能混同。

两个本地ZIP位于原工作空间任务目录：`D:/00-code/FPGA_Prj/fpga_tdc_v3_cal/codex_generate/2026-11-04-02-四相TDC固定延迟补偿/`，名称为TDC_Review_Source_Results.zip和TDC_Review_Implementation.zip；ZIP_MANIFEST.json记录大小与SHA。ZIP没有重复提交到Git；其全部关键内容以本目录逐文件形式上传。工具缓存不归档，清单见review_package/EXCLUDED_CACHE_FILES.csv；原工程和历史任务未覆盖。
'''

if __name__ == '__main__':
    main()
