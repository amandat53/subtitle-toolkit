"""Parsing and manipulation of .srt subtitle files."""

from __future__ import annotations

import re
from dataclasses import dataclass

__version__ = "0.1.0"

_TIME_RE = re.compile(r"(\d+):(\d{2}):(\d{2})[,.](\d{3})")
_TIMESTAMP_RE = re.compile(r"(\d+:\d{2}:\d{2}[,.]\d{3})\s*-->\s*(\d+:\d{2}:\d{2}[,.]\d{3})")

# WebVTT timestamps drop the hours component when it's zero, unlike .srt.
_VTT_TIME_RE = re.compile(r"(?:(\d+):)?(\d{2}):(\d{2})\.(\d{3})")
_VTT_TIMESTAMP_RE = re.compile(
    r"((?:\d+:)?\d{2}:\d{2}\.\d{3})\s*-->\s*((?:\d+:)?\d{2}:\d{2}\.\d{3})"
)


class SubtitleError(ValueError):
    """Raised when a subtitle file can't be parsed."""


@dataclass
class Cue:
    index: int
    start_ms: int
    end_ms: int
    text: str

    @property
    def duration_ms(self) -> int:
        return self.end_ms - self.start_ms


def parse_timestamp(raw: str) -> int:
    """Convert 'HH:MM:SS,mmm' or 'HH:MM:SS.mmm' to milliseconds."""
    m = _TIME_RE.match(raw.strip())
    if not m:
        raise SubtitleError(f"bad timestamp: {raw!r}")
    hours, minutes, seconds, millis = (int(g) for g in m.groups())
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def format_timestamp(ms: int, sep: str = ",") -> str:
    ms = max(0, ms)
    hours, rem = divmod(ms, 3_600_000)
    minutes, rem = divmod(rem, 60_000)
    seconds, millis = divmod(rem, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}{sep}{millis:03d}"


def parse(text: str) -> list[Cue]:
    """Parse the contents of an .srt file into a list of Cue objects."""
    blocks = re.split(r"\r?\n\r?\n+", text.strip())
    cues: list[Cue] = []
    for block in blocks:
        lines = [line for line in block.splitlines() if line.strip() != ""]
        if not lines:
            continue
        # A leading numeric index is standard but some tools drop it, so
        # only consume it when it's actually there.
        offset = 1 if lines[0].strip().isdigit() else 0
        if len(lines) <= offset:
            raise SubtitleError(f"malformed cue block: {block!r}")
        ts_match = _TIMESTAMP_RE.search(lines[offset])
        if not ts_match:
            raise SubtitleError(f"missing timestamp line in block: {block!r}")
        start_ms = parse_timestamp(ts_match.group(1))
        end_ms = parse_timestamp(ts_match.group(2))
        text_lines = lines[offset + 1:]
        cues.append(Cue(index=len(cues) + 1, start_ms=start_ms, end_ms=end_ms,
                         text="\n".join(text_lines)))
    return cues


def parse_vtt_timestamp(raw: str) -> int:
    """Convert a WebVTT timestamp ('HH:MM:SS.mmm' or 'MM:SS.mmm') to milliseconds."""
    m = _VTT_TIME_RE.match(raw.strip())
    if not m:
        raise SubtitleError(f"bad timestamp: {raw!r}")
    hours = int(m.group(1)) if m.group(1) else 0
    minutes, seconds, millis = (int(g) for g in m.groups()[1:])
    return ((hours * 60 + minutes) * 60 + seconds) * 1000 + millis


def parse_vtt(text: str) -> list[Cue]:
    """Parse the contents of a WebVTT file into a list of Cue objects.

    Cue identifiers, NOTE/STYLE/REGION blocks, and cue settings (position,
    line, align, etc.) are recognized and discarded; only timing and text
    are kept.
    """
    text = text.strip()
    if not text.startswith("WEBVTT"):
        raise SubtitleError("not a WebVTT file: missing WEBVTT header")
    blocks = re.split(r"\r?\n\r?\n+", text)
    cues: list[Cue] = []
    for block in blocks[1:]:
        lines = [line for line in block.splitlines() if line.strip() != ""]
        if not lines:
            continue
        first = lines[0].strip()
        if first.startswith(("NOTE", "STYLE", "REGION")):
            continue
        # A cue identifier is optional; when present it's the line before
        # the timing line rather than the line containing '-->'.
        offset = 0 if "-->" in lines[0] else 1
        if len(lines) <= offset:
            raise SubtitleError(f"malformed cue block: {block!r}")
        ts_match = _VTT_TIMESTAMP_RE.search(lines[offset])
        if not ts_match:
            raise SubtitleError(f"missing timestamp line in block: {block!r}")
        start_ms = parse_vtt_timestamp(ts_match.group(1))
        end_ms = parse_vtt_timestamp(ts_match.group(2))
        text_lines = lines[offset + 1:]
        cues.append(Cue(index=len(cues) + 1, start_ms=start_ms, end_ms=end_ms,
                         text="\n".join(text_lines)))
    return cues


def parse_any(text: str) -> list[Cue]:
    """Parse either .srt or WebVTT text, detected from the content."""
    if text.lstrip().startswith("WEBVTT"):
        return parse_vtt(text)
    return parse(text)


def dump(cues: list[Cue]) -> str:
    """Serialize cues back to .srt text, renumbering sequentially."""
    parts = []
    for i, cue in enumerate(cues, start=1):
        parts.append(
            f"{i}\n"
            f"{format_timestamp(cue.start_ms)} --> {format_timestamp(cue.end_ms)}\n"
            f"{cue.text}\n"
        )
    return "\n".join(parts) + "\n"


def shift(cues: list[Cue], offset_ms: int) -> list[Cue]:
    """Return a new list of cues with all timestamps shifted by offset_ms."""
    return [
        Cue(index=c.index, start_ms=max(0, c.start_ms + offset_ms),
            end_ms=max(0, c.end_ms + offset_ms), text=c.text)
        for c in cues
    ]


def find_overlaps(cues: list[Cue]) -> list[tuple[Cue, Cue]]:
    """Return pairs of cues whose time ranges overlap, ordered by start time."""
    ordered = sorted(cues, key=lambda c: c.start_ms)
    return [(a, b) for a, b in zip(ordered, ordered[1:]) if b.start_ms < a.end_ms]


def to_vtt(cues: list[Cue]) -> str:
    """Render cues as a WebVTT document."""
    lines = ["WEBVTT", ""]
    for cue in cues:
        lines.append(
            f"{format_timestamp(cue.start_ms, sep='.')} --> "
            f"{format_timestamp(cue.end_ms, sep='.')}"
        )
        lines.append(cue.text)
        lines.append("")
    return "\n".join(lines)
