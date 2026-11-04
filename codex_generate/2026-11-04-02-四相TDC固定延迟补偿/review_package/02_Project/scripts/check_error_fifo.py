"""重现既有窄低电平异常，独立检查同一bitstream的错误FIFO跨域读出。"""
import json
import sys
from experiment import ROOT, read_csv, write_csv, numeric, sha

if sys.argv[1]=="generate":
    source=read_csv(ROOT/"results/baseline/gate_validation/truth.csv")
    rows=[dict(r) for r in source if 3047<=int(r["pulse_id"])<=3054]
    shift=((int(rows[0]["rise_ps"])-10000000)//10000)*10000
    assert shift%10000==0
    for r in rows:
        r["rise_ps"]=int(r["rise_ps"])-shift
        r["fall_ps"]=int(r["fall_ps"])-shift
    write_csv(ROOT/"sim/stimuli/fifo_probe_truth.csv",rows)
    with (ROOT/"sim/stimuli/fifo_probe.txt").open("w",encoding="ascii") as stream:
        for r in rows: stream.write("{pulse_id} {rise_ps} {fall_ps} {period_ps}\n".format(**r))
    print("诊断仅平移原输入片段的绝对时间，保持高低电平及500/100MHz相位，shift_ps=",shift)
else:
    variant=sys.argv[1]
    folder=ROOT/"results"/variant/"gate_fifo_probe"
    assert (folder/"run_manifest.txt").exists(),"诊断尚未结束"
    written=[int(r["code"]) for r in read_csv(folder/"errors.csv") if r["kind"]=="merge"]
    received=[r["code"] for r in numeric(folder/"error_fifo.csv")]
    assert written==[2],("未重现唯一预期孤立下降沿",written)
    assert received==written,("错误FIFO跨域数据或数量不一致",received,written)
    widths=[r["width_ps"] for r in numeric(folder/"widths.csv")]
    assert len(widths)==7,("8输入中的预期7个有效脉宽未复现",len(widths))
    assert widths==[r["width_ps"] for r in numeric(folder/"fifo.csv")]
    assert not any(r["kind"] in ("overflow","unknown_control","unknown_timestamp","unknown_width") for r in read_csv(folder/"errors.csv"))
    result=dict(status="PASS",scope="post-route directed error-FIFO reproduction; not a precision-validation replacement",
        source_error_codes=written,read_100MHz_error_codes=received,result_fifo_sequence_equal=True,
        stimulus_sha256=sha(folder/"stimulus.txt"))
    (folder/"fifo_check.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
    print(json.dumps(result,indent=2))
