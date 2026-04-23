import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import numpy as np


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name)


def ema(values: np.ndarray, alpha: float) -> np.ndarray:
    if len(values) == 0:
        return values
    out = np.empty_like(values, dtype=float)
    out[0] = values[0]
    for i in range(1, len(values)):
        out[i] = alpha * values[i] + (1.0 - alpha) * out[i - 1]
    return out


def apply_style_template(style_template: str) -> None:
    plt.style.use("seaborn-v0_8-whitegrid")
    if style_template == "ieee":
        plt.rcParams.update(
            {
                "font.family": "serif",
                "font.size": 8,
                "axes.titlesize": 9,
                "axes.labelsize": 8,
                "xtick.labelsize": 7,
                "ytick.labelsize": 7,
                "legend.fontsize": 7,
                "figure.figsize": (3.5, 2.4),  # single-column IEEE-ish
                "lines.linewidth": 1.6,
            }
        )
    elif style_template == "springer":
        plt.rcParams.update(
            {
                "font.family": "serif",
                "font.size": 9,
                "axes.titlesize": 10,
                "axes.labelsize": 9,
                "xtick.labelsize": 8,
                "ytick.labelsize": 8,
                "legend.fontsize": 8,
                "figure.figsize": (4.8, 3.0),
                "lines.linewidth": 1.8,
            }
        )
    else:
        plt.rcParams.update(
            {
                "font.family": "sans-serif",
                "font.size": 10,
                "axes.titlesize": 11,
                "axes.labelsize": 10,
                "xtick.labelsize": 9,
                "ytick.labelsize": 9,
                "legend.fontsize": 9,
                "figure.figsize": (6.6, 4.2),
                "lines.linewidth": 2.0,
            }
        )


