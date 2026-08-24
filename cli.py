#!/usr/bin/env python3

import argparse
import asyncio
import json
import sys
from services import match_service


class ScoreCLI:
    @staticmethod
    def validate_match_id(value: str) -> str:
        value = value.strip()
        if not value:
            raise argparse.ArgumentTypeError("match_id cannot be empty")
        if not value.isdigit():
            raise argparse.ArgumentTypeError("match_id must contain digits only")
        if len(value) < 4:
            raise argparse.ArgumentTypeError("match_id must be at least 4 digits")
        return value

    @classmethod
    def parse_arguments(cls):
        parser = argparse.ArgumentParser(
            prog="scorecli",
            description="Fetch live cricket scores, matches, scorecards, and commentary",
            formatter_class=argparse.RawTextHelpFormatter,
        )

        parser.add_argument(
            "match_id",
            nargs="?",
            default=None,
            help="numeric match id (optional if --live or --upcoming is used)",
        )

        group = parser.add_mutually_exclusive_group()
        group.add_argument("--live", action="store_true", help="list live matches")
        group.add_argument("--upcoming", action="store_true", help="list upcoming matches")
        group.add_argument("--scorecard", action="store_true", help="fetch detailed scorecard")
        group.add_argument("--commentary", action="store_true", help="fetch live ball-by-ball commentary")
        group.add_argument("--recent", action="store_true", help="fetch latest commentary event")
        group.add_argument("--full", action="store_true", help="fetch full combined match payload")
        group.add_argument("--changes", action="store_true", help="detect recent ball & score changes")

        return parser.parse_args()

    @classmethod
    async def async_run(cls):
        args = cls.parse_arguments()

        if args.live:
            res = await match_service.get_live_matches()
            print(json.dumps(res.model_dump(), indent=2, ensure_ascii=False))
            return

        if args.upcoming:
            res = await match_service.get_upcoming_matches()
            print(json.dumps(res.model_dump(), indent=2, ensure_ascii=False))
            return

        if not args.match_id:
            print("Error: match_id is required unless --live or --upcoming is specified.")
            sys.exit(1)

        cls.validate_match_id(args.match_id)

        if args.scorecard:
            res = await match_service.get_scorecard(args.match_id)
            print(json.dumps(res.model_dump(), indent=2, ensure_ascii=False))
            return

        if args.commentary:
            res = await match_service.get_commentary(args.match_id)
            print(json.dumps(res.model_dump(), indent=2, ensure_ascii=False))
            return

        if args.recent:
            res = await match_service.get_recent_event(args.match_id)
            print(json.dumps(res.model_dump(), indent=2, ensure_ascii=False))
            return

        if args.full:
            res = await match_service.get_full_match(args.match_id)
            print(json.dumps(res.model_dump(), indent=2, ensure_ascii=False))
            return

        if args.changes:
            res = await match_service.detect_match_changes(args.match_id)
            print(json.dumps(res.model_dump(), indent=2, ensure_ascii=False))
            return

        # Default overview
        res = await match_service.get_match_overview(args.match_id)
        print(json.dumps(res.model_dump(), indent=2, ensure_ascii=False))

    @classmethod
    def run(cls):
        if hasattr(sys.stdout, "reconfigure"):
            try:
                sys.stdout.reconfigure(encoding="utf-8")
            except Exception:
                pass

        asyncio.run(cls.async_run())


if __name__ == "__main__":
    try:
        ScoreCLI.run()
    except KeyboardInterrupt:
        print("\nInterrupted by user")
        sys.exit(130)