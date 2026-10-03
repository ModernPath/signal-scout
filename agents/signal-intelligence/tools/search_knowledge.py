#!/usr/bin/env python3
"""Inspect/index company memory or refine one explicitly selected opportunity."""
import argparse
from _common import make_service, print_result

def main():
    parser=argparse.ArgumentParser()
    commands=parser.add_subparsers(dest='action',required=True)
    commands.add_parser('status')
    commands.add_parser('index')
    search=commands.add_parser('search');search.add_argument('query')
    refine=commands.add_parser('refine');refine.add_argument('id',type=int)
    args=parser.parse_args()
    def action():
        agent=make_service()
        if args.action=='status': return agent.knowledge.status()
        if args.action=='index':
            agent.knowledge.store.retry()
            return agent.knowledge.index_pending()
        if args.action=='search': return agent.search_knowledge(args.query)
        return agent.refine_angle(args.id)
    print_result(action)

if __name__=='__main__': main()