def load_tag_csv(path: Path) -> Dict[str, List[Tuple[int, float]]]:
    by_run: Dict[str, List[Tuple[int, float]]] = defaultdict(list)
    with path.open("r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            by_run[row["run"]].append((int(row["step"]), float(row["value"])))
    for run in by_run:
        by_run[run].sort(key=lambda x: x[0])
    return by_run


def aggregate_by_step(run_series: Dict[str, List[Tuple[int, float]]], alpha: float):
    smoothed: Dict[str, List[Tuple[int, float]]] = {}
    for run, points in run_series.items():
        steps = np.array([p[0] for p in points], dtype=int)
        values = np.array([p[1] for p in points], dtype=float)
        if alpha > 0:
            values = ema(values, alpha=alpha)
        smoothed[run] = list(zip(steps, values))

    values_by_step: Dict[int, List[float]] = defaultdict(list)
    for points in smoothed.values():
        for step, value in points:
            values_by_step[int(step)].append(float(value))

    steps = np.array(sorted(values_by_step.keys()), dtype=int)
    mean = np.array([np.mean(values_by_step[s]) for s in steps], dtype=float)
    std = np.array([np.std(values_by_step[s]) for s in steps], dtype=float)
    return smoothed, steps, mean, std


def load_optional_json(path: Optional[Path]) -> dict:
    if path is None:
        return {}
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def resolve_original_tag(csv_stem: str, index_json: dict) -> str:
    if not index_json:
        return csv_stem
    tags = index_json.get("tags", {})
    for original_tag, csv_path in tags.items():
        if Path(csv_path).stem == csv_stem:
            return original_tag
    return csv_stem


def pretty_label(tag: str, pretty_map: dict) -> str:
    if tag in pretty_map:
        return pretty_map[tag]
    for key, value in pretty_map.items():
        if key.startswith("re:"):
            pattern = key[3:]
            if re.search(pattern, tag):
                return value
    return tag


def assign_run_group(run_name: str, group_rules: dict) -> str:
    # group_rules format: {"COMA": "regex", "Baseline": "regex2"}
    for group_name, pattern in group_rules.items():
        if re.search(pattern, run_name):
            return group_name
    return "Ungrouped"


def plot_single_tag(
    title_tag: str,
    run_series: Dict[str, List[Tuple[int, float]]],
    outdir: Path,
    alpha: float,
    dpi: int,
    xlim: Optional[Tuple[float, float]],
    ylim: Optional[Tuple[float, float]],
) -> None:
    smoothed, steps, mean, std = aggregate_by_step(run_series, alpha=alpha)
    if len(steps) == 0:
        return

    fig, ax = plt.subplots()
    for _, points in smoothed.items():
        x = np.array([p[0] for p in points], dtype=int)
        y = np.array([p[1] for p in points], dtype=float)
        ax.plot(x, y, alpha=0.20, linewidth=1.0, color="#7fa8ff")

    ax.plot(steps, mean, color="#1144aa", label="Mean")
    if len(smoothed) > 1:
        ax.fill_between(steps, mean - std, mean + std, color="#1144aa", alpha=0.20, label="±1 std")

    ax.set_title(title_tag)
    ax.set_xlabel("Step")
    ax.set_ylabel("Value")
    if xlim is not None:
        ax.set_xlim(*xlim)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.legend(loc="best", frameon=True)
    fig.tight_layout()

    filename = sanitize_filename(title_tag)
    outdir.mkdir(parents=True, exist_ok=True)
    fig.savefig(outdir / f"{filename}.png", dpi=dpi, bbox_inches="tight")
    fig.savefig(outdir / f"{filename}.pdf", bbox_inches="tight")
    plt.close(fig)


def plot_group_comparison(
    title_tag: str,
    run_series: Dict[str, List[Tuple[int, float]]],
    outdir: Path,
    alpha: float,
    dpi: int,
    group_rules: dict,
    xlim: Optional[Tuple[float, float]],
    ylim: Optional[Tuple[float, float]],
) -> bool:
    grouped_runs: Dict[str, Dict[str, List[Tuple[int, float]]]] = defaultdict(dict)
    for run_name, points in run_series.items():
        group_name = assign_run_group(run_name, group_rules)
        grouped_runs[group_name][run_name] = points

    # If we have matched groups, drop legacy/unmatched runs from comparison view.
    matched_groups = [g for g in grouped_runs.keys() if g != "Ungrouped"]
    if len(matched_groups) > 0 and "Ungrouped" in grouped_runs:
        grouped_runs.pop("Ungrouped", None)

    # If grouping is still meaningless (all ungrouped or only one group), skip.
    if len(grouped_runs) <= 1:
        return False

    fig, ax = plt.subplots()
    colors = ["#1144aa", "#c0392b", "#1e8449", "#7d3c98", "#ca6f1e", "#117a65"]

    for idx, (group_name, series) in enumerate(sorted(grouped_runs.items())):
        _, steps, mean, std = aggregate_by_step(series, alpha=alpha)
        if len(steps) == 0:
            continue
        color = colors[idx % len(colors)]
        if len(steps) <= 2:
            ax.plot(
                steps,
                mean,
                color=color,
                label=f"{group_name} mean",
                marker="o",
                markersize=5,
            )
        else:
            ax.plot(steps, mean, color=color, label=f"{group_name} mean")
        if len(series) > 1:
            ax.fill_between(steps, mean - std, mean + std, color=color, alpha=0.18, label=f"{group_name} ±1 std")

    ax.set_title(f"{title_tag} (Group Comparison)")
    ax.set_xlabel("Step")
    ax.set_ylabel("Value")
    if xlim is not None:
        ax.set_xlim(*xlim)
    if ylim is not None:
        ax.set_ylim(*ylim)
    ax.legend(loc="best", frameon=True)
    fig.tight_layout()

    filename = sanitize_filename(f"{title_tag}_group_compare")
    outdir.mkdir(parents=True, exist_ok=True)
    fig.savefig(outdir / f"{filename}.png", dpi=dpi, bbox_inches="tight")
    fig.savefig(outdir / f"{filename}.pdf", bbox_inches="tight")
    plt.close(fig)
    return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Create publication-style plots from extracted TensorBoard scalar CSVs.")
    parser.add_argument(
        "--scalars-dir",
        type=Path,
        default=Path("analysis/tb_export/scalars"),
        help="Directory containing per-tag CSV files from extract_tb_scalars.py",
    )
    parser.add_argument("--outdir", type=Path, default=Path("analysis/paper_figures"), help="Output figure directory.")
    parser.add_argument(
        "--include-tags",
        type=str,
        default="",
        help="Optional regex filter on tag names (applied to original tag if index is available).",
    )
    parser.add_argument(
        "--ema-alpha",
        type=float,
        default=0.2,
        help="EMA smoothing alpha in [0,1]. Set 0 for no smoothing.",
    )
    parser.add_argument("--dpi", type=int, default=300, help="PNG export DPI.")
    parser.add_argument(
        "--style-template",
        type=str,
        default="default",
        choices=["default", "ieee", "springer"],
        help="Paper style template preset.",
    )
    parser.add_argument(
        "--index-json",
        type=Path,
        default=Path("analysis/tb_export/index.json"),
        help="Index file created by extract_tb_scalars.py for restoring original tag names.",
    )
    parser.add_argument(
        "--pretty-labels-json",
        type=Path,
        default=None,
        help="Optional JSON for pretty labels. Supports exact tag keys and 're:<pattern>' keys.",
    )
    parser.add_argument(
        "--group-regex-json",
        type=Path,
        default=None,
        help="Optional JSON mapping {group_name: regex} for algorithm/run group comparison plots.",
    )
    parser.add_argument("--xlim-min", type=float, default=None, help="Optional x-axis minimum.")
    parser.add_argument("--xlim-max", type=float, default=None, help="Optional x-axis maximum.")
    parser.add_argument("--ylim-min", type=float, default=None, help="Optional y-axis minimum.")
    parser.add_argument("--ylim-max", type=float, default=None, help="Optional y-axis maximum.")
    args = parser.parse_args()

    if not args.scalars_dir.exists():
        raise FileNotFoundError(f"Scalars directory not found: {args.scalars_dir}")
    if not (0.0 <= args.ema_alpha <= 1.0):
        raise ValueError("--ema-alpha must be between 0 and 1.")

    apply_style_template(args.style_template)
    xlim = (
        (args.xlim_min, args.xlim_max)
        if (args.xlim_min is not None and args.xlim_max is not None)
        else None
    )
    ylim = (
        (args.ylim_min, args.ylim_max)
        if (args.ylim_min is not None and args.ylim_max is not None)
        else None
    )

    include = re.compile(args.include_tags) if args.include_tags else None
    csv_files = sorted(args.scalars_dir.glob("*.csv"))
    if not csv_files:
        raise FileNotFoundError(f"No CSV files found in: {args.scalars_dir}")

    index_json = load_optional_json(args.index_json)
    pretty_map = load_optional_json(args.pretty_labels_json)
    group_rules = load_optional_json(args.group_regex_json)

    single_outdir = args.outdir / "single"
    compare_outdir = args.outdir / "group_compare"
    plotted_single = 0
    plotted_compare = 0

    for csv_file in csv_files:
        csv_stem = csv_file.stem
        original_tag = resolve_original_tag(csv_stem, index_json)
        if include and not include.search(original_tag):
            continue

        display_tag = pretty_label(original_tag, pretty_map)
        run_series = load_tag_csv(csv_file)
        if not run_series:
            continue

        plot_single_tag(
            display_tag, run_series, single_outdir, args.ema_alpha, args.dpi, xlim, ylim
        )
        plotted_single += 1

        if group_rules:
            created = plot_group_comparison(
                display_tag,
                run_series,
                compare_outdir,
                args.ema_alpha,
                args.dpi,
                group_rules,
                xlim,
                ylim,
            )
            if created:
                plotted_compare += 1

    if plotted_single == 0:
        raise ValueError("No tags plotted. Check --include-tags filter.")

    print(f"Done. Generated {plotted_single} single-tag figure(s) in: {single_outdir}")
    if group_rules:
        print(f"Done. Generated {plotted_compare} group comparison figure(s) in: {compare_outdir}")


if __name__ == "__main__":
    main()
