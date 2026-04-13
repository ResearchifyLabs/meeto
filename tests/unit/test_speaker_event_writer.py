import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from meeto.speaker_event_writer import SpeakerEventWriter


class TestSpeakerEventWriter(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def _make_writer(self, **kwargs):
        defaults = dict(meeting_id="test-meeting", speaker_events_dir=self._tmpdir)
        defaults.update(kwargs)
        return SpeakerEventWriter(**defaults)

    def test_open_creates_file(self):
        w = self._make_writer()
        path = w.open()
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith("_speakers.jsonl"))
        w.close()

    def test_open_writes_metadata_header(self):
        w = self._make_writer(meeting_id="m123")
        path = w.open()
        w.close()
        with open(path) as f:
            line = json.loads(f.readline())
        self.assertEqual(line["type"], "metadata")
        self.assertEqual(line["meeting_id"], "m123")
        self.assertIn("created_at", line)

    def test_write_event_appends_jsonl(self):
        w = self._make_writer()
        w.open()
        w.write_event("Alice", 1000.0, True, stream_id="stream_1", detection="audio+name")
        w.write_event("Alice", 1005.0, False)
        w.write_event("Bob", 1006.0, True, stream_id="stream_2", detection="audio+name")
        w.close()
        with open(w.filepath) as f:
            lines = [json.loads(line) for line in f]
        self.assertEqual(len(lines), 4)
        self.assertEqual(lines[0]["type"], "metadata")
        self.assertEqual(lines[1]["type"], "speaker_event")
        self.assertEqual(lines[1]["speaker"], "Alice")
        self.assertEqual(lines[1]["timestamp"], 1000.0)
        self.assertTrue(lines[1]["is_speaking"])
        self.assertEqual(lines[1]["stream_id"], "stream_1")
        self.assertEqual(lines[1]["detection"], "audio+name")
        self.assertFalse(lines[2]["is_speaking"])
        self.assertEqual(lines[3]["speaker"], "Bob")

    def test_write_event_before_open_is_noop(self):
        w = self._make_writer()
        w.write_event("Alice", 1000.0, True)
        self.assertIsNone(w.filepath)

    def test_event_fields_are_complete(self):
        w = self._make_writer()
        w.open()
        w.write_event("Charlie", 1234.5, True, stream_id="stream_3", detection="audio+name")
        w.close()
        with open(w.filepath) as f:
            lines = [json.loads(line) for line in f]
        rec = lines[1]
        self.assertEqual(rec["speaker"], "Charlie")
        self.assertEqual(rec["timestamp"], 1234.5)
        self.assertTrue(rec["is_speaking"])
        self.assertEqual(rec["stream_id"], "stream_3")
        self.assertEqual(rec["detection"], "audio+name")
        self.assertIn("wall_time", rec)

    def test_close_returns_local_path(self):
        w = self._make_writer()
        w.open()
        result = w.close()
        self.assertIsNotNone(result["local_path"])
        self.assertIsNone(result["remote_path"])

    def test_close_with_storage_adapter(self):
        adapter = MagicMock()
        adapter.upload.return_value = "gs://bucket/speakers.jsonl"
        w = self._make_writer(storage_adapter=adapter)
        w.open()
        result = w.close()
        adapter.upload.assert_called_once()
        self.assertEqual(result["remote_path"], "gs://bucket/speakers.jsonl")

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

    def test_none_speaker_name(self):
        w = self._make_writer()
        w.open()
        w.write_event(None, 1000.0, False)
        w.close()
        with open(w.filepath) as f:
            lines = [json.loads(line) for line in f]
        self.assertEqual(lines[1]["speaker"], None)
