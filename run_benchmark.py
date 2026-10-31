#!/usr/bin/env python3
"""
RSI-Bench: Quick CLI runner script.
Usage:
    python run_benchmark.py --mock
    python run_benchmark.py --provider deepseek --model deepseek-reasoner
    python run_benchmark.py --list-providers
"""

import sys
from rsi_bench.cli import main

if __name__ == "__main__":
    sys.exit(main())
