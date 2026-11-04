"""从冻结实现和完整仿真结果生成报告、追溯清单及终端汇总。"""
import csv
import difflib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from experiment import ROOT, read_csv, sha


def timing(variant):
    path=ROOT/"results"/variant/"timing_summary.rpt"
    text=path.read_text(encoding="utf-8",errors="replace")
    section=text.split("Design Timing Summary",1)[1]
    for line in section.splitlines():
        parts=line.split()
        if len(parts)==12:
            try: values=list(map(float,parts))
            except ValueError: continue
            return dict(wns_ns=values[0],tns_ns=values[1],setup_failing=int(values[2]),
                whs_ns=values[4],ths_ns=values[5],hold_failing=int(values[6]),wpws_ns=values[8])
    raise ValueError(f"无法解析时序报告：{path}")


def dynamic_timing(folder):
    counts=Counter(); scopes=Counter()
    pattern=re.compile(r'Timing violation in scope (\S+) at time (\d+) ps (\$\w+)')
    with (folder/"simulation.log").open(encoding="utf-8",errors="replace") as stream:
        for line in stream:
            match=pattern.search(line)
            if not match: continue
            scope,when,check=match.groups()
            if "mmcm_adv_inst" in scope and ("CLKOUT5" in line or "CLKOUT6" in line): category="MMCM_unused_CLKOUT5_6"
            elif "/thermo_q_reg" in scope: category="TDL_async_sampling"
            elif "/pwm_meta_reg" in scope: category="PWM_async_synchronizer"
            else: category="other_logic_or_IP"
            counts[category,check]+=1
            scopes[scope.split("/TChk")[0],check]+=1
    rows=[dict(category=c,check=k,count=n) for (c,k),n in sorted(counts.items())]
    with (folder/"timing_violation_counts.csv").open("w",newline="",encoding="utf-8") as stream:
        writer=csv.DictWriter(stream,fieldnames=["category","check","count"])
        writer.writeheader(); writer.writerows(rows)
    return dict(total=sum(counts.values()),categories=rows,unique_scope_checks=len(scopes))


def frontend_comparison():
    routes={}
    for variant in ("baseline","compensated"):
        with (ROOT/"results"/variant/"frontend_route.tsv").open(encoding="utf-8",newline="") as stream:
            routes[variant]={r["name"]:r["route"] for r in csv.DictReader(stream,delimiter="\t")}
    a,b=routes["baseline"],routes["compensated"]
    common=a.keys() & b.keys()
    changed=[name for name in sorted(common) if a[name]!=b[name]]
    return dict(common_nets=len(common),identical_routes=len(common)-len(changed),changed_routes=len(changed),
        baseline_only=sorted(a.keys()-b.keys()),compensated_only=sorted(b.keys()-a.keys()),changed_names=changed)


def fmt(value):
    return "N/A" if value is None else f"{float(value):.4f}"


