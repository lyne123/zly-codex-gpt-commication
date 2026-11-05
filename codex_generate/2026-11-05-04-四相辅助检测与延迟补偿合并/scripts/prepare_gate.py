"""复用上轮只读SDF观察及统计方法，直接执行同一完整3512激励。"""
from pathlib import Path

ROOT=Path('W:/');PREV=Path('X:/')
def main():
    text=(PREV/'scripts/run_gate.py').read_text(encoding='utf-8')
    text=text.replace('仅运行新Baseline的局部及一次完整MAX-SDF','运行新Compensated完整MAX-SDF').replace("ROOT/'results/baseline'","ROOT/'results/compensated'")
    text=text.replace('variant=baseline','variant=compensated')
    text=text.replace("s=json.loads((parent/'gate_local/VALIDATION.json').read_text())\n        assert s['functional_pass'] and s['annotation_success'],'局部SDF未通过，禁止运行完整激励'", "s=json.loads((ROOT/'results/TIMING_REVIEW.json').read_text())\n        assert s['main_static_pass'],'核心静态时序未通过，停止后续依赖步骤'")
    (ROOT/'scripts/run_gate.py').write_text(text,encoding='utf-8')
    text=(PREV/'scripts/analyze_gate.py').read_text(encoding='utf-8').replace("ROOT/'results/baseline'","ROOT/'results/compensated'")
    (ROOT/'scripts/analyze_gate.py').write_text(text,encoding='utf-8')
    # 时序审查脚本独立保留，包含模块from/to边界；不再用旧的单向版本覆盖。
    print('SDF_AND_TIMING_SCRIPTS_PREPARED')

if __name__=='__main__':main()
