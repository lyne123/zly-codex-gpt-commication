"""读取Vivado原始ILA CSV，只把valid=1且数值可读的脉宽计为测量；不做离群值筛选。"""
from pathlib import Path
import csv, hashlib, json

ROOT=Path(__file__).resolve().parents[1]
MODULO_PS=2048000

def digest(path):
    with Path(path).open('rb') as stream:return hashlib.file_digest(stream,'sha256').hexdigest()

def number(text, radix):
    text=text.strip().replace('_','')
    if not text or any(c in text.lower() for c in 'xz?'):return None
    radix=radix.upper()
    base=16 if 'HEX' in radix else 2 if 'BIN' in radix else 10
    return int(text,base)

def read_capture(path):
    with Path(path).open(encoding='utf-8-sig',newline='') as stream:
        reader=csv.reader(stream);header=[name.strip() for name in next(reader)];radix=next(reader)
        if len(radix)!=len(header) or not radix[0].startswith('Radix'):raise ValueError('缺少Vivado Radix行')
        def column(prefix):
            matches=[i for i,name in enumerate(header) if name==prefix or name.startswith(prefix+'[')]
            if len(matches)!=1:raise ValueError('探针列不唯一或缺失：'+prefix)
            return matches[0]
        vi=column('pulse_width_valid_100m');wi=column('pulse_width_ps_100m')
        ei=column('error_valid_100m') if any(n.startswith('error_valid_100m') for n in header) else None
        ci=column('error_code_100m') if ei is not None else None
        counts=dict(buffer_rows=0,valid_measurements=0,idle_cycles=0,invalid_width_events=0,unknown_valid_cycles=0,error_events=0,error_unknown_cycles=0)
        samples=[];invalid=[];errors=[]
        for index,row in enumerate(reader):
            if not row:continue
            if len(row)!=len(header):raise ValueError(f'CSV列数错误：{path}:{index+3}')
            source_index=number(row[0],radix[0])
            if source_index!=index:raise ValueError('ILA采样下标不连续')
            counts['buffer_rows']+=1
            try:valid=number(row[vi],radix[vi])
            except ValueError:valid=None
            if valid==0:counts['idle_cycles']+=1
            elif valid==1:
                try:width=number(row[wi],radix[wi])
                except ValueError:width=None
                if width is None or not 0<=width<MODULO_PS:
                    counts['invalid_width_events']+=1;invalid.append(dict(buffer_sample_idx=index,reason='valid1_width_unknown_or_out_of_modulo',raw_width=row[wi]))
                else:
                    counts['valid_measurements']+=1;samples.append(dict(buffer_sample_idx=index,pulse_width_ps=width))
            else:
                counts['unknown_valid_cycles']+=1;invalid.append(dict(buffer_sample_idx=index,reason='unknown_valid_flag',raw_width=row[wi]))
            if ei is not None:
                try:error_valid=number(row[ei],radix[ei])
                except ValueError:error_valid=None
                if error_valid==1:
                    try:code=number(row[ci],radix[ci])
                    except ValueError:code=None
                    counts['error_events']+=1;errors.append(dict(buffer_sample_idx=index,error_code='' if code is None else code))
                elif error_valid not in (0,1):counts['error_unknown_cycles']+=1
        return dict(header=header,counts=counts,samples=samples,invalid=invalid,errors=errors,error_stream_available=ei is not None)

def write_csv(path, fields, rows):
    path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
    temporary=path.with_suffix(path.suffix+'.tmp')
    with temporary.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields);writer.writeheader();writer.writerows(rows)
    temporary.replace(path)

def process_point(folder):
    """原始capture不改写；派生表可重建，续采依靠原始文件下标，不按数值去重。"""
    folder=Path(folder);meta=json.loads((folder/'point.json').read_text(encoding='utf-8'))
    samples=[];invalid=[];errors=[];captures=[];totals={};missing_errors=False
    for path in sorted(path for path in folder.glob('batch_*.csv') if path.stem.removeprefix('batch_').isdigit()):
        parsed=read_capture(path);capture=path.stem
        captures.append(dict(capture_id=capture,sha256=digest(path),**parsed['counts']))
        for key,value in parsed['counts'].items():totals[key]=totals.get(key,0)+value
        missing_errors |= not parsed['error_stream_available']
        for row in parsed['samples']:
            index=len(samples);width=row['pulse_width_ps'];state=meta['state']
            samples.append(dict(sample_idx=index,capture_id=capture,buffer_sample_idx=row['buffer_sample_idx'],
                set_pw_ps=meta['set_pw_ps'],ref_pw_ps='' if meta['ref_pw_ps'] is None else meta['ref_pw_ps'],
                compensation_state=state,pulse_width_ps=width,pulse_width_raw=width if state=='off' else '',
                pulse_width_corrected=width if state=='on' else '',pulse_width_valid=1,error_flags='',
                error_association='independent_error_stream_no_per_pulse_tag',include_in_primary_statistics=int(index<meta['target_valid'])))
        invalid.extend(dict(capture_id=capture,**row) for row in parsed['invalid'])
        errors.extend(dict(capture_id=capture,**row) for row in parsed['errors'])
    if captures:
        output=ROOT/'data'/('compensation_'+meta['state'])/(f"pw_{meta['set_pw_ps']}_{meta['kind']}.csv")
        write_csv(output,list(samples[0]) if samples else ['sample_idx','capture_id','buffer_sample_idx','set_pw_ps','ref_pw_ps','compensation_state','pulse_width_ps','pulse_width_raw','pulse_width_corrected','pulse_width_valid','error_flags','error_association','include_in_primary_statistics'],samples)
        write_csv(folder/'invalid_records.csv',['capture_id','buffer_sample_idx','reason','raw_width'],invalid)
        write_csv(folder/'error_events.csv',['capture_id','buffer_sample_idx','error_code'],errors)
    report=dict(**totals,actual_valid=len(samples),primary_valid=min(len(samples),meta['target_valid']),
        extra_valid_preserved=max(0,len(samples)-meta['target_valid']),target_valid=meta['target_valid'],
        complete=len(samples)>=meta['target_valid'],captures=captures,error_stream_missing=missing_errors,
        per_pulse_error_association_available=False,FIFO_overflow_observable=False,
        inter_capture_input_events_unobserved=True,raw_timestamps_collected=False,TDL_IDs_collected=False,
        incomplete_raw_files=[str(path) for path in folder.glob('batch_*.partial.csv')],
        selection_rule='first target_valid valid results in acquisition order; all extra/raw/invalid retained; incomplete exports retained but not counted; no outlier removal')
    (folder/'capture_summary.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    return report
