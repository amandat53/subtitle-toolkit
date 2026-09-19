import unittest

from subtl import (
    Cue,
    SubtitleError,
    dump,
    find_overlaps,
    fix_overlaps,
    format_timestamp,
    frames_to_ms,
    parse,
    parse_any,
    parse_ass,
    parse_ass_timestamp,
    parse_timestamp,
    parse_vtt,
    parse_vtt_timestamp,
    shift,
    to_vtt,
)

SAMPLE_SRT = """1
00:00:01,000 --> 00:00:02,500
Hello there.

2
00:00:03,250 --> 00:00:04,000
Second line, first.
Second line, second.
"""


class TimestampTests(unittest.TestCase):
    def test_parse_timestamp_comma(self):
        self.assertEqual(parse_timestamp("00:00:01,000"), 1000)

    def test_parse_timestamp_dot(self):
        self.assertEqual(parse_timestamp("00:00:01.000"), 1000)

    def test_parse_timestamp_hours_and_millis(self):
        self.assertEqual(parse_timestamp("01:02:03,456"), 3723456)

    def test_parse_timestamp_rejects_garbage(self):
        with self.assertRaises(SubtitleError):
            parse_timestamp("not a timestamp")

    def test_format_timestamp_round_trip(self):
        for ms in (0, 1000, 61_500, 3_723_456):
            self.assertEqual(parse_timestamp(format_timestamp(ms)), ms)

    def test_format_timestamp_clamps_negative(self):
        self.assertEqual(format_timestamp(-500), "00:00:00,000")

    def test_format_timestamp_custom_separator(self):
        self.assertEqual(format_timestamp(1000, sep="."), "00:00:01.000")


class ParseTests(unittest.TestCase):
    def test_parse_basic(self):
        cues = parse(SAMPLE_SRT)
        self.assertEqual(len(cues), 2)
        self.assertEqual(cues[0], Cue(index=1, start_ms=1000, end_ms=2500, text="Hello there."))
        self.assertEqual(
            cues[1],
            Cue(index=2, start_ms=3250, end_ms=4000,
                text="Second line, first.\nSecond line, second."),
        )

    def test_parse_renumbers_sequentially(self):
        # Indices in the file are ignored in favor of position in the file.
        text = "5\n00:00:01,000 --> 00:00:02,000\nA\n\n9\n00:00:02,000 --> 00:00:03,000\nB\n"
        cues = parse(text)
        self.assertEqual([c.index for c in cues], [1, 2])

    def test_parse_without_index_line(self):
        text = "00:00:01,000 --> 00:00:02,000\nNo index here.\n"
        cues = parse(text)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].text, "No index here.")

    def test_parse_missing_timestamp_raises(self):
        with self.assertRaises(SubtitleError):
            parse("1\njust some text\nmore text\n")

    def test_parse_empty_input(self):
        self.assertEqual(parse(""), [])

    def test_parse_ignores_blank_blocks(self):
        text = "1\n00:00:01,000 --> 00:00:02,000\nA\n\n\n\n2\n00:00:02,000 --> 00:00:03,000\nB\n"
        cues = parse(text)
        self.assertEqual(len(cues), 2)


class DumpRoundTripTests(unittest.TestCase):
    def test_round_trip_preserves_timing_and_text(self):
        original = parse(SAMPLE_SRT)
        reparsed = parse(dump(original))
        self.assertEqual(original, reparsed)

    def test_dump_renumbers_from_one(self):
        cues = [
            Cue(index=7, start_ms=0, end_ms=1000, text="A"),
            Cue(index=8, start_ms=1000, end_ms=2000, text="B"),
        ]
        reparsed = parse(dump(cues))
        self.assertEqual([c.index for c in reparsed], [1, 2])

    def test_dump_empty_list(self):
        self.assertEqual(dump([]), "\n")

    def test_dump_multiline_text_round_trips(self):
        cues = [Cue(index=1, start_ms=0, end_ms=1000, text="line one\nline two")]
        reparsed = parse(dump(cues))
        self.assertEqual(reparsed[0].text, "line one\nline two")

    def test_round_trip_is_stable_under_repetition(self):
        # Dumping and reparsing twice should land on the same result as once.
        once = dump(parse(SAMPLE_SRT))
        twice = dump(parse(once))
        self.assertEqual(once, twice)


