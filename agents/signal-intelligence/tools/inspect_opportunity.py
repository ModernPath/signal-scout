#!/usr/bin/env python3
"""Inspect ranked opportunities and provenance."""

import argparse

from _common import make_service, print_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("id", type=int, nargs="?")
    args = parser.parse_args()
    service = make_service()
    print_result(lambda: service.opportunity(args.id) if args.id else service.opportunities())


if __name__ == "__main__":
    main()
