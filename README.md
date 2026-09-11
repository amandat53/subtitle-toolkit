# subtl

A pulled-down movie has audio that's a couple seconds out of sync with the
subtitle track someone else timed against a different rip. Or you've got an
.srt from one source and need a .vtt for a web player. `subtl` is a small
Python library plus a CLI for the handful of things I keep needing to do to
subtitle files: shift every timestamp by a fixed offset, convert between
formats, and check whether a file has overlapping cues (usually a sign the
timing is broken). Input can be .srt or WebVTT; every command figures out
which one it's looking at from the content.

No dependencies beyond the standard library.

## Install

Nothing is published yet. Clone this repo and run the CLI straight from the
source tree:

```
python -m subtl.cli check movie.srt
```

or install it locally in editable mode:

```
pip install -e .
subtl check movie.srt
```

## CLI usage

Shift a subtitle file forward by 2.5 seconds (writes to stdout):

```
subtl shift movie.srt 2500 -o movie-fixed.srt
```

Negative numbers shift earlier:

```
subtl shift movie.srt -1200 -o movie-fixed.srt
```

Convert to WebVTT for a browser player:

```
subtl to-vtt movie.srt -o movie.vtt
```

Check for cues that overlap each other (exit code is 1 if any are found):

```
subtl check movie.srt
```

Fix overlaps by trimming each cue's end time back to where the next one
starts:

```
subtl fix-overlaps movie.srt -o movie-fixed.srt
```

Any command that takes a file also accepts `-` to read from stdin.

## Library usage

```python
from subtl import parse, shift, dump

with open("movie.srt", encoding="utf-8-sig") as f:
    cues = parse(f.read())

fixed = shift(cues, 2500)  # +2.5s

with open("movie-fixed.srt", "w", encoding="utf-8") as f:
    f.write(dump(fixed))
```

`Cue` is a plain dataclass with `index`, `start_ms`, `end_ms`, and `text`, so
it's easy to filter, merge, or rewrite cues by hand before calling `dump`.

## Status

Handles well-formed .srt and WebVTT input, and writes .srt or .vtt output.
Can detect and auto-fix overlapping cues. Doesn't yet read .ass or .sub.
See the source for the full surface — it's under 400 lines.