class VttTests(unittest.TestCase):
    def test_parse_vtt_requires_header(self):
        with self.assertRaises(SubtitleError):
            parse_vtt("00:00:01.000 --> 00:00:02.000\nHi\n")

    def test_parse_vtt_basic(self):
        text = "WEBVTT\n\n00:00:01.000 --> 00:00:02.500\nHello there.\n"
        cues = parse_vtt(text)
        self.assertEqual(cues, [Cue(index=1, start_ms=1000, end_ms=2500, text="Hello there.")])

    def test_parse_vtt_timestamp_without_hours(self):
        self.assertEqual(parse_vtt_timestamp("01:02.500"), 62500)

    def test_parse_vtt_skips_notes(self):
        text = "WEBVTT\n\nNOTE this is a comment\n\n00:00:01.000 --> 00:00:02.000\nHi\n"
        cues = parse_vtt(text)
        self.assertEqual(len(cues), 1)

    def test_to_vtt_then_parse_vtt_round_trips(self):
        original = parse(SAMPLE_SRT)
        reparsed = parse_vtt(to_vtt(original))
        self.assertEqual(
            [(c.start_ms, c.end_ms, c.text) for c in original],
            [(c.start_ms, c.end_ms, c.text) for c in reparsed],
        )

    def test_parse_any_detects_vtt(self):
        text = "WEBVTT\n\n00:00:01.000 --> 00:00:02.000\nHi\n"
        cues = parse_any(text)
        self.assertEqual(cues[0].text, "Hi")

    def test_parse_any_detects_srt(self):
        cues = parse_any(SAMPLE_SRT)
        self.assertEqual(len(cues), 2)


class ShiftTests(unittest.TestCase):
    def test_shift_positive(self):
        cues = parse(SAMPLE_SRT)
        shifted = shift(cues, 500)
        self.assertEqual(shifted[0].start_ms, 1500)
        self.assertEqual(shifted[0].end_ms, 3000)

    def test_shift_clamps_at_zero(self):
        cues = [Cue(index=1, start_ms=200, end_ms=800, text="A")]
        shifted = shift(cues, -1000)
        self.assertEqual(shifted[0].start_ms, 0)
        self.assertEqual(shifted[0].end_ms, 0)

    def test_shift_does_not_mutate_input(self):
        cues = parse(SAMPLE_SRT)
        original_start = cues[0].start_ms
        shift(cues, 500)
        self.assertEqual(cues[0].start_ms, original_start)

    def test_frames_to_ms(self):
        self.assertEqual(frames_to_ms(25, 25), 1000)

    def test_frames_to_ms_rejects_nonpositive_fps(self):
        with self.assertRaises(ValueError):
            frames_to_ms(1, 0)


class OverlapTests(unittest.TestCase):
    def test_find_overlaps_none(self):
        cues = parse(SAMPLE_SRT)
        self.assertEqual(find_overlaps(cues), [])

    def test_find_overlaps_detects_pair(self):
        cues = [
            Cue(index=1, start_ms=0, end_ms=2000, text="A"),
            Cue(index=2, start_ms=1000, end_ms=3000, text="B"),
        ]
        overlaps = find_overlaps(cues)
        self.assertEqual(len(overlaps), 1)
        self.assertEqual((overlaps[0][0].index, overlaps[0][1].index), (1, 2))

    def test_fix_overlaps_trims_end_time(self):
        cues = [
            Cue(index=1, start_ms=0, end_ms=2000, text="A"),
            Cue(index=2, start_ms=1000, end_ms=3000, text="B"),
        ]
        fixed = fix_overlaps(cues)
        self.assertEqual(fixed[0].end_ms, 1000)
        self.assertEqual(fixed[1].start_ms, 1000)
        self.assertEqual(find_overlaps(fixed), [])

    def test_fix_overlaps_preserves_list_order(self):
        cues = [
            Cue(index=1, start_ms=1000, end_ms=3000, text="B"),
            Cue(index=2, start_ms=0, end_ms=2000, text="A"),
        ]
        fixed = fix_overlaps(cues)
        self.assertEqual([c.text for c in fixed], ["B", "A"])

    def test_fix_overlaps_chains_across_multiple_cues(self):
        cues = [
            Cue(index=1, start_ms=0, end_ms=5000, text="A"),
            Cue(index=2, start_ms=1000, end_ms=2000, text="B"),
            Cue(index=3, start_ms=1500, end_ms=2500, text="C"),
        ]
        fixed = fix_overlaps(cues)
        self.assertEqual(find_overlaps(fixed), [])


