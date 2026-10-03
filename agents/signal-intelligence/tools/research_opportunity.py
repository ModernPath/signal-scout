#!/usr/bin/env python3
"""Research one explicitly selected opportunity."""

import argparse

from _common import make_service, print_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("id", type=int)
    args = parser.parse_args()
    print_result(lambda: make_service().research(args.id))


if __name__ == "__main__":
    main()
