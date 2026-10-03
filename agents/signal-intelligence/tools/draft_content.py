#!/usr/bin/env python3
"""Write one unpublished channel/format draft."""

import argparse

from _common import make_service, print_result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("id", type=int)
    parser.add_argument("--channel", choices=("linkedin", "x"), required=True)
    parser.add_argument("--format", choices=("post", "reply"), required=True)
    args = parser.parse_args()
    print_result(lambda: make_service().draft(args.id, args.channel, args.format))


if __name__ == "__main__":
    main()
