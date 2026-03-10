import unittest

from meeto.meet.speaker_attribution import (
    STTDiarizationAttribution,
    create_speaker_attribution,
)
from meeto.stt.base import TranscriptSegment


class TestSTTDiarizationAttribution(unittest.TestCase):
    def test_returns_segment_speaker(self):
        attr = STTDiarizationAttribution()
        segment = TranscriptSegment(
            text="hello",
            seq=1,
            ts_start=0.0,
            ts_end=1.0,
            speaker="Speaker 0",
            is_final=True,
            confidence=0.9,
            lang="en",
            payload={},
        )
        self.assertEqual(attr.get_speaker_for_segment(segment), "Speaker 0")

    def test_returns_none_when_no_speaker(self):
        attr = STTDiarizationAttribution()
        segment = TranscriptSegment(
            text="hello",
            seq=1,
            ts_start=0.0,
            ts_end=1.0,
            speaker=None,
            is_final=True,
            confidence=0.9,
            lang="en",
            payload={},
        )
        self.assertIsNone(attr.get_speaker_for_segment(segment))


class TestCreateSpeakerAttribution(unittest.TestCase):
    def test_stt_native_no_page_needed(self):
        attr = create_speaker_attribution("stt_native")
        self.assertIsInstance(attr, STTDiarizationAttribution)

    def test_unknown_strategy_raises(self):
        with self.assertRaises(ValueError) as ctx:
            create_speaker_attribution("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))

    def test_dom_requires_page(self):
        with self.assertRaises(ValueError):
            create_speaker_attribution("dom")

    def test_hybrid_requires_page(self):
        with self.assertRaises(ValueError):
            create_speaker_attribution("hybrid")