def write_reports(summaries,static,dynamic,comparison,frontend,status,business_ok):
    labels={"fixed_25300":"固定25.3 ns","10MHz_50":"10 MHz / 50%","20MHz_50":"20 MHz / 50%",
        "header_5":"5%暂定帧头","header_95":"95%暂定帧头","spwm_data":"SPWM数据",
        "complete_frame":"两频率完整暂定帧合计","ATC_10MHz":"10 MHz完整暂定帧","ATC_20MHz":"20 MHz完整暂定帧","10MHz_5":"10 MHz / 5%","10MHz_95":"10 MHz / 95%",
        "20MHz_5":"20 MHz / 5%","20MHz_95":"20 MHz / 95%","all":"全部验证脉冲"}
    rows={r["test"]:r for r in comparison["independent_implementation_results"]}
    lines=["# 最终脉宽RMSE对比", "",f"整体验收：**{status}**。业务与事件关联检查：{'PASS' if business_ok else 'FAIL'}。",
        "静态时序与动态timing warnings单独保留，业务输出正常不能替代时序签核。所有主表值来自两套真实实现后SDF验证，不是理想RTL数据或训练集统计。", "",
        "| 测试 | Baseline RMSE ps | 补偿 RMSE ps | 改善比例 | Baseline Bias ps | 补偿 Bias ps | Baseline STD ps | 补偿 STD ps | 样本数 前/后 |",
        "|---|---:|---:|---:|---:|---:|---:|---:|---:|"]
    for group,label in labels.items():
        r=rows.get(group)
        if not r: lines.append(f"| {label} | N/A | N/A | N/A | N/A | N/A | N/A | N/A | 0/0 |"); continue
        if not (r["baseline_complete"] and r["compensated_complete"]):
            lines.append(f"| {label} | N/A | N/A | N/A | N/A | N/A | N/A | N/A | {r['baseline_n']}/{r['baseline_expected_n']}；{r['compensated_n']}/{r['compensated_expected_n']} |"); continue
        improvement="N/A" if r["improvement"] is None else f"{100*r['improvement']:.2f}%"
        lines.append(f"| {label} | {fmt(r['baseline_rmse_ps'])} | {fmt(r['compensated_rmse_ps'])} | {improvement} | {fmt(r['baseline_bias_ps'])} | {fmt(r['compensated_bias_ps'])} | {fmt(r['baseline_std_ps'])} | {fmt(r['compensated_std_ps'])} | {r['baseline_n']}/{r['compensated_n']} |")
    lines += ["", "RMSE直接以真实脉宽为参考；STD为去均值后的辅助指标。改善比例为1−补偿RMSE/Baseline RMSE，负值如实表示变差。", "",
        "误差指标N/A表示存在漏测/错配，完整测试失败；改善比例N/A也可能因Baseline RMSE为0而无定义。10MHz/50%的0值是本确定性模型下同相位周期抵消的结果，不代表硅片0ps分辨率。不能用成功子集冒充全体精度。以下保留不完整测试的成功配对样本条件统计，所有异常原始输出仍在CSV及ANOMALIES.md中。", "",
        "| 不完整测试的成功子集 | Baseline RMSE/Bias/STD ps | 补偿 RMSE/Bias/STD ps |", "|---|---|---|"]
    for group,label in labels.items():
        r=rows.get(group)
        if r and not (r["baseline_complete"] and r["compensated_complete"]):
            lines.append(f"| {label} | {fmt(r['baseline_rmse_ps'])}/{fmt(r['baseline_bias_ps'])}/{fmt(r['baseline_std_ps'])} | {fmt(r['compensated_rmse_ps'])}/{fmt(r['compensated_bias_ps'])}/{fmt(r['compensated_std_ps'])} |")
    lines += ["",
        "## 连续测量与时间戳", "", "| 版本 | 输入 | 脉宽输出 | 有效配对率 | 缺失 | 重复ID | 关联/算术故障 | 业务错误行 | FIFO序列相等 |", "|---|---:|---:|---:|---:|---:|---:|---:|---|"]
    for v,s in summaries.items():
        lines.append(f"| {v} | {s['expected_pulses']} | {s['output_widths']} | {s['valid_rate']:.6%} | {len(s['missing'])} | {len(s['duplicate'])} | {len(s['faults'])} | {len(s['business_errors'])} | {s['fifo_sequence_equal']} |")
    for v,s in summaries.items():
        lines.append(f"\n{v}：缺失上升沿{len(s['missing_rise_ids'])}个、下降沿{len(s['missing_fall_ids'])}个；重复上升/下降沿分别{len(s['duplicate_rise_ids'])}/{len(s['duplicate_fall_ids'])}。逐通道有效数、选择比例、偏差和完整相位点清单位于该批次channel_statistics.csv。")
    lines += ["", "| 测试 | Baseline MaxAbs ps | 补偿 MaxAbs ps |", "|---|---:|---:|"]
    for group,label in labels.items():
        r=rows.get(group)
        if r: lines.append(f"| {label} | {fmt(r['baseline_max_abs_ps']) if r['baseline_complete'] else 'N/A'} | {fmt(r['compensated_max_abs_ps']) if r['compensated_complete'] else 'N/A'} |")
    lines += ["", "以下时间戳指标仅统计实际输出的有效边沿，缺失边沿另计，不代表全量边沿通过。", "", "| 版本 | 上升沿时间戳RMSE ps | 上升沿Bias ps | 下降沿时间戳RMSE ps | 下降沿Bias ps |", "|---|---:|---:|---:|---:|"]
    for v,s in summaries.items():
        lines.append(f"| {v} | {fmt(s['rise']['rmse_ps'])} | {fmt(s['rise']['bias_ps'])} | {fmt(s['fall']['rmse_ps'])} | {fmt(s['fall']['bias_ps'])} |")
    for v,s in summaries.items():
        lines.append(f"\n{v}选择次数（sel_index=0/1/2/3，对应90/180/270/下一周期0°）：`{s['selection_counts']}`。")
    lines += ["", "每个成功配对脉宽按事件ID一一对应，缺失或额外输出不参与强制行对齐；完整异常列表在各批次summary.json，逐事件对照在results/paired_comparison.csv。", "",
        "## 8个实际补偿参数", "", "| 通道 | 上升沿 ps | 下降沿 ps |", "|---|---:|---:|"]
    parameters=read_csv(ROOT/"results/tdc_skew_calibration.csv")
    for phase in ("0","90","180","270"):
        values={r["polarity"]:r["offset_ps"] for r in parameters if r["tdl_phase"]==phase}
        lines.append(f"| {phase}° | {values['rise']} | {values['fall']} |")
    replay=comparison["same_layout_digital_replay"]
    delta=comparison["actual_implementation_minus_same_layout_replay"]
    lines += ["", "## 布局与算法归因", "",
        f"前端指纹共有{frontend['common_nets']}条同名网，其中路由相同{frontend['identical_routes']}条、不同{frontend['changed_routes']}条。即使启用增量实现，也不能声称两套bitstream严格共享全部物理条件。",
        f"另存同一Baseline SDF样本的数字反事实重算：RMSE={fmt(replay['rmse_ps'])} ps、Bias={fmt(replay['bias_ps'])} ps、STD={fmt(replay['std_ps'])} ps。它用于分离算法效果，**不是补偿版SDF或独立硬件测量**，不代替主表。", "",
        f"重新实现的真实补偿输出减去同布局数字重算，在{delta['n']}个共同正确配对样本上最大差值为{fmt(delta['max_abs_ps'])} ps；本批实际输出与算法预测逐点一致，但不改变物理路由存在差异的事实。", "",
        "## 位流、复现与限制", "",
        "- [Baseline位流](results/baseline/tdc_baseline.bit)：原始RTL快照，无补偿；新增显式旁路已通过等价回归。",
        "- [Compensated位流](results/compensated/tdc_compensated.bit)：ENABLE_SKEW_COMP=1，8项参数来自独立校准。",
        "- [复现说明](REPRODUCE.md)；从新的任务副本运行scripts/run.ps1 -Stage all。",
        "- [时序报告](TIMING_REPORT.md)、[校准报告](CALIBRATION_REPORT.md)、[RTL审查](RTL_REVIEW.md)。",
        "- ATC bank/帧头/SPWM配置为明确的临时协议假设，不能等同实际芯片协议验收。",
        "- SDF仅代表当前器件模型与slow/MAX角；尚未完成硅片、温压、板级I/O及真实相位抖动验证。",
        "- 先处理500 MHz真实setup违例及MMCM模型告警，再上板重新扫描相位、核验8项参数；固定偏移不能修复tap非线性、TAP_PS估计误差或时序违例。"]
    (ROOT/"FINAL_RMS_COMPARISON.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    timing_lines=["# 静态与动态时序报告", "", "| 版本 | WNS ns | TNS ns | Setup失败端点 | WHS ns | Hold失败端点 | WPWS ns |", "|---|---:|---:|---:|---:|---:|---:|"]
    for v,t in static.items(): timing_lines.append(f"| {v} | {t['wns_ns']} | {t['tns_ns']} | {t['setup_failing']} | {t['whs_ns']} | {t['hold_failing']} | {t['wpws_ns']} |")
    timing_lines += ["", "两个版本都没有降低500 MHz或放宽时序例外。Baseline最差路径为90°计1编码到0°pack90_d1极性位，另有500 MHz ILA路径；不能靠数字偏移解决。原PWM和复位没有板级input delay，debug hub频率参数与实际100 MHz不符，详见RTL_REVIEW。", "",
        "## SDF与动态告警", "", "SDF采用实际路由后网表、slow/MAX、1ps时间分辨率。每批保留elaboration.log、实际注释输入哈希、simulation.log和原始CSV。64个TDL CARRY4、256个采样FF、7个LUT1均在SDF关键清单中；未把清单覆盖冒充工具逐路径百分比。", "", "| 版本 | 分类 | 检查 | 告警次数 |", "|---|---|---|---:|"]
    for v,d in dynamic.items():
        for r in d["categories"]: timing_lines.append(f"| {v} | {r['category']} | {r['check']} | {r['count']} |")
    timing_lines += ["", "全部告警原文保留，没有notimingchecks/no_notifier/suppress、没有编辑厂商模型。MMCM未使用CLKOUT5/6的$period检查值显示0，原因尚未获厂商确认，不能擅自归类为可忽略误报。TDL与pwm_meta的异步采样setup/hold告警也保留；模型出现数值输出不等于硬件不存在亚稳态。", "",
        "ASYNCHRONOUS寄存器属性来自原始RTL；仿真器对其使用的XON配置属于原工程/厂商模型行为，本次没有人为禁用通知器。有效输出X/Z及FIFO异常由独立监测CSV检查。", "",
        f"整体时序验收：{'PASS' if all(t['wns_ns']>=0 and t['whs_ns']>=0 for t in static.values()) and all(d['total']==0 for d in dynamic.values()) else 'FAIL'}。STA分析min/max角；动态实验只执行slow/MAX，未将其他角或上板测试标为通过。"]
    (ROOT/"TIMING_REPORT.md").write_text("\n".join(timing_lines)+"\n",encoding="utf-8")
    anomalies=["# 连续测量异常与FIFO诊断", "", "当前临时协议的帧头在单元起点上升，数据PWM由峰值起始的三角载波自然比较生成，属于中心对齐。二者混合在20MHz帧部分bank边界产生1.293～1.736ns低电平。本实验保留原输入，不根据失败结果重排帧头或更改波形。", ""]
    for v,s in summaries.items():
        folder=ROOT/"results"/v/"gate_validation"
        truth=read_csv(folder/"truth.csv")
        anomalies += [f"## {v}","",f"输入{s['expected_pulses']}，输出{s['output_widths']}，正确配对{s['valid_matched_pulses']}；缺失R={s['missing_rise_ids']}、F={s['missing_fall_ids']}。", "", "| 无正确配对的输入ID | bank | channel | header | 真实高电平ps | 前一低电平ps |", "|---:|---:|---:|---:|---:|---:|"]
        for event in s["missing"]:
            r=truth[event]; low=int(r["rise_ps"])-int(truth[event-1]["fall_ps"])
            anomalies.append(f"| {event} | {r['bank']} | {r['channel']} | {r['header']} | {r['true_width_ps']} | {low} |")
        anomalies += ["", "| 错配输出对应下降沿ID | 实际来源上升沿ID | 实际脉宽ps | 本下降沿输入高电平ps |", "|---:|---:|---:|---:|"]
        for r in read_csv(folder/"measurements.csv"):
            if r["matched"]=="0": anomalies.append(f"| {r['fall_input_id']} | {r['rise_input_id']} | {r['measured_width_ps']} | {r['true_width_ps']} |")
        anomalies += ["", "全部业务错误事件：", "", "```json",json.dumps(s["business_errors"],ensure_ascii=False,indent=2),"```", ""]
        raw={int(r["time_ps"]):r for r in read_csv(folder/"raw.csv")}
        for e in s["business_errors"]:
            if e["kind"]=="conflict": anomalies.append(f"conflict@{e['time_ps']}ps的前5拍原始帧：`{raw.get(int(e['time_ps'])-10000)}`。")
        probe=ROOT/"results"/v/"gate_fifo_probe/fifo_check.json"
        if probe.exists(): anomalies += ["", "独立错误FIFO诊断：", "```json",probe.read_text(),"```", ""]
    anomalies += ["同帧同时含下一周期0°上升候选与90°/180°下降候选，原candidate逻辑明确判polarity_conflict并丢帧。前两个边界丢失上一数据单元F和下一帧头R，留下的帧头F与旧R形成约50.9ns错误宽度；第三个边界出现孤立F错误2。该原因有真实raw帧及控制错误日志支持，不是关联脚本错位。", "", "独立FIFO诊断只将原ID3047～3054片段平移235160000ps（100MHz与500MHz整周期），保持高低间隔与相位，预期8输入产生7脉宽及一个错误2；两套位流均直接核对500MHz错误入队与100MHz错误读出。它不替代原3512输入验证，不将预期故障当作正常帧通过。", "", "下一步应先确认真实ATC帧头与数据的对齐协议。若真实输入允许同一采样帧含两个异极性边沿，需要独立设计多事件帧缓冲/排序并保留采样帧粗时间标签，再重新实现和独立校准；固定时间戳偏移无法恢复被候选层丢弃的事件。"]
    (ROOT/"ANOMALIES.md").write_text("\n".join(anomalies)+"\n",encoding="utf-8")


def main():
    variants=("baseline","compensated")
    folders={v:ROOT/"results"/v/"gate_validation" for v in variants}
    summaries={v:json.loads((p/"summary.json").read_text()) for v,p in folders.items()}
    static={v:timing(v) for v in variants}
    dynamic={v:dynamic_timing(p) for v,p in folders.items()}
    annotation_ok=True
    for v in variants:
        audit=json.loads((ROOT/"results"/v/"sdf_audit.json").read_text())
        validation_logs=[r for r in audit["case_annotation_logs"] if r["case"]=="gate_validation"]
        annotation_ok &= not audit["missing_critical"] and not audit["changed_critical_sdf_records"] and bool(validation_logs)
        annotation_ok &= all(r["annotation_success"] and not r["annotation_warnings"] for r in validation_logs)
    comparison=json.loads((ROOT/"results/comparison.json").read_text(encoding="utf-8"))
    frontend=frontend_comparison()
    (ROOT/"results/frontend_comparison.json").write_text(json.dumps(frontend,indent=2),encoding="utf-8")
    business_ok=all(s["valid_rate"]==1 and not s["faults"] and not s["business_errors"] and not s["missing"]
        and not s["duplicate"] and s["fifo_sequence_equal"] for s in summaries.values())
    timing_ok=all(s["wns_ns"]>=0 and s["whs_ns"]>=0 and s["wpws_ns"]>=0 for s in static.values())
    status="PASS" if business_ok and timing_ok and annotation_ok and all(d["total"]==0 for d in dynamic.values()) else "FAIL"
    write_reports(summaries,static,dynamic,comparison,frontend,status,business_ok)
    patch="".join("".join(difflib.unified_diff((ROOT/"baseline/rtl"/p.name).read_text().splitlines(True),p.read_text().splitlines(True),fromfile="a/fpga_tdc_v3_cal_rtl/"+p.name,tofile="b/fpga_tdc_v3_cal_rtl/"+p.name)) for p in sorted((ROOT/"rtl").glob("*.v")))
    (ROOT/"补偿RTL变更.patch").write_text(patch,encoding="utf-8")
    versions={}
    for v in variants:
        rtl=ROOT/("baseline/rtl" if v=="baseline" else "rtl")
        versions[v]=dict(part="xc7k325tffg900-2",vivado="2022.2",tap_ps=10,coarse_w=10,carry_num=16,
            compensation_mode="original_no_compensation" if v=="baseline" else "ENABLE_SKEW_COMP=1",
            rtl_sha256={p.name:sha(p) for p in rtl.glob("*.v")},
            constraint_sha256=sha(ROOT/"inputs/combine.xdc"),
            ip_sha256={str(p.relative_to(ROOT/"inputs")):sha(p) for p in (ROOT/"inputs/ip").rglob("*.xci")},
            bit_sha256=sha(ROOT/"results"/v/f"tdc_{v}.bit"),
            dcp_sha256=sha(ROOT/"results"/v/"design.dcp"),
            annotated_sdf_sha256=sha(ROOT/"results"/v/"annotated_design.sdf"),
            calibration_params_sha256=sha(ROOT/"results/calibration_params.tcl") if v=="compensated" else None,
            strategy=(ROOT/"results"/v/"build_metadata.txt").read_text(),
            validation_input_sha256=summaries[v]["stimulus_sha256"])
        (ROOT/"results"/v/"version_manifest.json").write_text(json.dumps(versions[v],indent=2),encoding="utf-8")
    (ROOT/"results/acceptance.json").write_text(json.dumps(dict(status=status,business_ok=business_ok,annotation_ok=annotation_ok,
        static_timing=static,dynamic_timing=dynamic,versions=versions),indent=2),encoding="utf-8")
    manifest={}
    for path in sorted(ROOT.rglob("*")):
        # 归档关键源文件和最终数据，不重复哈希可再生的编译缓存或巨型工具中间库。
        if not path.is_file() or "build" in path.relative_to(ROOT).parts or path.name in ("delivery_manifest.json","evidence_verification.json"): continue
        # 根logs可能正由调用者重定向写入；只哈希已关闭并冻结在results下的仿真日志。
        if path.suffix==".log" and path.relative_to(ROOT).parts[0]=="logs": continue
        if path.suffix in (".v",".sv",".xdc",".xci",".tcl",".py",".ps1",".json",".csv",".txt",".bit",".dcp",".sdf",".md",".png",".svg",".pdf",".log",".patch",".rpt",".jou"):
            manifest[str(path.relative_to(ROOT))]=dict(bytes=path.stat().st_size,sha256=sha(path))
    (ROOT/"results/delivery_manifest.json").write_text(json.dumps(dict(status=status,files=manifest),indent=2),encoding="utf-8")
    print((ROOT/"FINAL_RMS_COMPARISON.md").read_text(encoding="utf-8"))
    print("报告与哈希清单：",ROOT)


if __name__=="__main__": main()
