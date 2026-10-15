"""Command-line interface for building TracePack case packs."""

from __future__ import annotations

import argparse
from pathlib import Path

from . import __version__
from .core import verify_case_pack, write_case_pack


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="tracepack",
        description="Turn an evidence folder into a searchable, offline case pack.",
    )
    parser.add_argument("--version", action="version", version=f"TracePack {__version__}")
    subparsers = parser.add_subparsers(dest="command", required=True)
    build = subparsers.add_parser("build", help="build HTML, Markdown, timeline, and manifest outputs")
    build.add_argument("input", type=Path, help="folder containing evidence files")
    build.add_argument("-o", "--output", type=Path, required=True, help="empty or replaceable output folder")
    build.add_argument("--title", default="Evidence case pack", help="case title shown in the generated pack")
    build.add_argument("--force", action="store_true", help="replace an existing non-empty output folder")
    verify = subparsers.add_parser("verify", help="verify a generated pack and its copied evidence")
    verify.add_argument("pack", type=Path, help="generated case-pack folder")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "build":
        try:
            files = write_case_pack(args.input, args.output, args.title, force=args.force)
        except (OSError, ValueError) as error:
            print(f"tracepack: error: {error}")
            return 2
        print(f"Built TracePack for {args.input} ({len(files)} generated artifacts)")
        for path in files.values():
            print(f"  - {path}")
        return 0
    if args.command == "verify":
        try:
            errors = verify_case_pack(args.pack)
        except OSError as error:
            print(f"tracepack: error: {error}")
            return 2
        if errors:
            print("TracePack verification failed:")
            for error in errors:
                print(f"  - {error}")
            return 2
        print(f"TracePack verification passed: {args.pack}")
        return 0
    return 2
