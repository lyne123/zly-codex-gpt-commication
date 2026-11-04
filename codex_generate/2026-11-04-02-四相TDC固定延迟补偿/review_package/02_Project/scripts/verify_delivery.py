"""核对交付证据完整性；证据一致不代表硬件或帧测试通过。"""
import json
import math
from collections import defaultdict
from pathlib import Path
from experiment import ROOT, read_csv, sha

manifest_path=ROOT/"results/delivery_manifest.json"
manifest=json.loads(manifest_path.read_text())
for name,record in manifest["files"].items():
    path=ROOT/name
    assert path.stat().st_size==record["bytes"],name
    assert sha(path)==record["sha256"],name
original=json.loads((ROOT/"baseline/sha256.json").read_text(encoding="utf-8-sig"))
for row in original:
    assert sha(ROOT/"baseline/rtl"/Path(row["Path"]).name)==row["Hash"].lower()
active=ROOT.parents[1]/"fpga_tdc_v3_cal_rtl"
if active.exists():
    for path in (ROOT/"rtl").glob("*.v"): assert sha(active/path.name)==sha(path),path.name
parameters=read_csv(ROOT/"results/tdc_skew_calibration.csv")
assert len(parameters)==8
observations=defaultdict(list)
for row in read_csv(ROOT/"results/calibration_observations.csv"):
    observations[int(row["index"]),int(row["type"])].append(int(row["error_ps"]))
for row in parameters:
    key=int(row["sel_index"]),int(row["polarity"]=="rise")
    values=observations[key]
    assert len(values)==int(row["n"])
    assert round(sum(values)/len(values))==int(row["offset_ps"])
    assert -131072<=int(row["offset_ps"])<=131071
hashes=[]
for variant in ("baseline","compensated"):
    folder=ROOT/"results"/variant
    version=json.loads((folder/"version_manifest.json").read_text())
    assert sha(folder/f"tdc_{variant}.bit")==version["bit_sha256"]
    hashes.append(version["bit_sha256"])
    audit=json.loads((folder/"sdf_audit.json").read_text())
    assert not audit["missing_critical"] and not audit["changed_critical_sdf_records"]
    assert audit["critical_inventory"]==dict(LUT1=7,CARRY4=64,FDRE=256)
    assert json.loads((folder/"gate_fifo_probe/fifo_check.json").read_text())["status"]=="PASS"
    case=folder/"gate_validation"
    summary=json.loads((case/"summary.json").read_text())
    assert sha(case/"stimulus.txt")==summary["stimulus_sha256"]
    for r in summary["groups"].values():
        if r["n"]:
            assert math.isclose(r["rmse_ps"]**2,r["bias_ps"]**2+r["std_ps"]**2,rel_tol=1e-10,abs_tol=1e-8)
    assert (case/"elaboration.log").read_text().find("SDF backannotation was successful")>=0
assert hashes[0]!=hashes[1],"两套位流不能是同一文件"
a=ROOT/"results/baseline/gate_validation"
b=ROOT/"results/compensated/gate_validation"
assert sha(a/"stimulus.txt")==sha(b/"stimulus.txt")
assert sha(a/"truth.csv")==sha(b/"truth.csv")
assert "ALL_COMPENSATION_TESTS_PASS" in (ROOT/"logs/compensation_test.log").read_text()
assert len(list((ROOT/"results/figures").glob("*.png")))==7
assert len(list((ROOT/"results/figures").glob("*.svg")))==7
assert len(list((ROOT/"results/figures").glob("*.pdf")))==7
result=dict(evidence_integrity="PASS",experiment_acceptance=manifest["status"],
    checked_files=len(manifest["files"]),delivery_manifest_sha256=sha(manifest_path),bit_sha256=hashes)
(ROOT/"results/evidence_verification.json").write_text(json.dumps(result,indent=2),encoding="utf-8")
print(json.dumps(result,indent=2))
