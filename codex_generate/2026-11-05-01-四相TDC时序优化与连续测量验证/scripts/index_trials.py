"""汇总实际保存的物理试验，不用控制台估计值代替最终报告。"""
from pathlib import Path
import hashlib
import analyze_results as a
import experiment as e

ROOT=Path(__file__).resolve().parents[1]

def main():
    rows=[]
    provenance=(ROOT/'results/optimized/baseline/SOURCE_PROVENANCE.json').read_text(encoding='utf-8')
    rtl_sha=hashlib.sha256((ROOT/'inputs/optimized_rtl_sha256.json').read_bytes()).hexdigest()
    notes={
        'baseline_initial':'首轮最终61份导出证据完整；部分原生中间报告被reset_run清理，见EVIDENCE_LIMITATIONS.md',
        'baseline_bram_routing_incomplete':'tns_cleanup选项不适用于本器件/组合，失败日志保留',
        'baseline_bram_routing':'路由后bram_power_opt被工具跳过；Setup与BRAM最小周期仍失败',
        'baseline_power_replicated':'实际源为baseline_initial/design.dcp；原build_metadata旧source描述见最终SOURCE_PROVENANCE更正',
        'baseline_power_aggressive':'对已路由DCP的AggressiveExplore及AlternateReplication未进一步改善',
        'baseline_ila_cluster':'局部54 Slice不足实际61 Slice；UTLZ-3警告，未选作最终版本',
        'baseline_ila_cluster_relaxed':'区域放宽为80 Slice，容量告警消除；最终选定Baseline'}
    notes['baseline_incremental_timing_closure']='仅TNS小幅改善，WNS仍负；未替换已有独立校准的主Baseline'
    notes['compensated_incremental_timing_closure']='最终导出与原参考关键路径/裕量一致，未选用；日志中瞬态较好估计不作为最终结果'
    folders=[p for p in (ROOT/'results/trials').iterdir() if p.is_dir()]
    folders.append(ROOT/'results/optimized/compensated')
    for folder in folders:
        timing=a.timing(folder) if (folder/'timing_summary.rpt').exists() and (folder/'check_timing.rpt').exists() else None
        resources=a.utilization(folder)
        row=dict(trial=folder.name,directory=folder.relative_to(ROOT).as_posix(),status='ROUTED_EXPORTED' if (folder/'design.dcp').exists() else 'INCOMPLETE_OR_TOOL_FAILURE',
            selected_final=folder.name=='baseline_ila_cluster_relaxed' or folder==ROOT/'results/optimized/compensated',
            rtl_version_manifest_sha256=rtl_sha,bit_files=';'.join(p.name for p in folder.glob('*.bit')),notes=notes.get(folder.name,'独立补偿参数综合与实现，实际配置见build_metadata及parameters_used.tcl'))
        for key in ['wns_ns','tns_ns','whs_ns','ths_ns','wpws_ns','setup_failing','hold_failing','pulse_width_failing']:row[key]=timing[key] if timing else 'NOT_AVAILABLE'
        for key in ['Slice LUTs','Slice Registers','Block RAM Tile','CARRY4']:row[key]=resources.get(key,'NOT_AVAILABLE') if resources else 'NOT_AVAILABLE'
        row['actual_export_metadata']=(folder/'build_metadata.txt').read_text(errors='replace').replace('\n',';') if (folder/'build_metadata.txt').exists() else 'NOT_AVAILABLE'
        row['actual_effective_recipe_reference']='results/optimized/compensated/SOURCE_PROVENANCE.json' if folder.name=='compensated' else '本行metadata及对应执行日志；请求策略与自动覆盖需按日志区分'
        rows.append(row)
    e.write_csv(ROOT/'PHYSICAL_TRIALS.csv',rows)
    print('实际物理试验',len(rows))

if __name__=='__main__':main()
