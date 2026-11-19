"""Plot saved native development data; no simulations, fitting or final tests.

Authorship: external report preparation. Data provenance is recorded per figure.
"""
from __future__ import annotations
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
from matplotlib.ticker import FixedLocator, ScalarFormatter
import numpy as np
from PIL import Image

REPORT = Path(__file__).resolve().parent
THERMAL = REPORT.parent
PROJECT = THERMAL / "home" / "projects" / "thermal-rom"
FIGURES = REPORT / "figures"
NAVY = "#164B6A"
TEAL = "#168A81"
ORANGE = "#CA7533"
RED = "#B44848"
GRAY = "#61727E"


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    plt.rcParams.update({
        "font.family": "DejaVu Sans", "font.size": 11,
        "axes.titlesize": 13, "axes.titleweight": "bold",
        "axes.labelsize": 11, "axes.labelcolor": "#253844",
        "axes.edgecolor": "#89949B", "axes.spines.top": False,
        "axes.spines.right": False, "xtick.color": "#425563", "ytick.color": "#425563",
        "legend.frameon": False, "legend.fontsize": 10,
        "savefig.facecolor": "white", "figure.facecolor": "white",
        "grid.color": "#DCE3E6", "grid.linewidth": .6, "lines.linewidth": 1.8,
        "mathtext.fontset": "dejavusans",
    })
    base_path = PROJECT / "workspace" / "results" / "02_baseline.json"
    failure_path = PROJECT / "workspace" / "results" / "03_failure.json"
    external_path = THERMAL / "independent_review" / "stage01_crosscheck.json"
    base, failure, external = map(read, [base_path, failure_path, external_path])
    fields_path = PROJECT / failure["artifact_directory"] / "development_fields.npz"
    with np.load(fields_path, allow_pickle=False) as archive:
        fields = {key: archive[key].copy() for key in archive.files}
    inputs = [base_path, failure_path, external_path, fields_path]
    before = {str(path): sha(path) for path in inputs}
    records = []

    def save(fig, name, paths, provenance, plotted_summary):
        output = FIGURES / name
        fig.savefig(output, dpi=300, facecolor="white", metadata={"Software": "Matplotlib; external report plotting"})
        plt.close(fig)
        with Image.open(output) as image:
            width, height = image.size
            dpi = image.info.get("dpi")
        records.append({
            "file": name, "sha256": sha(output), "width_px": width, "height_px": height,
            "dpi_metadata": dpi, "origin": "External figure preparation; not a native Moonshine tool action",
            "data_provenance": provenance,
            "input_files": [{"path": p.relative_to(THERMAL).as_posix(), "sha256": before[str(p)]} for p in paths],
            "plotted_summary": plotted_summary,
        })

    # 1: Preserve the near-machine-precision training point at full snapshot rank.
    fig, ax = plt.subplots(figsize=(7.2, 4.6), layout="constrained")
    for label, color, marker, display in [("train", TEAL, "o", "Training (24 points)"), ("tune", NAVY, "s", "Tuning (12 points)")]:
        rows = sorted((row for row in base["rank_curves"] if row["dataset"] == label), key=lambda r: r["rank"])
        ax.plot([r["rank"] for r in rows], [r["max_field_linf_error"] for r in rows], marker=marker,
                color=color, label=display, markersize=5.5)
    ax.axhline(.001, color=ORANGE, linestyle="--", linewidth=1.5, label=r"Target $\tau=10^{-3}$")
    ax.axvline(8, color="#8B969D", linestyle=":", linewidth=1.2)
    ax.set(xscale="log", yscale="log", xlabel="POD basis dimension r",
           ylabel=r"Maximum field error $\|T_{\rm ROM}-T_{\rm FOM}\|_\infty$",
           title="Rank selection on development data", xlim=(.85, 28), ylim=(4e-16, .07))
    ax.xaxis.set_major_locator(FixedLocator([1,2,4,8,12,24]))
    ax.xaxis.set_major_formatter(ScalarFormatter())
    ax.minorticks_off()
    ax.grid(axis="y")
    ax.legend(loc="lower left")
    ax.annotate("Selected: r = 8", xy=(8, .001), xytext=(.33, .65), textcoords="axes fraction",
                fontsize=11, color=NAVY, arrowprops={"arrowstyle":"-", "color":GRAY, "linewidth":.9},
                bbox={"facecolor":"white","edgecolor":"none","alpha":.95,"pad":3})
    fig.get_layout_engine().set(h_pad=.08, w_pad=.08)
    save(fig, "development_rank_curve.png", [base_path], "Native Moonshine Stage 2 JSON; existing training/tuning data only",
         {"n":24, "selected_rank":8, "tuning_error_r8":next(r["max_field_linf_error"] for r in base["rank_curves"] if r["dataset"]=="tune" and r["rank"]==8),
          "training_rank24_value_not_clipped":next(r["max_field_linf_error"] for r in base["rank_curves"] if r["dataset"]=="train" and r["rank"]==24)})

    # 2: False alarms refer to pre-correction field error, not hotspot-value error.
    rows = failure["rows"]
    error = np.array([r["field_linf_error"] for r in rows])
    eta = np.array([r["eta_float"] for r in rows])
    index = np.arange(1,len(rows)+1)
    tau = failure["summary"]["tau"]
    true_alarm = int(np.sum((eta>tau)&(error>tau)))
    false_alarm = int(np.sum((eta>tau)&(error<=tau)))
    misses = int(np.sum((eta<=tau)&(error>tau)))
    fig, axes = plt.subplots(1,2,figsize=(10.0,4.6),layout="constrained",gridspec_kw={"width_ratios":[2.1,1]})
    ax = axes[0]
    ax.plot(index, eta, color=ORANGE, marker="^", markersize=4, label=r"Barrier indicator $\eta$")
    ax.plot(index, error, color=NAVY, marker="o", markersize=4, label="Observed field error")
    ax.axhline(tau,color=RED,linestyle="--",linewidth=1.3,label=r"Target $\tau=10^{-3}$")
    ax.axvline(12.5,color=GRAY,linestyle=":",linewidth=1)
    ax.set(yscale="log",xlabel="Development-case index",ylabel="Error / indicator (dimensionless)",
           title="(a) Indicator versus observed error",xlim=(.5,28.5),ylim=(1e-5,4))
    ax.set_xticks([1,6,12,16,20,24,28])
    ax.grid(axis="y")
    handles,labels=ax.get_legend_handles_labels()
    fig.legend(handles,labels,loc="outside lower center",ncol=3,fontsize=10)
    ax.text(.18,.97,"12 tuning",transform=ax.transAxes,ha="center",va="top",color=GRAY,fontsize=10)
    ax.text(.72,.97,"16 corners",transform=ax.transAxes,ha="center",va="top",color=GRAY,fontsize=10)
    ax = axes[1]
    bars = ax.bar(["False\nalarm", "True\nalarm", "Miss"], [false_alarm,true_alarm,misses],
                  color=[ORANGE,NAVY,RED],width=.62)
    ax.set(title="(b) Trigger outcomes",ylabel="Cases",ylim=(0,30))
    ax.set_yticks([0,5,10,15,20,25,30])
    ax.grid(axis="y")
    ax.set_axisbelow(True)
    for bar, value in zip(bars,[false_alarm,true_alarm,misses]):
        ax.text(bar.get_x()+bar.get_width()/2,value+.6,str(value),ha="center",va="bottom",fontweight="bold",fontsize=12)
    save(fig, "development_indicator_failures.png", [failure_path], "Native Moonshine Stage 3 JSON; 12 reused tuning and 16 development corners",
         {"points":28,"true_alarms":true_alarm,"false_alarms":false_alarm,"misses":misses,"criterion":"field Linf before any correction", "floating_indicator_is_not_roundoff_certified":True})

    # 3: Read the already saved worst-case fields; no external PDE solve is done.
    worst_index = int(np.argmax(error))
    assert np.array_equal(fields["parameters"][worst_index], np.array(rows[worst_index]["h"]))
    full = fields["fom"][:,worst_index].reshape(24,24)
    reduced = fields["rom"][:,worst_index].reshape(24,24)
    absolute = np.abs(reduced-full)
    assert abs(float(absolute.max())-float(error[worst_index]))<1e-14
    vmin, vmax = min(float(full.min()),float(reduced.min())),max(float(full.max()),float(reduced.max()))
    fig, axes = plt.subplots(1,3,figsize=(10.5,4.1),layout="constrained")
    temperature_images=[]
    for ax, data, title in zip(axes[:2],[full,reduced],["(a) Full-order reference", "(b) Fixed POD, r = 8"]):
        im=ax.imshow(data,origin="lower",extent=(0,1,0,1),vmin=vmin,vmax=vmax,cmap="magma",interpolation="nearest")
        temperature_images.append(im)
        ax.set(title=title,xlabel="x",ylabel="y")
        for lo in [.2,.6]:
            ax.add_patch(Rectangle((lo,lo),.2,.2,fill=False,edgecolor="white",linewidth=.75,alpha=.65))
    im=axes[2].imshow(absolute,origin="lower",extent=(0,1,0,1),vmin=0,vmax=float(absolute.max()),cmap="viridis",interpolation="nearest")
    axes[2].set(title="(c) Absolute field error",xlabel="x",ylabel="y")
    for ax in axes:
        ax.set_xticks([0,.5,1]); ax.set_yticks([0,.5,1])
        ax.tick_params(labelsize=10)
    cb=fig.colorbar(temperature_images[0],ax=axes[:2],orientation="horizontal",shrink=.8,pad=.08,fraction=.08)
    cb.set_label("Dimensionless temperature rise",fontsize=11)
    cb.ax.tick_params(labelsize=9)
    ce=fig.colorbar(im,ax=axes[2],orientation="horizontal",shrink=.9,pad=.08,fraction=.08)
    ce.set_label("Absolute error",fontsize=11)
    ce.ax.tick_params(labelsize=9)
    ce.formatter.set_powerlimits((-3,3)); ce.update_ticks()
    fig.suptitle("Worst development case: h = (0.2, 0.2, 0.2, 0.2)",fontsize=14,fontweight="bold")
    save(fig,"development_worst_fields.png",[failure_path,fields_path],"Saved native Stage 3 NPZ fields, selected by largest recorded development field error; no recomputation",
         {"development_array_column":worst_index,"n":24,"rank":8,"parameter":rows[worst_index]["h"],
          "max_field_error":float(absolute.max()),"temperature_color_scale_shared":True})

    # 4: Explicitly separate external numerical validation from native agent work.
    external_check=next(v for v in external["checks"] if v["name"]=="native_operator_passes_external_manufactured_refinement")
    n=np.array([v["n"] for v in external_check["cases"]])
    measured=np.array([v["continuum_linf_error"] for v in external_check["cases"]])
    reference=measured[0]*(n[0]/n)**2
    fig,ax=plt.subplots(figsize=(7.2,4.5),layout="constrained")
    ax.plot(n,measured,color=NAVY,marker="o",markersize=6,label="Measured error")
    ax.plot(n,reference,color=ORANGE,linestyle="--",linewidth=1.4,label=r"Reference $n^{-2}$")
    ax.set(xscale="log",yscale="log",xlabel="Cells per side n",ylabel=r"Error against manufactured solution ($L^\infty$)",
           title="External manufactured-solution validation",xlim=(7,73))
    ax.xaxis.set_major_locator(FixedLocator([8,16,32,64]));ax.xaxis.set_major_formatter(ScalarFormatter());ax.minorticks_off()
    ax.grid(axis="both")
    ax.legend(loc="upper right")
    orders=external_check["observed_orders"]
    ax.text(.04,.08,"Observed orders: "+", ".join(f"{v:.3f}" for v in orders),transform=ax.transAxes,
            fontsize=11,color=NAVY,bbox={"facecolor":"white","edgecolor":"none","alpha":.9,"pad":5})
    save(fig,"external_manufactured_convergence.png",[external_path],"External independent Stage 1 crosscheck, using a manufactured source and the copied native operator; not a native Moonshine experiment",
         {"observed_orders":orders,"source_is_different_from_project_heat_rectangles":True,"no_new_solves_during_plotting":True})

    if before!={str(path):sha(path) for path in inputs}:
        raise RuntimeError("Input files changed during plotting; rerun against stable data.")
    manifest={"created_at":datetime.now(timezone.utc).isoformat(),"plotting_script_sha256":sha(Path(__file__)),
              "plotting_origin":"External report preparation", "real_model_calls":0, "new_simulations":0,
              "final_test_data_read_or_generated":False,"native_input_files_unchanged":True,"figures":records}
    (FIGURES/"figure_manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"figures":[{"file":r["file"],"size":[r["width_px"],r["height_px"]]} for r in records],"new_simulations":0},ensure_ascii=False))


if __name__=="__main__":
    main()
