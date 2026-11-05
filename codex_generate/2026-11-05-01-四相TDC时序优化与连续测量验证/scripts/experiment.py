"""确定性激励、独立校准和逐事件统计；只读取实际仿真CSV。"""
import argparse
import bisect
import csv
import hashlib
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODULO = 2000 * 1024
PHASES = (90, 180, 270, 0)


def sha(path):
    digest=hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda:stream.read(1024*1024),b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path, rows, fields=None):
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields or list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_csv(path):
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def numeric(path):
    rows = read_csv(path)
    for row in rows:
        for key, value in row.items():
            if key != "kind":
                row[key] = int(value)
    return rows


def stats(values):
    values = list(values)
    if not values:
        return dict(n=0, rmse_ps=None, bias_ps=None, std_ps=None, max_abs_ps=None)
    bias = statistics.mean(values)
    return dict(n=len(values), rmse_ps=math.sqrt(statistics.mean(x*x for x in values)),
                bias_ps=bias, std_ps=math.sqrt(statistics.mean((x-bias)**2 for x in values)),
                max_abs_ps=max(map(abs, values)))


def circular(value):
    return (value + MODULO//2) % MODULO - MODULO//2


def generate():
    out = ROOT / "sim" / "stimuli"
    out.mkdir(exist_ok=True)
    # 暂定协议集中管理；缺少芯片规范，不能将本配置称为真实ATC协议。
    cfg_path = ROOT / "sim" / "atc_assumptions.json"
    if not cfg_path.exists():
        cfg_path.write_text(json.dumps(dict(status="PROVISIONAL_NOT_CHIP_PROTOCOL",
            banks=16, channels_per_bank=64, header_duties=[0.05, 0.95],
            bank_order=list(range(16)), channel_order=list(range(64)),
            cell_is_one_pwm_period=True, header_alignment="edge",data_alignment="natural_centered",modulation_hz=10000,
            analog_amplitude=0.9, analog_offset=0.0,
            carrier="symmetric triangle -1..1; natural sine comparison, 1 ps grid",
            duty_mapping="PWM high when analog sine > triangle; no ADC scale inferred"),
            indent=2), encoding="utf-8")
    cfg = json.loads(cfg_path.read_text(encoding="utf-8"))
    if cfg.get("header_alignment","edge")!="edge" or cfg.get("data_alignment","natural_centered")!="natural_centered":
        raise ValueError("本暂定激励仅实现边沿对齐帧头和自然中心对齐数据；其他排列需按真实协议重新实现")
    if sorted(cfg["bank_order"]) != list(range(16)) or sorted(cfg["channel_order"]) != list(range(64)):
        raise ValueError("暂定协议的bank/channel排列必须完整")
    for dataset in ("smoke", "calibration", "validation"):
        rows = []
        cursor = 10000000

        def append_pulse(case, period, width, phase=None, bank=-1, channel=-1, header=-1):
            nonlocal cursor
            if phase is None:
                rise=cursor
            elif dataset=="calibration":
                # 保留已执行独立校准批次的原调度：50.00~52.02ns间隔，真实边沿已逐条记录。
                # 本批次用于相位扫描，不将名义50ns标签宣称为实际固定载波周期。
                rise=((cursor+1999)//2000)*2000+phase
            else:
                # 相同相位重复时不额外插入2ns；相位切换仅增加必要的相位差。
                rise=cursor+((phase-cursor)%2000)
            width = int(width)
            if not 0 < width < period:
                raise ValueError("激励高低电平均必须大于0")
            rows.append(dict(pulse_id=len(rows), dataset=dataset, case=case,
                rise_ps=rise, fall_ps=rise+width, period_ps=period,
                true_width_ps=width, phase_ps=rise % 2000,
                bank=bank, channel=channel, header=header))
            cursor = rise+period

        step = 200 if dataset == "smoke" else 20
        shift = 10 if dataset == "validation" else 0
        repeats = 1 if dataset == "smoke" else (8 if dataset == "calibration" else 2)
        if dataset in ("smoke", "calibration"):
            for phase in range(0, 2000, step):
                for _ in range(repeats):
                    append_pulse("fixed_25300", 50000, 25300, phase)
        else:
            cases = [("fixed_25300",50000,25300),("10MHz_50",100000,50000),
                     ("20MHz_50",50000,25000),("10MHz_5",100000,5000),
                     ("10MHz_95",100000,95000),("20MHz_5",50000,2500),
                     ("20MHz_95",50000,47500)]
            for name, period, width in cases:
                for phase in range(shift, 2000, step):
                    for _ in range(repeats):
                        append_pulse(name,period,width,phase)
            # 连续帧中没有额外相位重置，每单元严格一个载波周期。
            for period in (100000,50000):
                frame_start = cursor
                for bank in cfg["bank_order"]:
                    for header, duty in enumerate(cfg["header_duties"]):
                        append_pulse(f"ATC_{1000000//period}MHz",period,round(period*duty),
                                     bank=bank,header=header)
                    for channel in cfg["channel_order"]:
                        # 自然采样SPWM：在三角波左右半周期分别二分求正弦交点。
                        # 载波在本单元起点为+1，半周期到-1，再升到+1。
                        t0 = cursor

                        # 载波峰值为单元边界，正脉冲位于周期内部。
                        def high(t):
                            analog=cfg["analog_offset"]+cfg["analog_amplitude"]*math.sin(
                                2*math.pi*cfg["modulation_hz"]*(t0-frame_start+t)/1e12)
                            triangle=1-4*t/period if t<=period/2 else -3+4*t/period
                            return analog>triangle
                        edges=[]
                        for lo,hi in ((0,period//2),(period//2,period)):
                            initial=high(lo)
                            while hi-lo>1:
                                mid=(lo+hi)//2
                                if high(mid)==initial: lo=mid
                                else: hi=mid
                            edges.append(hi)
                        rise,fall=t0+edges[0],t0+edges[1]
                        rows.append(dict(pulse_id=len(rows),dataset=dataset,
                            case=f"ATC_{1000000//period}MHz",rise_ps=rise,fall_ps=fall,
                            period_ps=period,true_width_ps=fall-rise,phase_ps=rise%2000,
                            bank=bank,channel=channel,header=-1))
                        cursor=t0+period
        # 真值脉宽只由生成的整数ps边沿相减，不使用理想duty代替实际比较结果。
        if any(a["fall_ps"] >= b["rise_ps"] for a,b in zip(rows,rows[1:])):
            raise ValueError("激励边沿顺序错误")
        for i,row in enumerate(rows):
            row["nominal_carrier_period_ps"]=row["period_ps"]
            row["actual_rise_interval_ps"]=rows[i+1]["rise_ps"]-row["rise_ps"] if i+1<len(rows) else 0
            row["rise_interval_known"]=int(i+1<len(rows))
        write_csv(out/f"{dataset}_truth.csv",rows)
        with (out/f"{dataset}.txt").open("w",encoding="ascii") as stream:
            for row in rows:
                stream.write("{pulse_id} {rise_ps} {fall_ps} {period_ps}\n".format(**row))
        write_csv(out/f"{dataset}_edges.csv",(dict(pulse_id=r["pulse_id"],type=p,
            time_ps=r["rise_ps"] if p else r["fall_ps"]) for r in rows for p in (1,0)))
        if dataset=="validation":
            write_csv(out/"header_positions.csv",(r for r in rows if r["header"]>=0))
            write_csv(out/"bank_channel_map.csv",(r for r in rows if r["bank"]>=0))
        print(dataset,len(rows),"pulses",sha(out/f"{dataset}.txt"))


def load_case(case):
    case=Path(case).resolve()
    truth_path=case/"truth.csv"
    if not truth_path.exists(): truth_path=ROOT/"sim"/"stimuli"/(case.name.split("_")[-1]+"_truth.csv")
    truth=read_csv(truth_path)
    for row in truth:
        for key in row:
            if key not in ("case","dataset"): row[key]=int(row[key])
    return case,truth


def calibrate(case):
    case,truth=load_case(case)
    if case.name!="gate_calibration":
        raise ValueError("只能使用独立实现后SDF校准集，不能使用理想RTL或验证数据")
    if "level=gate" not in (case/"run_manifest.txt").read_text(encoding="utf-8"):
        raise ValueError("缺少实现后时序仿真执行记录")
    epoch=int(read_csv(case/"clock_epoch.csv")[0]["epoch_ps"])
    times={p:[r["rise_ps" if p else "fall_ps"] for r in truth] for p in (0,1)}
    raw=numeric(case/"raw.csv")
    candidates=numeric(case/"candidate.csv")
    timestamps=numeric(case/"timestamps.csv")
    if not raw or not candidates or len(candidates)!=len(timestamps):
        raise ValueError("校准无有效观测或候选/时间戳数量不一致")
    by_time={r["time_ps"]:r for r in raw}
    groups=defaultdict(list)
    latencies=defaultdict(list)
    audit=[]
    for r in raw:
        for index in range(4):
            if not r["mask"] & (1<<index): continue
            polarity=(r["polarity"]>>(index*2)) & 3
            if polarity not in (2,3): raise ValueError("valid极性不合法")
            p=int(polarity==3)
            k=bisect.bisect_right(times[p],r["time_ps"])-1
            if k<0: raise ValueError("找不到因果真值")
            true=times[p][k]
            code=(r["codes"]>>(index*8)) & 255
            tap=code if p else 64-code
            measured=(((r["coarse"]+6)%1024)*2000+(index+1)*500-tap*10)%MODULO
            error=circular(measured-(true-epoch)%MODULO)
            groups[index,p].append(error)
            latencies[index,p].append(r["time_ps"]-true)
            audit.append(dict(index=index,phase=PHASES[index],type=p,pulse_id=k,
                time_ps=r["time_ps"],true_time_ps=true,phase_ps=(true-epoch)%2000,
                program_phase_ps=true%2000,
                code=code,timestamp_ps=measured,error_ps=error))
    # 独立核验虚拟四通道公式与真实选中输出完全一致，禁止只凭流水线猜测校准。
    for c,t in zip(candidates,timestamps):
        if c["type"]!=t["type"] or t["time_ps"]-c["time_ps"]!=10000:
            raise ValueError("候选到时间戳的type/5拍延迟不成立")
        tap=c["code"] if c["type"] else 64-c["code"]
        expected=(((c["coarse"]+1)%1024)*2000+(c["index"]+1)*500-tap*10)%MODULO
        if expected!=t["timestamp_ps"]:
            raise ValueError("粗中细时间模型与实际baseline输出不一致")
        f=by_time.get(c["time_ps"]-10000)
        if f is None or not f["mask"] & (1<<c["index"]) or (
            (f["codes"]>>(c["index"]*8)) & 255)!=c["code"]:
            raise ValueError("raw与候选5拍对齐不成立")
    params=[]
    for index in range(4):
        for p in (1,0):
            values=groups[index,p]
            if len(values)<20: raise ValueError(f"通道{index}/{p}样本不足: {len(values)}")
            offset=round(statistics.mean(values))
            if not -131072<=offset<=131071: raise ValueError("偏移超过18位范围")
            item=dict(sel_index=index,tdl_phase=PHASES[index],polarity="rise" if p else "fall",
                offset_ps=offset,**stats(values),residual_std_ps=statistics.pstdev(values),
                latency_ps=statistics.median(latencies[index,p]),
                phase_min_ps=min(r["phase_ps"] for r in audit if r["index"]==index and r["type"]==p),
                phase_max_ps=max(r["phase_ps"] for r in audit if r["index"]==index and r["type"]==p))
            params.append(item)
    # 单独冻结候选输出延迟，用于验证集事件关联，不改变测量数值。
    candidate_latency=defaultdict(list)
    for c in candidates:
        p=c["type"]
        k=bisect.bisect_right(times[p],c["time_ps"])-1
        candidate_latency[c["index"],p].append(c["time_ps"]-times[p][k])
    metadata=dict(status="MEASURED_POST_IMPLEMENTATION_SDF",epoch_ps=epoch,
        source_case=str(case),parameters=params,
        candidate_latency={f"{i},{p}":statistics.median(v) for (i,p),v in candidate_latency.items()},
        sha256={str(f.relative_to(ROOT)):sha(f) for f in
            [case/"raw.csv",case/"candidate.csv",case/"timestamps.csv",
             ROOT/"sim/stimuli/calibration_truth.csv",case.parent/"design.v",case.parent/"design.sdf",
             case.parent/"annotated_design.v",case.parent/"annotated_design.sdf",case/"input_sha256.json"]})
    write_csv(ROOT/"results/tdc_skew_calibration.csv",params)
    write_csv(ROOT/"results/calibration_observations.csv",audit)
    coverage=defaultdict(list)
    for r in audit:
        coverage[r["index"],r["type"],r["phase_ps"]].append(r["error_ps"])
    write_csv(ROOT/"results/calibration_phase_coverage.csv",(dict(sel_index=i,type=p,
        phase_ps=phase,**stats(v)) for (i,p,phase),v in sorted(coverage.items())))
    (ROOT/"results/calibration.json").write_text(json.dumps(metadata,indent=2),encoding="utf-8")
    generics=["ENABLE_SKEW_COMP=1"]
    for r in params:
        generics.append(f"{r['polarity'].upper()}_OFFSET_{r['tdl_phase']}_PS={r['offset_ps']}")
    (ROOT/"results/calibration_params.tcl").write_text(
        "# 参数仅来自独立实现后校准批次，单位ps。\nset compensation_generics {"+" ".join(generics)+"}\n",encoding="utf-8")
    print(json.dumps(metadata,indent=2))


def analyze(case, calibration_path=None):
    case,truth=load_case(case)
    if case.name.startswith("gate_") and not (case/"run_manifest.txt").exists():
        raise ValueError("仿真批次尚未正常结束，拒绝将部分数据作为完整结果")
    calibration=json.loads(Path(calibration_path or ROOT/"results/calibration.json").read_text(encoding="utf-8"))
    candidates=numeric(case/"candidate.csv")
    timestamps=numeric(case/"timestamps.csv")
    widths=numeric(case/"widths.csv")
    fifo=numeric(case/"fifo.csv")
    errors=read_csv(case/"errors.csv")
    epoch=int(read_csv(case/"clock_epoch.csv")[0]["epoch_ps"])
    times={p:[r["rise_ps" if p else "fall_ps"] for r in truth] for p in (0,1)}
    association=[]
    faults=[]
    offsets={(r["sel_index"],int(r["polarity"]=="rise")):r["offset_ps"] for r in calibration["parameters"]}
    compensated=case.parent.name=="compensated"
    for seq,t in enumerate(timestamps):
        if seq>=len(candidates):
            faults.append(dict(kind="extra_timestamp",row=seq)); continue
        c=candidates[seq]
        key=f"{c['index']},{c['type']}"
        if key not in calibration["candidate_latency"]:
            faults.append(dict(kind="untrained_selection",row=seq)); continue
        target=c["time_ps"]-calibration["candidate_latency"][key]
        k=bisect.bisect_left(times[c["type"]],target)
        options=[j for j in (k-1,k) if 0<=j<len(truth)]
        k=min(options,key=lambda j:abs(times[c["type"]][j]-target))
        residual=abs(times[c["type"]][k]-target)
        distances=sorted(abs(times[c["type"]][j]-target) for j in options)
        association_margin=distances[1]-distances[0] if len(distances)>1 else MODULO
        if association_margin==0: faults.append(dict(kind="ambiguous_equal_distance",row=seq))
        if residual>2000:
            faults.append(dict(kind="ambiguous_truth",row=seq,residual_ps=residual))
        true=times[c["type"]][k]
        tap=c["code"] if c["type"] else 64-c["code"]
        expected=(((c["coarse"]+1)%1024)*2000+(c["index"]+1)*500-tap*10
                  -(offsets[c["index"],c["type"]] if compensated else 0))%MODULO
        if expected!=t["timestamp_ps"] or c["type"]!=t["type"] or t["time_ps"]-c["time_ps"]!=10000:
            faults.append(dict(kind="timestamp_model_or_alignment",row=seq))
        association.append(dict(pulse_id=k,type=t["type"],index=c["index"],
            code=c["code"],time_ps=t["time_ps"],timestamp_ps=t["timestamp_ps"],
            true_time_ps=true,error_ps=circular(t["timestamp_ps"]-(true-epoch)%MODULO)))
        association[-1]["association_residual_ps"]=residual
        association[-1]["association_margin_ps"]=association_margin
    pending=None
    pairs=[]
    for event in association:
        if event["type"]:
            pending=event
        elif pending:
            pairs.append((pending,event)); pending=None
    measurements=[]
    for seq,w in enumerate(widths):
        if seq>=len(pairs):
            faults.append(dict(kind="extra_width",row=seq)); continue
        rise,fall=pairs[seq]
        matched=(rise["pulse_id"]==fall["pulse_id"])
        if not matched: faults.append(dict(kind="mispair",row=seq))
        if (fall["timestamp_ps"]-rise["timestamp_ps"])%MODULO != w["width_ps"]:
            faults.append(dict(kind="width_arithmetic",row=seq))
        if w["time_ps"]-fall["time_ps"]!=6000:
            faults.append(dict(kind="merge_latency",row=seq))
        r=truth[fall["pulse_id"]]
        measurements.append(dict(**r,matched=int(matched),clock_relative_phase_ps=(r["rise_ps"]-epoch)%2000,rise_index=rise["index"],
            rise_input_id=rise["pulse_id"],fall_input_id=fall["pulse_id"],
            fall_index=fall["index"],rise_timestamp_ps=rise["timestamp_ps"],
            fall_timestamp_ps=fall["timestamp_ps"],measured_width_ps=w["width_ps"],
            error_ps=w["width_ps"]-r["true_width_ps"]))
    counts=Counter(m["pulse_id"] for m in measurements if m["matched"])
    edge_counts={p:Counter(r["pulse_id"] for r in association if r["type"]==p) for p in (0,1)}
    channel_rows=[]
    for index in range(4):
        for polarity in (1,0):
            subset=[r for r in association if r["index"]==index and r["type"]==polarity]
            phases=sorted({(r["true_time_ps"]-epoch)%2000 for r in subset})
            total=sum(edge_counts[polarity].values())
            channel_rows.append(dict(sel_index=index,tdl_phase=PHASES[index],polarity="rise" if polarity else "fall",
                **stats(r["error_ps"] for r in subset),selection_ratio_within_polarity=len(subset)/total if total else None,
                phase_min_ps=min(phases) if phases else None,phase_max_ps=max(phases) if phases else None,
                phase_points_ps=json.dumps(phases)))
    write_csv(case/"channel_statistics.csv",channel_rows)
    missing=[r["pulse_id"] for r in truth if not counts[r["pulse_id"]]]
    duplicate=[k for k,v in counts.items() if v>1]
    groups=defaultdict(list)
    expected_groups=Counter()
    unique_groups=defaultdict(set)
    def categories(row):
        keys=[row["case"],"all"]
        if row["bank"]>=0: keys.append("complete_frame")
        if row["header"]==0: keys.append("header_5")
        if row["header"]==1: keys.append("header_95")
        if row["bank"]>=0 and row["header"]<0: keys.append("spwm_data")
        return keys
    for row in truth:
        expected_groups.update(categories(row))
    for m in measurements:
        if not m["matched"]: continue
        for key in categories(m):
            groups[key].append(m["error_ps"])
            unique_groups[key].add(m["pulse_id"])
    summary=dict(expected_pulses=len(truth),output_widths=len(widths),
        valid_matched_pulses=len(counts),valid_rate=len(counts)/len(truth),
        missing=missing,duplicate=duplicate,faults=faults,business_errors=errors,
        missing_rise_ids=[r["pulse_id"] for r in truth if not edge_counts[1][r["pulse_id"]]],
        missing_fall_ids=[r["pulse_id"] for r in truth if not edge_counts[0][r["pulse_id"]]],
        duplicate_rise_ids=[k for k,n in edge_counts[1].items() if n>1],
        duplicate_fall_ids=[k for k,n in edge_counts[0].items() if n>1],
        candidate_count=len(candidates),timestamp_count=len(timestamps),
        fifo_sequence_equal=[r["width_ps"] for r in fifo]==[r["width_ps"] for r in widths],
        rise=stats(r["error_ps"] for r in association if r["type"]),
        fall=stats(r["error_ps"] for r in association if not r["type"]),
        selection_counts=dict(Counter(str(r["index"]) for r in association)),
        maximum_association_residual_ps=max((r["association_residual_ps"] for r in association),default=None),
        minimum_association_margin_ps=min((r["association_margin_ps"] for r in association),default=None),
        groups={k:dict(**stats(groups[k]),expected_n=expected_groups[k],matched_unique_n=len(unique_groups[k]),
            complete=len(unique_groups[k])==expected_groups[k] and len(groups[k])==expected_groups[k]) for k in expected_groups},
        stimulus_sha256=sha(case/"stimulus.txt" if (case/"stimulus.txt").exists() else ROOT/"sim/stimuli"/(case.name.split("_")[-1]+".txt")))
    write_csv(case/"measurements.csv",measurements,
        fields=list(measurements[0]) if measurements else list(truth[0])+["matched","error_ps"])
    write_csv(case/"associated_timestamps.csv",association,
        fields=list(association[0]) if association else ["pulse_id","type","index","error_ps"])
    (case/"summary.json").write_text(json.dumps(summary,indent=2),encoding="utf-8")
    print(json.dumps({k:v for k,v in summary.items() if k not in ("business_errors","missing","faults")},indent=2))
    print("missing",len(missing),"faults",len(faults),"business_errors",len(errors))


if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("action",choices=["generate","calibrate","analyze"])
    parser.add_argument("case",nargs="?")
    args=parser.parse_args()
    if args.action=="generate": generate()
    elif args.action=="calibrate": calibrate(args.case)
    else: analyze(args.case)
