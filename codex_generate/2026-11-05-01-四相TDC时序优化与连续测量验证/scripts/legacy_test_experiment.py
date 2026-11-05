"""验证真值生成、数据隔离和统计定义，避免把去均值RMS误当RMSE。"""
import contextlib
import io
import math
from experiment import ROOT, generate, read_csv, sha, stats, circular, MODULO, calibrate

before={p.name:sha(p) for p in (ROOT/"sim/stimuli").glob("*")}
with contextlib.redirect_stdout(io.StringIO()):
    generate()
after={p.name:sha(p) for p in (ROOT/"sim/stimuli").glob("*")}
assert before==after,"同参数激励不确定"
cal=read_csv(ROOT/"sim/stimuli/calibration_truth.csv")
val=read_csv(ROOT/"sim/stimuli/validation_truth.csv")
assert len(cal)==800 and len(val)==3512
assert set(int(r["phase_ps"]) for r in cal)==set(range(0,2000,20))
for case, width in (("20MHz_5",2500),("20MHz_95",47500),("fixed_25300",25300)):
    assert {int(r["true_width_ps"]) for r in val if r["case"]==case}=={width}
for name in ("ATC_10MHz","ATC_20MHz"):
    frame=[r for r in val if r["case"]==name]
    assert len(frame)==1056
    assert sum(int(r["header"])>=0 for r in frame)==32
    assert len({(r["bank"],r["channel"]) for r in frame if int(r["channel"])>=0})==1024
    for r in frame:
        assert int(r["fall_ps"])-int(r["rise_ps"])==int(r["true_width_ps"])
for a,b in zip(val,val[1:]):
    assert int(a["fall_ps"])<int(b["rise_ps"])
result=stats([1,3])
assert result["bias_ps"]==2 and result["std_ps"]==1
assert math.isclose(result["rmse_ps"]**2,result["bias_ps"]**2+result["std_ps"]**2)
assert circular(MODULO-10)==-10 and circular(MODULO+10)==10
try:
    calibrate(ROOT/"results/baseline/rtl_validation")
except ValueError:
    pass
else:
    raise AssertionError("必须拒绝验证集或RTL作为校准来源")
print("PASS: deterministic stimulus, 1056-cell frames, narrow pulses, RMSE and calibration isolation")
