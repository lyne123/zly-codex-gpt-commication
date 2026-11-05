"""核对关键单元SDF清单、注释日志及原导出SDF的一致性。"""
import json
import re
from collections import Counter
from experiment import ROOT, read_csv, sha


def cells(path):
    text=path.read_text(encoding="utf-8")
    matches=list(re.finditer(r'\(CELL\s+\(CELLTYPE "([^"]+)"\)\s+\(INSTANCE ([^)]*)\)',text))
    result={}
    for i,m in enumerate(matches):
        name=m[2].replace("\\", "")
        block=text[m.start():matches[i+1].start() if i+1<len(matches) else len(text)]
        result[name]=(m[1],Counter(s.strip() for s in block.splitlines() if s.strip()))
    return result


def audit(variant):
    folder=ROOT/"results"/variant
    original=cells(folder/"design.sdf")
    annotated=cells(folder/"annotated_design.sdf")
    structure=read_csv(folder/"frontend_structure.csv")
    critical=Counter()
    missing=[]
    changed=[]
    for row in structure:
        name=row["name"]
        critical[row["ref_name"]]+=1
        if name not in annotated: missing.append(name)
        elif original.get(name)!=annotated[name]: changed.append(name)
    cases=[]
    for p in folder.glob("gate_*/elaboration.log"):
        text=p.read_text(encoding="utf-8",errors="replace")
        cases.append(dict(case=p.parent.name,annotation_success="SDF backannotation was successful" in text,
            annotation_warnings=[line for line in text.splitlines() if "SDF" in line and ("WARNING" in line or "ERROR" in line)]))
    result=dict(variant=variant,critical_inventory=dict(critical),missing_critical=missing,
        changed_critical_sdf_records=changed,total_sdf_cells=len(annotated),
        cell_record_inventory_equal=original==annotated,case_annotation_logs=cases,
        note="清单覆盖不是仿真器逐路径百分比报告；时序违例另行统计，不能据此宣称时序通过。",
        sha256={f.name:sha(f) for f in [folder/"design.dcp",folder/"design.sdf",folder/"annotated_design.sdf",folder/"annotated_design.v"]})
    (folder/"sdf_audit.json").write_text(json.dumps(result,indent=2,ensure_ascii=False),encoding="utf-8")
    print(json.dumps(result,indent=2,ensure_ascii=False))


if __name__=="__main__":
    import sys
    audit(sys.argv[1])
