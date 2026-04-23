import argparse
import csv
import json
import re
from pathlib import Path
from typing import Dict, List

from tensorboard.backend.event_processing.event_accumulator import EventAccumulator


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^a-zA-Z0-9._-]+", "_", name)


def discover_event_files(logdir: Path) -> List[Path]:
    return sorted(logdir.rglob("events.out.tfevents.*"))


def run_name_from_path(event_file: Path, logdir: Path) -> str:
    rel_parent = event_file.parent.relative_to(logdir)
    stem = sanitize_filename(event_file.name)
    if str(rel_parent) == ".":
        return stem
    return sanitize_filename(f"{rel_parent}_{stem}")


def extract_scalars(event_file: Path) -> Dict[str, List[dict]]:
    accumulator = EventAccumulator(str(event_file), size_guidance={"scalars": 0})
    accumulator.Reload()
    tags = accumulator.Tags().get("scalars", [])
    output = {}
    for tag in tags:
        events = accumulator.Scalars(tag)
        output[tag] = [
            {"step": int(event.step), "value": float(event.value), "wall_time": float(event.wall_time)}
            for event in events
        ]
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Extract TensorBoard scalar events to CSV files.")
    parser.add_argument("--logdir", type=Path, required=True, help="TensorBoard logs directory.")
    parser.add_argument(
        "--outdir", type=Path, default=Path("analysis/tb_export"), help="Output directory for extracted CSV files."
    )
    parser.add_argument(
        "--include-tags",
        type=str,
        default="",
        help="Optional regex to include only matching tags. Empty means include all.",
    )
    args = parser.parse_args()

    event_files = discover_event_files(args.logdir)
    if not event_files:
        raise FileNotFoundError(f"No TensorBoard event files found under: {args.logdir}")

    tag_filter = re.compile(args.include_tags) if args.include_tags else None
    scalars_dir = args.outdir / "scalars"
    scalars_dir.mkdir(parents=True, exist_ok=True)

    merged_by_tag: Dict[str, List[dict]] = {}
    run_event_map = {}

    for event_file in event_files:
        run_name = run_name_from_path(event_file, args.logdir)
        run_event_map[run_name] = str(event_file)
        scalar_map = extract_scalars(event_file)
        for tag, rows in scalar_map.items():
            if tag_filter and not tag_filter.search(tag):
                continue
            merged_by_tag.setdefault(tag, [])
            for row in rows:
                merged_by_tag[tag].append(
                    {
                        "run": run_name,
                        "step": row["step"],
                        "value": row["value"],
                        "wall_time": row["wall_time"],
                    }
                )

    if not merged_by_tag:
        raise ValueError("No scalar tags extracted. Check your --include-tags filter.")

    index = {}
    for tag, rows in merged_by_tag.items():
        safe_tag = sanitize_filename(tag)
        csv_path = scalars_dir / f"{safe_tag}.csv"
        with csv_path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=["run", "step", "value", "wall_time"])
            writer.writeheader()
            writer.writerows(rows)
        index[tag] = str(csv_path)

    with (args.outdir / "index.json").open("w", encoding="utf-8") as f:
        json.dump({"logdir": str(args.logdir), "runs": run_event_map, "tags": index}, f, indent=2)

    print(f"Done. Extracted {len(index)} scalar tags from {len(event_files)} event files.")
    print(f"Output directory: {args.outdir}")


if __name__ == "__main__":
    main()
