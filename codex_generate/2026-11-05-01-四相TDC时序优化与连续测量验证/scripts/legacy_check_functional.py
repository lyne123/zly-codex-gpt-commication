"""核对原始RTL在理想10ps模型下的功能；不能据此宣称物理精度。"""
import json
import sys
from pathlib import Path
from experiment import ROOT, MODULO, numeric, read_csv, stats

case=Path(sys.argv[1]) if len(sys.argv)>1 else ROOT/"results/baseline/rtl_validation"
truth=read_csv(case/"truth.csv" if (case/"truth.csv").exists() else ROOT/"sim/stimuli/validation_truth.csv")
timestamps=numeric(case/"timestamps.csv")
widths=numeric(case/"widths.csv")
fifo=numeric(case/"fifo.csv")
errors=read_csv(case/"errors.csv")
epoch=int(read_csv(case/"clock_epoch.csv")[0]["epoch_ps"])
assert len(timestamps)==2*len(truth), (len(timestamps),len(truth))
assert len(widths)==len(truth)==len(fifo)
assert not errors, errors[:5]
assert [r["width_ps"] for r in fifo]==[r["width_ps"] for r in widths]
width_errors=[]
for i,t in enumerate(timestamps):
    pulse=truth[i//2]
    polarity=int(i%2==0)
    true=int(pulse["rise_ps" if polarity else "fall_ps"])
    assert t["type"]==polarity
    # 此30000ps仅为该理想模型下源码流水线的共同整数周期偏移。
    error=(t["timestamp_ps"]-(true-epoch)-30000+MODULO//2)%MODULO-MODULO//2
    assert abs(error)<=10, (i,error)
for t,w in zip(truth,widths):
    error=w["width_ps"]-int(t["true_width_ps"])
    assert abs(error)<=20,(t["pulse_id"],error)
    width_errors.append(error)
result=dict(status="PASS",simulation_level="RTL_WITH_IDEAL_TEST_MODELS_ONLY",
    physical_accuracy_claim=False,expected_pulses=len(truth),output_widths=len(widths),
    timestamp_count=len(timestamps),business_errors=len(errors),fifo_sequence_equal=True,
    ideal_model_width_errors=stats(width_errors))
(case/"functional_check.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
