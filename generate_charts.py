#!/usr/bin/env python3
"""
RSI-Bench Chart Generator CLI.

Generates:
1. Artificial Analysis Intelligence Index style bar chart matching the benchmark image.
2. Trajectory line graph displaying turn-by-turn integer outputs + cumulative prefix sums
   with completely UNLABELED axes to preserve the benchmark spoof.
3. High-resolution PNG renders via Chrome or Edge headless CLI.

Usage:
    python generate_charts.py
    python generate_charts.py --reference
    python generate_charts.py --data results/batch_8472fbc647.json
    python generate_charts.py --data results/benchmark_summary.csv
    python generate_charts.py --no-png
"""

from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys
import webbrowser

from rsi_bench.visualization import (
    find_browser_executable,
    find_latest_results,
    generate_all_charts,
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate Artificial Analysis style benchmark charts and multi-turn trajectory graphs for RSI-Bench.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-d", "--data",
        type=str,
        default=None,
        help="Path to results batch JSON, summary CSV, or traces directory. Defaults to latest result or reference data.",
    )
    parser.add_argument(
        "-r", "--reference",
        action="store_true",
        help="Generate exact Artificial Analysis reference chart (29 models with exact scores matching the image).",
    )
    parser.add_argument(
        "-o", "--output-dir",
        type=str,
        default="results/charts",
        help="Directory where HTML and PNG charts will be saved.",
    )
    parser.add_argument(
        "-n", "--turns",
        type=int,
        default=5,
        help="Number of turns to show/simulate in the multi-turn trajectory graph.",
    )
    parser.add_argument(
        "--no-png",
        action="store_true",
        help="Skip automatic PNG generation via headless browser (generate HTML only).",
    )
    parser.add_argument(
        "--browser",
        type=str,
        default=None,
        help="Explicit path to Chrome or Edge executable for headless rendering.",
    )
    parser.add_argument(
        "--open",
        action="store_true",
        help="Open the generated HTML charts in default web browser.",
    )

    args = parser.parse_args()

    # Determine data source
    data_source = args.data
    if not data_source and not args.reference:
        latest = find_latest_results()
        if latest:
            print(f"[*] Detected recent benchmark results: {latest}")
            data_source = latest
        else:
            print("[*] No existing benchmark results found. Using reference mock data.")

    print(f"[*] Generating RSI-Bench charts in: {args.output_dir}")

    # Generate charts
    try:
        results = generate_all_charts(
            data_source=data_source,
            output_dir=args.output_dir,
            num_turns=args.turns,
            render_png=not args.no_png,
            browser_path=args.browser,
            use_reference_scores=args.reference,
        )
    except Exception as exc:
        print(f"[!] Error generating charts: {exc}", file=sys.stderr)
        return 1

    print("\n[+] Generated Chart Artifacts:")
    for key, path in results.items():
        print(f"    - {key:<20}: file:///{path.absolute().as_posix()}")

    if not args.no_png:
        if "bar_chart_png" not in results or "line_graph_png" not in results:
            browser = find_browser_executable(args.browser)
            if not browser:
                print("\n[i] Note: Chrome or Edge was not detected on system PATH. PNG export skipped (HTML ready).")

    if args.open and "bar_chart_html" in results:
        webbrowser.open(results["bar_chart_html"].resolve().as_uri())

    return 0


if __name__ == "__main__":
    sys.exit(main())