ASS_HEADER = """[Script Info]
Title: Example

[V4+ Styles]
Format: Name, Fontname, Fontsize
Style: Default,Arial,20

"""


class AssTests(unittest.TestCase):
    def test_parse_ass_timestamp(self):
        self.assertEqual(parse_ass_timestamp("0:00:01.50"), 1500)

    def test_parse_ass_timestamp_hours(self):
        self.assertEqual(parse_ass_timestamp("1:02:03.45"), 3723450)

    def test_parse_ass_timestamp_rejects_garbage(self):
        with self.assertRaises(SubtitleError):
            parse_ass_timestamp("not a timestamp")

    def test_parse_ass_basic(self):
        text = ASS_HEADER + (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.50,Default,,0,0,0,,Hello there!\n"
        )
        cues = parse_ass(text)
        self.assertEqual(cues, [Cue(index=1, start_ms=1000, end_ms=2500, text="Hello there!")])

    def test_parse_ass_keeps_commas_in_text_field(self):
        text = ASS_HEADER + (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Second line, with a comma.\n"
        )
        cues = parse_ass(text)
        self.assertEqual(cues[0].text, "Second line, with a comma.")

    def test_parse_ass_honors_ssa_field_order(self):
        # Old-style SSA uses "Marked" instead of "Layer" as the first field.
        text = ASS_HEADER + (
            "[Events]\n"
            "Format: Marked, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: Marked=0,0:00:01.00,0:00:02.00,Default,,0000,0000,0000,,Hi\n"
        )
        cues = parse_ass(text)
        self.assertEqual(cues[0].text, "Hi")

    def test_parse_ass_strips_override_tags(self):
        text = ASS_HEADER + (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,{\\an8}Top of screen.\n"
        )
        cues = parse_ass(text)
        self.assertEqual(cues[0].text, "Top of screen.")

    def test_parse_ass_converts_forced_line_breaks(self):
        text = ASS_HEADER + (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Line one\\NLine two\n"
        )
        cues = parse_ass(text)
        self.assertEqual(cues[0].text, "Line one\nLine two")

    def test_parse_ass_skips_comment_lines(self):
        text = ASS_HEADER + (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Comment: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,not shown\n"
            "Dialogue: 0,0:00:03.00,0:00:04.00,Default,,0,0,0,,shown\n"
        )
        cues = parse_ass(text)
        self.assertEqual(len(cues), 1)
        self.assertEqual(cues[0].text, "shown")

    def test_parse_ass_requires_events_section(self):
        with self.assertRaises(SubtitleError):
            parse_ass(ASS_HEADER)

    def test_parse_ass_dialogue_before_format_raises(self):
        text = (
            "[Events]\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hi\n"
        )
        with self.assertRaises(SubtitleError):
            parse_ass(text)

    def test_parse_any_detects_ass(self):
        text = ASS_HEADER + (
            "[Events]\n"
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
            "Dialogue: 0,0:00:01.00,0:00:02.00,Default,,0,0,0,,Hi\n"
        )
        cues = parse_any(text)
        self.assertEqual(cues[0].text, "Hi")


if __name__ == "__main__":
    unittest.main()
