#!/usr/bin/env python3
"""Analyze recent signals and emit one JSON envelope."""

import argparse

from _common import make_service, print_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=30)
    parser.add_argument("--limit", type=int, default=500)
    args = parser.parse_args()
    print_result(lambda: make_service().analyze(days=args.days, limit=args.limit))


if __name__ == "__main__":
    main()
