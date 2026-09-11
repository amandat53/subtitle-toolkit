"""Command-line interface for subtl."""

from __future__ import annotations

import argparse
import sys

from . import SubtitleError, dump, find_overlaps, fix_overlaps, parse_any, shift, to_vtt


def _read(path: str) -> str:
    if path == "-":
        return sys.stdin.read()
    with open(path, encoding="utf-8-sig") as f:
        return f.read()


def _write(path: str | None, text: str) -> None:
    if path is None or path == "-":
        sys.stdout.write(text)
    else:
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)


def cmd_shift(args: argparse.Namespace) -> int:
    cues = parse_any(_read(args.input))
    _write(args.output, dump(shift(cues, args.milliseconds)))
    return 0


def cmd_convert(args: argparse.Namespace) -> int:
    cues = parse_any(_read(args.input))
    _write(args.output, to_vtt(cues))
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    cues = parse_any(_read(args.input))
    overlaps = find_overlaps(cues)
    print(f"{len(cues)} cues")
    if not overlaps:
        print("no overlaps found")
        return 0
    for a, b in overlaps:
        print(f"overlap: cue {a.index} ends after cue {b.index} starts")
    return 1


def cmd_fix_overlaps(args: argparse.Namespace) -> int:
    cues = parse_any(_read(args.input))
    fixed = fix_overlaps(cues)
    _write(args.output, dump(fixed))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="subtl", description="Work with .srt subtitle files.")
    sub = parser.add_subparsers(dest="command", required=True)

    p_shift = sub.add_parser("shift", help="shift all timestamps by a fixed offset")
    p_shift.add_argument("input", help="input .srt file, or - for stdin")
    p_shift.add_argument("milliseconds", type=int, help="offset in ms, may be negative")
    p_shift.add_argument("-o", "--output", help="output file, defaults to stdout")
    p_shift.set_defaults(func=cmd_shift)

    p_convert = sub.add_parser("to-vtt", help="convert an .srt file to WebVTT")
    p_convert.add_argument("input", help="input .srt file, or - for stdin")
    p_convert.add_argument("-o", "--output", help="output file, defaults to stdout")
    p_convert.set_defaults(func=cmd_convert)

    p_check = sub.add_parser("check", help="report cue count and overlapping timestamps")
    p_check.add_argument("input", help="input .srt file, or - for stdin")
    p_check.set_defaults(func=cmd_check)

    p_fix = sub.add_parser(
        "fix-overlaps", help="trim cue end times so no cue overlaps the next one"
    )
    p_fix.add_argument("input", help="input .srt file, or - for stdin")
    p_fix.add_argument("-o", "--output", help="output file, defaults to stdout")
    p_fix.set_defaults(func=cmd_fix_overlaps)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except (SubtitleError, OSError) as exc:
        print(f"subtl: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
