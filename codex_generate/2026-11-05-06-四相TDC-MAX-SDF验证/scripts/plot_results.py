"""按science-plotting规范画全部原始误差，不平滑、不删除离群点。"""
import os
os.environ['MPLCONFIGDIR']='Z:/build/mpl_cache'
from pathlib import Path
import csv,json,math
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path('Z:/')
def read(p):
    with p.open(encoding='utf-8-sig',newline='') as f:return list(csv.DictReader(f))
def write(p,rows):
    with p.open('w',encoding='utf-8-sig',newline='') as f:
        w=csv.DictWriter(f,fieldnames=list(rows[0]));w.writeheader();w.writerows(rows)
def save(fig,name):
    fig.savefig(ROOT/'plots'/(name+'.svg'),bbox_inches='tight')
    fig.savefig(ROOT/'plots'/(name+'.png'),dpi=360,bbox_inches='tight');plt.close(fig)
def main():
    s=json.loads((ROOT/'results/ERROR_STATISTICS.json').read_text(encoding='utf-8'));assert s['precision_complete']
    edges=read(ROOT/'results/EDGE_RESULTS.csv');pulses=read(ROOT/'results/PULSE_RESULTS.csv');assert all(r['status']=='MATCHED' for r in edges+pulses)
    colors=['#5A76A8','#C96A6A','#4FA38F']
    plt.rcParams.update({'font.family':'serif','font.serif':['STIXGeneral','DejaVu Serif'],'font.size':10,'axes.labelsize':11,'xtick.labelsize':9,'ytick.labelsize':9,'axes.linewidth':0.8,'legend.fontsize':9,'legend.frameon':False,'svg.fonttype':'none','axes.grid':False,'xtick.direction':'in','ytick.direction':'in'})
    fig,axes=plt.subplots(1,2,figsize=(7.0,3.0),sharey=True,layout='constrained')
    allvalues=[];names=['Rise','Fall','Pulse width'];data=[]
    for ax,pol,color,label in zip(axes,[1,0],colors[:2],names[:2]):
        rows=[r for r in edges if int(r['polarity'])==pol];ids=np.array([int(r['event_id']) for r in rows]);values=np.array([float(r['error_ps']) for r in rows]);allvalues.extend(values);data.append(values)
        ax.scatter(ids,values,s=3.0,color=color,alpha=0.65,linewidths=0,label=label)
        ax.axhline(0,color='#222222',ls='--',lw=0.8);ax.set_xlabel('Event ID');ax.set_xlim(-40,3550);ax.set_xticks([0,1000,2000,3000]);ax.legend(loc='upper left',bbox_to_anchor=(0,1.17))
    axes[0].set_ylabel('Timestamp error (ps)');axes[0].set_ylim(min(allvalues)-15,max(allvalues)+15);save(fig,'timestamp_error')
    width=np.array([float(r['error_ps']) for r in pulses]);ids=np.array([int(r['event_id']) for r in pulses]);data.append(width)
    fig,ax=plt.subplots(figsize=(7.0,3.0),layout='constrained');ax.scatter(ids,width,s=4,color=colors[2],alpha=0.72,linewidths=0)
    ax.axhline(0,color='#222222',ls='--',lw=0.8);ax.set_xlabel('Event ID');ax.set_ylabel('Pulse-width error (ps)');ax.set_xlim(-40,3550);ax.set_xticks([0,500,1000,1500,2000,2500,3000,3500]);ax.set_ylim(min(width)-15,max(width)+15);save(fig,'pulse_width_error')
    lower=20*math.floor(min(min(v) for v in data)/20);upper=20*math.ceil(max(max(v) for v in data)/20);bins=np.arange(lower,upper+20,20)
    fig,axes=plt.subplots(1,3,figsize=(9.0,3.0),sharex=True,layout='constrained');hist=[]
    for ax,v,color,label in zip(axes,data,colors,names):
        counts,edges_=np.histogram(v,bins=bins);assert int(counts.sum())==3512
        ax.hist(v,bins=bins,color=color,alpha=0.65,edgecolor=color,linewidth=0.7)
        ax.axvline(0,color='#222222',ls='--',lw=0.8);ax.axvline(np.mean(v),color=color,lw=1.2,label=f'{label}\nBias {np.mean(v):.2f} ps')
        ax.set_xlabel('Error (ps)');ax.set_ylabel('Count');ax.legend(loc='upper left',bbox_to_anchor=(0,1.24));ax.set_xlim(lower,upper)
        hist.extend(dict(series=label,bin_left_ps=float(a),bin_right_ps=float(b),count=int(n)) for a,b,n in zip(edges_[:-1],edges_[1:],counts))
    save(fig,'error_histogram');write(ROOT/'results/ERROR_HISTOGRAM_DATA.csv',hist)
    metadata=dict(timestamp_x='EDGE_RESULTS.csv event_id',timestamp_y='EDGE_RESULTS.csv error_ps',timestamp_group='polarity 1=rise,0=fall',width_x='PULSE_RESULTS.csv event_id',width_y='PULSE_RESULTS.csv error_ps',units='ps',rows_per_series=3512,smoothing=False,outlier_removal=False,histogram_bin_width_ps=20,formats=['SVG vector','PNG 360dpi'],palette='science-muted',visual_QA='pending visual inspection')
    (ROOT/'plots/PLOT_METADATA.json').write_text(json.dumps(metadata,ensure_ascii=False,indent=2),encoding='utf-8');print('PLOTS_CREATED 3 SVG + 3 PNG; all 3512 points/series preserved')
if __name__=='__main__':main()
