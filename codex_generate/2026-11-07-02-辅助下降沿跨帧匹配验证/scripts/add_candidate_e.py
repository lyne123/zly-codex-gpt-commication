"""按实际路径压力引出的共同匹配问题增加无状态回退候选；不修改正式代码。"""
from pathlib import Path
import shutil
TASK=Path(__file__).resolve().parents[1];ROOT=TASK.parents[1]
text=(TASK/'original/rtl/tdc_fine_layer.v').read_text(encoding='utf-8')
start=text.index('        assign aux_rise_match[0] = rise_now[0]')
end=text.index('`ifndef SYNTHESIS',start)
block=text[start:end].replace('assign aux_rise_match','assign base_rise_match').replace('assign aux_fall_match','assign base_fall_match')
block='''        wire [3:0] base_rise_match, base_fall_match;
'''+block+'''
        // 保持原确认优先；仅在整帧无原有效候选时考虑前帧回退。
        wire base_confirmed =
            (pack0_d1[9] && (pack0_d1[8] ? base_rise_match[3] : base_fall_match[3])) ||
            (pack270_to90[9] && (pack270_to90[8] ? base_rise_match[2] : base_fall_match[2])) ||
            (pack180_d1[9] && (pack180_d1[8] ? base_rise_match[1] : base_fall_match[1])) ||
            (pack90_d2[9] && (pack90_d2[8] ? base_rise_match[0] : base_fall_match[0]));
        wire raw_has_rise = pack0_d1[9:8]==2'b11 || pack270_to90[9:8]==2'b11 ||
                            pack180_d1[9:8]==2'b11 || pack90_d2[9:8]==2'b11;
        wire raw_has_fall = pack0_d1[9:8]==2'b10 || pack270_to90[9:8]==2'b10 ||
                            pack180_d1[9:8]==2'b10 || pack90_d2[9:8]==2'b10;
        // 多事件或混合极性时不推测归属；previous已按原claimed规则扣除使用过的事件。
        wire rise_previous_single = (|rise_previous) && ((rise_previous & (rise_previous-4'b0001))==0);
        wire fall_previous_single = (|fall_previous) && ((fall_previous & (fall_previous-4'b0001))==0);
        wire rise_fallback = !base_confirmed && raw_has_rise && !raw_has_fall && rise_previous_single;
        wire fall_fallback = !base_confirmed && raw_has_fall && !raw_has_rise && fall_previous_single;
        assign aux_rise_match = base_rise_match | {4{rise_fallback}};
        assign aux_fall_match = base_fall_match | {4{fall_fallback}};
'''
text=text[:start]+block+text[end:]
dst=TASK/'variants/E_guarded';assert not dst.exists()
shutil.copytree(TASK/'original/rtl',dst);(dst/'tdc_fine_layer.v').write_text(text,encoding='utf-8')
shutil.copytree(dst,ROOT/'codex_generate/.vivado_work/tdc_auxfall_20261107_02/E_guarded')
print('E_GUARDED_PREPARED; original confirmations preserved; formal RTL unchanged')
