"""冻结真实CSV及正式Baseline，建立四个独立验证副本；暂不修改正式RTL。"""
from pathlib import Path
import hashlib,json,shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
PREV=ROOT/'codex_generate/2026-11-07-01-上板边沿配对错误ILA定位'
WORK=ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02'
def sha(p):
    with p.open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
def main():
    assert not (TASK/'inputs/SOURCE.json').exists(),'禁止覆盖冻结输入'
    for folder in ['inputs','original/rtl','variants','sim','scripts','results','logs']:(TASK/folder).mkdir(parents=True,exist_ok=True)
    WORK.mkdir(parents=True,exist_ok=True)
    manifest=json.loads((PREV/'inputs/SOURCE.json').read_text(encoding='utf-8'))
    for name,digest in manifest['formal_RTL_sha256'].items():
        src=ROOT/'fpga_tdc_v3_cal_rtl'/name;assert sha(src)==digest,name
        shutil.copy2(src,TASK/'original/rtl'/name)
    csv=PREV/'results/hardware_debug_04/TRIGGER_A.csv'
    assert sha(csv)=='0bfb3038261c9d01d31253d1e445fad8d22bfd88caa34449da21e78b0dce3bca'
    shutil.copy2(csv,TASK/'inputs/TRIGGER_A.csv')
    for name in ['compensation_params.tcl','frozen_compensation.csv','combine_AD23.xdc']:
        shutil.copy2(PREV/'inputs'/name,TASK/'inputs'/name)
    old=ROOT/'codex_generate/2026-11-05-05-四相TDC核心时序优化'
    for name in ['functional_models.v','compensation_parameters.vh']:
        shutil.copy2(old/'sim'/name,TASK/'sim'/name)
    source=(TASK/'original/rtl/tdc_fine_layer.v').read_text(encoding='utf-8')
    marker='        assign aux_fall_match[3] = |fall_now;';assert source.count(marker)==1
    changes={
      'A_baseline':source,
      'B_previous':source.replace(marker,'        assign aux_fall_match[3] = (|fall_now) | fall_previous[3];'),
      'C_delay_fall':source.replace('        wire [3:0] fall_now = fall_history[ALIGN_CYCLES];',
          '''        // 仅实验副本：下降事件整体延迟一拍，上升通路不动。
        reg [3:0] fall_delayed_previous;
        always @(posedge clk_500m or negedge rst_n_0)
            if (!rst_n_0) fall_delayed_previous <= 0;
            else fall_delayed_previous <= fall_history[ALIGN_CYCLES+1];
        wire [3:0] fall_now = fall_history[ALIGN_CYCLES+1];''').replace(
          'wire [3:0] fall_previous = fall_history[ALIGN_CYCLES+1] & ~fall_claimed_previous;',
          'wire [3:0] fall_previous = fall_delayed_previous & ~fall_claimed_previous;'),
      'D_fallback':source.replace(marker,'''        // 仅在其余三相都没有候选时，允许0°使用尚未归属的前帧slot3。
        // 已有可用帧保持原确认结果，不改变候选选择或claimed状态更新。
        wire fall0_previous_fallback = fall_previous[3] &&
            !pack90_d2[9] && !pack180_d1[9] && !pack270_to90[9];
        assign aux_fall_match[3] = (|fall_now) | fall0_previous_fallback;''')}
    for variant,text in changes.items():
        dst=TASK/'variants'/variant;shutil.copytree(TASK/'original/rtl',dst)
        (dst/'tdc_fine_layer.v').write_text(text,encoding='utf-8')
        shutil.copytree(dst,WORK/variant)
    shutil.copytree(TASK/'sim',WORK/'sim',dirs_exist_ok=True)
    record=dict(analysis_commit='2e9cf594aed51c67d48c090fdea9b92125f7822b',
        formal_source_commit=manifest['source_commit'],formal_RTL_sha256=manifest['formal_RTL_sha256'],
        real_CSV_sha256=sha(csv),work=str(WORK),formal_RTL_modified=False,
        parameters_recalculated=False,real_csv_sample728='aux_fall_slots=1000; fall_previous=0000')
    (TASK/'inputs/SOURCE.json').write_text(json.dumps(record,ensure_ascii=False,indent=2),encoding='utf-8')
    with (ROOT/'codex_generate/README.md').open('a',encoding='utf-8') as f:
        f.write('\n2026-11-07-02：[辅助下降沿跨帧匹配验证](2026-11-07-02-辅助下降沿跨帧匹配验证/README.md)。\n')
    print('INPUTS_FROZEN; variants A/B/C/D prepared; formal RTL unchanged')
if __name__=='__main__':main()
