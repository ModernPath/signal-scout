#!/usr/bin/env python3
"""Manage the company brief and previous content through one JSON tool."""

import argparse

from _common import make_service, print_result, read_json


def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="kind", required=True)
    brief = sub.add_parser("brief")
    brief_sub = brief.add_subparsers(dest="action", required=True)
    brief_sub.add_parser("show")
    brief_sub.add_parser("set").add_argument("file")
    brief_sub.add_parser("delete")
    content = sub.add_parser("content")
    content_sub = content.add_subparsers(dest="action", required=True)
    content_sub.add_parser("list")
    content_sub.add_parser("add").add_argument("file")
    replace = content_sub.add_parser("replace")
    replace.add_argument("id", type=int)
    replace.add_argument("file")
    content_sub.add_parser("delete").add_argument("id", type=int)
    args = parser.parse_args()
    service = make_service()

    def action():
        if args.kind == "brief":
            if args.action == "show":
                return service.get_brief()
            if args.action == "delete":
                return service.clear_brief()
            return service.set_brief(read_json(args.file))
        if args.action == "list":
            return service.list_content()
        if args.action == "add":
            return service.add_content(read_json(args.file))
        if args.action == "replace":
            return service.replace_content(args.id, read_json(args.file))
        return service.delete_content(args.id)

    print_result(action)


if __name__ == "__main__":
    main()
