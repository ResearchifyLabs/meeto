import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from meeto.stt.base import TranscriptSegment
from meeto.transcript_writer import TranscriptWriter


def _make_segment(**overrides) -> TranscriptSegment:
    defaults = dict(
        text="hello world",
        seq=1,
        ts_start=0.5,
        ts_end=1.5,
        speaker="0",
        is_final=True,
        confidence=0.95,
        lang="en",
        payload={},
    )
    defaults.update(overrides)
    return TranscriptSegment(**defaults)


class TestTranscriptWriter(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def _make_writer(self, **kwargs):
        defaults = dict(meeting_id="test-meeting", transcript_dir=self._tmpdir)
        defaults.update(kwargs)
        return TranscriptWriter(**defaults)

    def test_open_creates_file(self):
        w = self._make_writer()
        path = w.open()
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".jsonl"))
        w.close()

    def test_open_writes_metadata_header(self):
        w = self._make_writer(meeting_id="m123", stt_provider="deepgram")
        path = w.open()
        w.close()
        with open(path) as f:
            line = json.loads(f.readline())
        self.assertEqual(line["type"], "metadata")
        self.assertEqual(line["meeting_id"], "m123")
        self.assertEqual(line["stt_provider"], "deepgram")
        self.assertIn("created_at", line)
        self.assertIn("sample_rate", line)

    def test_write_segment_appends_jsonl(self):
        w = self._make_writer()
        w.open()
        w.write_segment(_make_segment(text="first"), speaker_name="Alice")
        w.write_segment(_make_segment(text="second"), speaker_name="Bob")
        w.close()
        with open(w.filepath) as f:
            lines = [json.loads(line) for line in f]
        self.assertEqual(len(lines), 3)
        self.assertEqual(lines[0]["type"], "metadata")
        self.assertEqual(lines[1]["type"], "segment")
        self.assertEqual(lines[1]["text"], "first")
        self.assertEqual(lines[1]["speaker"], "Alice")
        self.assertEqual(lines[2]["text"], "second")
        self.assertEqual(lines[2]["speaker"], "Bob")

    def test_write_segment_before_open_is_noop(self):
        w = self._make_writer()
        w.write_segment(_make_segment())
        self.assertIsNone(w.filepath)

    def test_segment_fields_are_complete(self):
        w = self._make_writer()
        w.open()
        seg = _make_segment(seq=5, ts_start=1.0, ts_end=2.0, speaker="2", confidence=0.88, lang="en")
        w.write_segment(seg, speaker_name="Charlie")
        w.close()
        with open(w.filepath) as f:
            lines = [json.loads(line) for line in f]
        rec = lines[1]
        self.assertEqual(rec["seq"], 5)
        self.assertEqual(rec["ts_start"], 1.0)
        self.assertEqual(rec["ts_end"], 2.0)
        self.assertEqual(rec["diarized_speaker"], "2")
        self.assertEqual(rec["speaker"], "Charlie")
        self.assertTrue(rec["is_final"])
        self.assertEqual(rec["confidence"], 0.88)
        self.assertEqual(rec["lang"], "en")
        self.assertIn("timestamp", rec)

    def test_close_returns_local_path(self):
        w = self._make_writer()
        w.open()
        result = w.close()
        self.assertIsNotNone(result["local_path"])
        self.assertIsNone(result["remote_path"])

    def test_close_with_storage_adapter(self):
        adapter = MagicMock()
        adapter.upload.return_value = "gs://bucket/transcript.jsonl"
        w = self._make_writer(storage_adapter=adapter)
        w.open()
        result = w.close()
        adapter.upload.assert_called_once()
        self.assertEqual(result["remote_path"], "gs://bucket/transcript.jsonl")

    def test_meeting_id_with_slashes_sanitized(self):
        w = self._make_writer(meeting_id="org/meeting/123")
        path = w.open()
        self.assertIn("org_meeting_123", os.path.basename(path))
        w.close()

    def test_filepath_property(self):
        w = self._make_writer()
        self.assertIsNone(w.filepath)
        w.open()
        self.assertIsNotNone(w.filepath)
        w.close()
