"""逐事件比较两个真实SDF批次，并另存同布局的数字补偿重算。"""
import json
from collections import Counter
from experiment import ROOT, MODULO, read_csv, write_csv, stats


def compare():
    folders={v:ROOT/"results"/v/"gate_validation" for v in ("baseline","compensated")}
    summaries={v:json.loads((p/"summary.json").read_text()) for v,p in folders.items()}
    assert summaries["baseline"]["stimulus_sha256"]==summaries["compensated"]["stimulus_sha256"]
    measurements={v:read_csv(p/"measurements.csv") for v,p in folders.items()}
    # 只以可追溯的事件ID配对；丢失、额外输出及重复分别保留在summary中。
    indexed={v:{int(r["pulse_id"]):r for r in rows if int(r["matched"])} for v,rows in measurements.items()}
    paired=[]
    for event in sorted(indexed["baseline"].keys() & indexed["compensated"].keys()):
        a,b=(indexed[v][event] for v in ("baseline","compensated"))
        assert all(a[k]==b[k] for k in ("rise_ps","fall_ps","true_width_ps","case"))
        paired.append(dict(pulse_id=event,case=a["case"],true_width_ps=a["true_width_ps"],
            baseline_width_ps=a["measured_width_ps"],compensated_width_ps=b["measured_width_ps"],
            baseline_error_ps=a["error_ps"],compensated_error_ps=b["error_ps"]))
    write_csv(ROOT/"results/paired_comparison.csv",paired)
    metrics=[]
    for group in sorted(summaries["baseline"]["groups"].keys() | summaries["compensated"]["groups"].keys()):
        before=summaries["baseline"]["groups"].get(group,stats([]))
        after=summaries["compensated"]["groups"].get(group,stats([]))
        improvement=None if not before["rmse_ps"] or after["rmse_ps"] is None else 1-after["rmse_ps"]/before["rmse_ps"]
        metrics.append(dict(test=group,baseline_n=before["n"],compensated_n=after["n"],
            baseline_expected_n=before.get("expected_n",0),compensated_expected_n=after.get("expected_n",0),
            baseline_complete=before.get("complete",False),compensated_complete=after.get("complete",False),
            baseline_rmse_ps=before["rmse_ps"],compensated_rmse_ps=after["rmse_ps"],
            baseline_bias_ps=before["bias_ps"],compensated_bias_ps=after["bias_ps"],
            baseline_std_ps=before["std_ps"],compensated_std_ps=after["std_ps"],improvement=improvement))
        metrics[-1].update(baseline_max_abs_ps=before["max_abs_ps"],compensated_max_abs_ps=after["max_abs_ps"])
    write_csv(ROOT/"results/comparison_metrics.csv",metrics)
    parameters=json.loads((ROOT/"results/calibration.json").read_text())["parameters"]
    offsets={(p["sel_index"],p["polarity"]):p["offset_ps"] for p in parameters}
    replay=[]
    for r in measurements["baseline"]:
        if not int(r["matched"]): continue
        rise=(int(r["rise_timestamp_ps"])-offsets[int(r["rise_index"]),"rise"])%MODULO
        fall=(int(r["fall_timestamp_ps"])-offsets[int(r["fall_index"]),"fall"])%MODULO
        corrected=(fall-rise)%MODULO
        replay.append(dict(pulse_id=r["pulse_id"],case=r["case"],true_width_ps=r["true_width_ps"],
            digitally_replayed_width_ps=corrected,error_ps=corrected-int(r["true_width_ps"])))
    write_csv(ROOT/"results/same_layout_counterfactual.csv",replay)
    replay_by_id={int(r["pulse_id"]):r for r in replay}
    physical_deltas=[int(r["compensated_width_ps"])-int(replay_by_id[int(r["pulse_id"])]["digitally_replayed_width_ps"]) for r in paired]
    report=dict(paired_events=len(paired),
        baseline_only_ids=sorted(indexed["baseline"].keys()-indexed["compensated"].keys()),
        compensated_only_ids=sorted(indexed["compensated"].keys()-indexed["baseline"].keys()),
        independent_implementation_results=metrics,
        same_layout_digital_replay=stats(int(r["error_ps"]) for r in replay),
        actual_implementation_minus_same_layout_replay=stats(physical_deltas),
        replay_note="同一baseline SDF样本的数字反事实重算；不是补偿版SDF仿真或独立硬件测量。",
        source_event_id_duplicates={v:[k for k,n in Counter(int(r["pulse_id"]) for r in rows if int(r["matched"])).items() if n>1] for v,rows in measurements.items()})
    (ROOT/"results/comparison.json").write_text(json.dumps(report,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=="__main__": compare()
