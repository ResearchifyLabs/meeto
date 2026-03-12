import unittest
from unittest.mock import MagicMock

from meeto.meet.speaker_attribution import (
    CorrelationSpeakerAttribution,
    SpeakerCorrelationMap,
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

    def test_correlation_requires_page(self):
        with self.assertRaises(ValueError):
            create_speaker_attribution("correlation")

    def test_factory_creates_correlation(self):
        page = MagicMock()
        attr = create_speaker_attribution("correlation", page=page)
        self.assertIsInstance(attr, CorrelationSpeakerAttribution)


def _make_segment(speaker: str = None, text: str = "hello") -> TranscriptSegment:
    return TranscriptSegment(
        text=text,
        seq=1,
        ts_start=0.0,
        ts_end=1.0,
        speaker=speaker,
        is_final=True,
        confidence=0.9,
        lang="en",
        payload={},
    )


class TestSpeakerCorrelationMap(unittest.TestCase):
    def test_resolve_returns_none_before_threshold(self):
        m = SpeakerCorrelationMap(confidence_threshold=3)
        m.record_vote("0", "Shivansh")
        m.record_vote("0", "Shivansh")
        self.assertIsNone(m.resolve("0"))

    def test_resolve_returns_name_at_threshold(self):
        m = SpeakerCorrelationMap(confidence_threshold=3)
        for _ in range(3):
            m.record_vote("0", "Shivansh")
        self.assertEqual(m.resolve("0"), "Shivansh")

    def test_majority_wins_with_mixed_votes(self):
        m = SpeakerCorrelationMap(confidence_threshold=3)
        for _ in range(5):
            m.record_vote("0", "Muskan")
        for _ in range(2):
            m.record_vote("0", "Shivansh")
        self.assertEqual(m.resolve("0"), "Muskan")

    def test_multiple_labels_independent(self):
        m = SpeakerCorrelationMap(confidence_threshold=3)
        for _ in range(3):
            m.record_vote("0", "Shivansh")
            m.record_vote("1", "Muskan")
        self.assertEqual(m.resolve("0"), "Shivansh")
        self.assertEqual(m.resolve("1"), "Muskan")

    def test_mapping_updates_on_drift(self):
        m = SpeakerCorrelationMap(confidence_threshold=3)
        for _ in range(3):
            m.record_vote("0", "Shivansh")
        self.assertEqual(m.resolve("0"), "Shivansh")
        for _ in range(5):
            m.record_vote("0", "Muskan")
        self.assertEqual(m.resolve("0"), "Muskan")

    def test_ignores_empty_label_or_name(self):
        m = SpeakerCorrelationMap(confidence_threshold=3)
        m.record_vote("", "Shivansh")
        m.record_vote("0", "")
        m.record_vote(None, "Shivansh")
        m.record_vote("0", None)
        self.assertEqual(m.resolved_map, {})

    def test_resolve_none_label(self):
        m = SpeakerCorrelationMap()
        self.assertIsNone(m.resolve(None))


class TestCorrelationSpeakerAttribution(unittest.TestCase):
    def test_returns_speaker_label_before_confidence(self):
        attr = CorrelationSpeakerAttribution(page=MagicMock())
        segment = _make_segment(speaker="2")
        result = attr.get_speaker_for_segment(segment)
        self.assertEqual(result, "Speaker 2")

    def test_returns_resolved_name_after_votes(self):
        attr = CorrelationSpeakerAttribution(page=MagicMock())
        attr._active_speaker = "Muskan Dhadda"
        for _ in range(3):
            attr.get_speaker_for_segment(_make_segment(speaker="2"))
        result = attr.get_speaker_for_segment(_make_segment(speaker="2"))
        self.assertEqual(result, "Muskan Dhadda")

    def test_records_vote_on_segment(self):
        attr = CorrelationSpeakerAttribution(page=MagicMock())
        attr._active_speaker = "Shivansh"
        attr.get_speaker_for_segment(_make_segment(speaker="0"))
        votes = attr.correlation_map._votes
        self.assertEqual(votes["0"]["Shivansh"], 1)

    def test_returns_active_speaker_when_no_label(self):
        attr = CorrelationSpeakerAttribution(page=MagicMock())
        attr._active_speaker = "Shivansh"
        result = attr.get_speaker_for_segment(_make_segment(speaker=None))
        self.assertEqual(result, "Shivansh")

    def test_interim_segments_do_not_record_votes(self):
        attr = CorrelationSpeakerAttribution(page=MagicMock())
        attr._active_speaker = "Shivansh"
        interim = TranscriptSegment(
            text="hello",
            seq=1,
            ts_start=0.0,
            ts_end=1.0,
            speaker="0",
            is_final=False,
            confidence=0.9,
            lang="en",
            payload={},
        )
        attr.get_speaker_for_segment(interim)
        self.assertEqual(attr.correlation_map._votes, {})
