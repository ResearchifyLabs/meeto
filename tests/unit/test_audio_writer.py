import os
import tempfile
import unittest
from unittest.mock import MagicMock

from meeto.audio_writer import AudioDumpWriter


class TestAudioDumpWriter(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def _make_writer(self, **kwargs):
        defaults = dict(meeting_id="test-audio", audio_dir=self._tmpdir)
        defaults.update(kwargs)
        return AudioDumpWriter(**defaults)

    def test_open_creates_file(self):
        w = self._make_writer()
        path = w.open()
        self.assertTrue(os.path.exists(path))
        self.assertTrue(path.endswith(".pcm"))
        w.close()

    def test_write_chunk_writes_bytes(self):
        w = self._make_writer()
        w.open()
        w.write_chunk(b"\x00\x01" * 100)
        w.write_chunk(b"\x02\x03" * 50)
        result = w.close()
        self.assertEqual(result["bytes_written"], 300)
        with open(w.filepath, "rb") as f:
            data = f.read()
        self.assertEqual(len(data), 300)

    def test_write_chunk_before_open_is_noop(self):
        w = self._make_writer()
        w.write_chunk(b"\x00\x01")
        self.assertEqual(w.bytes_written, 0)

    def test_write_chunk_empty_bytes_is_noop(self):
        w = self._make_writer()
        w.open()
        w.write_chunk(b"")
        self.assertEqual(w.bytes_written, 0)
        w.close()

    def test_close_returns_duration(self):
        w = self._make_writer(sample_rate=16000, channels=1)
        w.open()
        w.write_chunk(b"\x00" * 32000)
        result = w.close()
        self.assertEqual(result["duration_seconds"], 1.0)

    def test_close_returns_zero_duration_no_data(self):
        w = self._make_writer()
        w.open()
        result = w.close()
        self.assertEqual(result["bytes_written"], 0)
        self.assertEqual(result["duration_seconds"], 0)

    def test_close_returns_local_path(self):
        w = self._make_writer()
        w.open()
        result = w.close()
        self.assertIsNotNone(result["local_path"])
        self.assertIsNone(result["remote_path"])

    def test_close_with_storage_adapter(self):
        adapter = MagicMock()
        adapter.upload.return_value = "gs://bucket/audio.pcm"
        w = self._make_writer(storage_adapter=adapter)
        w.open()
        w.write_chunk(b"\x00" * 100)
        result = w.close()
        adapter.upload.assert_called_once()
        self.assertEqual(result["remote_path"], "gs://bucket/audio.pcm")

    def test_meeting_id_with_slashes_sanitized(self):
        w = self._make_writer(meeting_id="org/meet/1")
        path = w.open()
        self.assertIn("org_meet_1", os.path.basename(path))
        w.close()

    def test_bytes_written_property(self):
        w = self._make_writer()
        self.assertEqual(w.bytes_written, 0)
        w.open()
        w.write_chunk(b"\x00" * 50)
        self.assertEqual(w.bytes_written, 50)
        w.close()

    def test_filepath_property(self):
        w = self._make_writer()
        self.assertIsNone(w.filepath)
        w.open()
        self.assertIsNotNone(w.filepath)
        w.close()
