"""七类图全部来自真实仿真测量CSV；缺少结果时直接报错。"""
from collections import Counter, defaultdict
import math
import statistics
import os
from experiment import ROOT, read_csv
os.environ.setdefault("MPLCONFIGDIR",str(ROOT/"build/mplconfig"))
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

OUT=ROOT/"results/figures"
OUT.mkdir(exist_ok=True)
COLORS={"baseline":"#0072B2","compensated":"#D55E00"}
plt.rcParams.update({"font.family":"DejaVu Sans","font.size":9,"axes.spines.top":False,
    "axes.spines.right":False,"savefig.dpi":300,"pdf.fonttype":42,"svg.fonttype":"none"})


def save(fig,name):
    fig.tight_layout()
    for suffix in ("png","svg","pdf"):
        fig.savefig(OUT/f"{name}.{suffix}",bbox_inches="tight")
    plt.close(fig)


def plot():
    params=read_csv(ROOT/"results/tdc_skew_calibration.csv")
    measurements={v:read_csv(ROOT/"results"/v/"gate_validation/measurements.csv") for v in COLORS}
    metrics=read_csv(ROOT/"results/comparison_metrics.csv")
    for polarity in ("rise","fall"):
        rows=sorted((r for r in params if r["polarity"]==polarity),key=lambda r:int(r["tdl_phase"]))
        fig,axes=plt.subplots(1,2,figsize=(7.1,3.3))
        x=list(range(4))
        absolute=[float(r["offset_ps"]) for r in rows]
        for ax,values,title in zip(axes,(absolute,[v-absolute[0] for v in absolute]),("Absolute correction","Relative to next 0 deg")):
            ax.bar(x,values,color=COLORS["baseline"])
            ax.set(xticks=x,xticklabels=[r["tdl_phase"]+" deg\nn="+r["n"] for r in rows],ylabel="Offset (ps)",title=f"{polarity.capitalize()}: {title}")
            ax.axhline(0,color="black",lw=.7); ax.margins(y=.18)
            for i,value in enumerate(values): ax.annotate(f"{value:.0f}",(i,value),xytext=(0,4 if value>=0 else -12),textcoords="offset points",ha="center",fontsize=7)
        save(fig,f"offset_{polarity}")
    fig,ax=plt.subplots(figsize=(5.3,3.5))
    values={v:[float(r["error_ps"]) for r in rows if int(r["matched"]) and int(r["bank"])<0] for v,rows in measurements.items()}
    low=min(min(v) for v in values.values()); high=max(max(v) for v in values.values())
    if high==low: high=low+1
    bins=[low+(high-low)*i/40 for i in range(41)]
    for v in COLORS: ax.hist(values[v],bins=bins,histtype="step",lw=1.5,label=f"{v}, n={len(values[v])}",color=COLORS[v])
    ax.set(xlabel="Width error (ps)",ylabel="Count",title="Fixed-width tests; all matched outputs")
    ax.legend(frameon=False)
    save(fig,"fixed_error_histogram")
    fig,ax=plt.subplots(figsize=(5.3,3.5))
    for variant,rows in measurements.items():
        groups=defaultdict(list)
        for r in rows:
            if r["case"]=="fixed_25300" and int(r["matched"]): groups[int(r["clock_relative_phase_ps"])].append(float(r["error_ps"]))
        x=sorted(groups)
        ax.plot(x,[statistics.mean(groups[p]) for p in x],".-",ms=3,lw=1,color=COLORS[variant],label=variant)
    ax.set(xlabel="Input rise phase (ps)",ylabel="Mean width error (ps)",title="25.3 ns; independent validation phases")
    ax.axhline(0,color="black",lw=.6); ax.legend(frameon=False)
    save(fig,"error_vs_phase")
    truth=read_csv(ROOT/"sim/stimuli/validation_truth.csv")
    fig,axes=plt.subplots(2,1,figsize=(7.2,6.2))
    for ax,case in zip(axes,("ATC_10MHz","ATC_20MHz")):
        data=[r for r in truth if r["case"]==case]
        ids=[int(r["pulse_id"]) for r in data]
        positions={event:i for i,event in enumerate(ids)}
        ax.plot(range(len(ids)),[float(r["true_width_ps"]) for r in data],color="black",lw=1.2,label="true edges")
        notes=[]
        for variant,rows in measurements.items():
            actual=[r for r in rows if r["case"]==case]
            by_id={int(r["pulse_id"]):float(r["measured_width_ps"]) for r in actual if int(r["matched"])}
            ax.plot(range(len(ids)),[by_id.get(i,math.nan) for i in ids],lw=.7,alpha=.85,label=variant,color=COLORS[variant])
            wrong=[r for r in actual if not int(r["matched"])]
            ax.scatter([positions[int(r["pulse_id"])] for r in wrong],[float(r["measured_width_ps"]) for r in wrong],marker="x",s=35,color=COLORS[variant],zorder=5)
            missing=[r for r in data if int(r["pulse_id"]) not in by_id]
            ax.scatter([positions[int(r["pulse_id"])] for r in missing],[float(r["true_width_ps"]) for r in missing],facecolors="none",edgecolors=COLORS[variant],s=30,zorder=4)
            notes.append(f"{variant}: {len(by_id)}/{len(data)} correct")
        ax.set(xlabel="Frame cell index (headers included)",ylabel="Pulse width (ps)",title=f"Provisional ATC/SPWM, {case.split('_')[1]} carrier")
        ax.margins(y=.18); ax.set_ylim(bottom=0)
        ax.legend(frameon=False,ncol=3,fontsize=7,loc="upper right")
        ax.text(.01,.98,"; ".join(notes),transform=ax.transAxes,va="top",fontsize=7)
    fig.text(.5,.003,"x: mispaired raw output; open circle: no correct output. All anomalies are retained in CSV.",ha="center",fontsize=7)
    save(fig,"spwm_widths")
    all_metrics=next(r for r in metrics if r["test"]=="all")
    fig,ax=plt.subplots(figsize=(5,3.5))
    for i,variant in enumerate(COLORS):
        ax.bar([x+(i-.5)*.35 for x in range(3)],[float(all_metrics[f"{variant}_{m}_ps"]) for m in ("rmse","bias","std")],width=.35,color=COLORS[variant],label=variant)
    ax.set(xticks=range(3),xticklabels=["RMSE","Bias","STD"],ylabel="Width error (ps)",title="Conditional metrics; frame test incomplete")
    ax.axhline(0,color="black",lw=.6); ax.legend(frameon=False)
    save(fig,"rmse_bias_std")
    fig,ax=plt.subplots(figsize=(5,3.5))
    for i,variant in enumerate(COLORS):
        timestamps=read_csv(ROOT/"results"/variant/"gate_validation/associated_timestamps.csv")
        counts=Counter(int(r["index"]) for r in timestamps)
        ax.bar([x+(i-.5)*.35 for x in range(4)],[100*counts[x]/len(timestamps) for x in range(4)],width=.35,color=COLORS[variant],label=variant)
    ax.set(xticks=range(4),xticklabels=["90 deg","180 deg","270 deg","next 0 deg"],ylabel="Selected edges (%)",title="Actual candidate selection")
    ax.legend(frameon=False)
    save(fig,"selection_ratios")
    print("Generated seven figures from simulation CSV:",OUT)


if __name__=="__main__": plot()
