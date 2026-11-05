"""从实测只读日志提取六事件证据，不计算或修改补偿参数。"""
from pathlib import Path
import csv
import json

ROOT=Path(__file__).resolve().parents[1]

def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))

def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)

def main():
    if not json.loads((ROOT/'results/SHORT_WINDOW_EQUIVALENCE.json').read_text())['pass_all_fields']:
        raise SystemExit('等价性未通过，停止形成根因结论。')
    case=ROOT/'results/short_baseline'
    samples=read(case/'frontend_signals.csv');changes=read(case/'signal_changes.csv');captures=read(case/'aux_capture.csv')
    pulses={int(r['event_id']):r for r in read(ROOT/'inputs/EDGE_TIME_MAPPING.csv')}
    def before(t):return max((r for r in samples if int(r['time_ps'])<=t),key=lambda r:int(r['time_ps']))
    def after(t):return min((r for r in samples if int(r['time_ps'])>t+100),key=lambda r:int(r['time_ps']))
    evidence=[];diagnoses=[];gates=[];aux_rows=[]
    for falling,rising in [(2917,2918),(2983,2984),(3049,3050)]:
        fall=int(pulses[falling]['fall_absolute_ps']);rise=int(pulses[rising]['rise_absolute_ps'])
        # 实际输入引脚及有效延迟输入的低脉冲边界必须一致，不能只用顶层 PWM 推断。
        low=next(int(r['time_ps']) for r in changes if r['signal']=='pwm_meta_D' and r['value_hex']=='0' and fall<int(r['time_ps'])<fall+4000)
        high=next(int(r['time_ps']) for r in changes if r['signal']=='pwm_meta_D' and r['value_hex']=='1' and low<int(r['time_ps'])<low+3000)
        effective=[(int(r['time_ps']),r['value_hex']) for r in changes if r['signal']=='pwm_meta_D_dly' and low<=int(r['time_ps'])<=high]
        assert effective==[(low,'0'),(high,'1')],effective
        meta=[r for r in captures if r['stage']=='pwm_meta']
        prev=max((r for r in meta if int(r['time_ps'])<low),key=lambda r:int(r['time_ps']))
        nxt=min((r for r in meta if int(r['time_ps'])>high),key=lambda r:int(r['time_ps']))
        inside=[r for r in meta if low<=int(r['time_ps'])<=high]
        assert not inside and prev['effective_D']==nxt['effective_D']==prev['Q_before']==nxt['Q_before']=='1'
        assert high-low==rise-fall
        aux_rows.append(dict(events=f'{falling};{rising}',fall_input_ps=fall,rise_input_ps=rise,low_width_ps=high-low,D_low_start_ps=low,D_low_end_ps=high,previous_C_rise_ps=prev['time_ps'],next_C_rise_ps=nxt['time_ps'],samples_inside_low=len(inside),previous_D=prev['effective_D'],next_D=nxt['effective_D'],Q_before_previous=prev['Q_before'],Q_before_next=nxt['Q_before'],input_to_D_delay_ps=low-fall))
        for event,pol,edge in [(falling,2,fall),(rising,3,rise)]:
            candidates=[]
            for phase in [0,90,180,270]:
                found=[r for r in changes if r['signal']==f'p{phase}_edge_type_q' and r['value_hex']==str(pol) and edge+14000<=int(r['time_ps'])<=edge+17500]
                for transition in found:
                    t=int(transition['time_ps']);pre=before(t);post=after(t)
                    thermo=before(t-11000);detected=before(t-9500)
                    code=int(post[f'p{phase}_code_q']);thermal=thermo[f'p{phase}_thermo'];count=int(thermal,16).bit_count()
                    assert count==code,(event,phase,thermal,count,code)
                    assert int(pre[f'p{phase}_raw_edge_type'])==pol
                    assert int(pre[f'p{phase}_code_raw'])==code
                    assert pre[f'p{phase}_code_in_range']==pre[f'p{phase}_encoder_ready']==post[f'p{phase}_output_ready']=='1'
                    assert int(detected[f'p{phase}_detected_type'])==pol,(event,phase,detected)
                    item=dict(event_id=event,polarity='F' if pol==2 else 'R',input_edge_ps=edge,phase=phase,
                              thermo_observed_ps=thermo['time_ps'],thermo_hex=thermal,popcount=count,
                              detected_observed_ps=detected['time_ps'],detected_type=detected[f'p{phase}_detected_type'],
                              encoder_input_observed_ps=pre['time_ps'],code_raw=pre[f'p{phase}_code_raw'],raw_edge_type=pre[f'p{phase}_raw_edge_type'],code_in_range_reconstructed=pre[f'p{phase}_code_in_range'],encoder_ready=pre[f'p{phase}_encoder_ready'],
                              edge_type_q_change_ps=t,output_observed_ps=post['time_ps'],edge_type_q=pol,code_q=code,output_ready=post[f'p{phase}_output_ready'])
                    evidence.append(item);candidates.append(item)
            assert len(candidates)==(2 if pol==2 else 1),(event,candidates)
            base=(edge//100000)*100000
            gate=before(base+(32500 if pol==2 else 34500))
            # 在实际确认寄存器输入处检查；不把重建的 match 当作独立物理节点。
            for c in candidates:
                phase=c['phase'];packname={0:'pack0_d1',90:'pack90_d2',180:'pack180_d1',270:'pack270_to90'}[phase]
                pack=int(gate[packname],16)
                assert (pack>>8)==pol and (pack&255)==c['code_q'],(event,phase,gate)
                assert gate[f'final_type{phase}']=='0' and gate['frame_ready']=='1'
                assert gate['aux_'+('fall' if pol==2 else 'rise')+'_match']=='0'
                gates.append(dict(event_id=event,phase=phase,observed_ps=gate['time_ps'],pack_signal=packname,pack_hex=gate[packname],pack_type=pack>>8,pack_code=pack&255,aux_rise_pipe=gate['aux_rise_pipe'],aux_fall_pipe=gate['aux_fall_pipe'],aux_match=0,frame_ready=gate['frame_ready'],actual_final_FF_D_type=gate[f'final_type{phase}']))
            descriptions='；'.join(f"{c['phase']}° type={pol}, code={c['code_q']} @ {c['edge_type_q_change_ps']} ps" for c in candidates)
            diagnoses.append({'事件ID':event,'极性':'下降沿' if pol==2 else '上升沿','真实边沿时间_ps':edge,
                              'TDL原始采样':'；'.join(f"{c['phase']}° 0x{c['thermo_hex']}，计1={c['popcount']}" for c in candidates),
                              '编码结果':descriptions+'；ready=1，输入范围有效',
                              '辅助检测':f"D低电平[{low},{high}) ps内无采样上升沿；pwm_meta保持1，未产生本事件aux_{'fall' if pol==2 else 'rise'}",
                              '最终确认':f"{gate['time_ps']} ps：包内候选仍正确，match=0，实际final_type=0；原始帧无本事件",
                              '首次异常位置':f"pwm_meta_reg：D/D_dly低脉冲[{low},{high}) ps在两次C上升沿之间漏采；{high} ps脉冲结束即可确定未采到；下一C={nxt['time_ps']} ps时D/Q_before仍为1（此前C={prev['time_ps']} ps）",
                              'D低脉冲开始_ps':low,'D低脉冲结束_ps':high,'最早确定完整脉冲漏采时间_ps':high,'漏采后首个采样时间_ps':nxt['time_ps'],'确认过滤观测时间_ps':gate['time_ps'],
                              '新增流水线是否首因':'否，输入同步漏采发生在编码器输出新增级之前','结论':'已确认：辅助同步器漏采及确认门控过滤'})
    write(ROOT/'results/AUX_SAMPLING_EVIDENCE.csv',aux_rows)
    write(ROOT/'results/TDL_CANDIDATE_EVIDENCE.csv',evidence)
    write(ROOT/'results/CONFIRM_GATE_EVIDENCE.csv',gates)
    write(ROOT/'EVENT_DIAGNOSIS.csv',diagnoses)
    print(json.dumps(dict(events=len(diagnoses),valid_tdl_candidates=len(evidence),all_aux_low_pulses_missed=True,all_candidates_filtered_at_confirm=True),ensure_ascii=False,indent=2))

if __name__=='__main__':main()
