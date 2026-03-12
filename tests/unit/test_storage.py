import os
import tempfile
import unittest

from meeto.storage import LocalStorageAdapter


class TestLocalStorageAdapter(unittest.TestCase):
    def setUp(self):
        self._adapter = LocalStorageAdapter()

    def test_upload_returns_absolute_path(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".txt") as f:
            f.write(b"test data")
            path = f.name
        try:
            result = self._adapter.upload(path)
            self.assertEqual(result, os.path.abspath(path))
        finally:
            os.unlink(path)

    def test_upload_nonexistent_file_returns_none(self):
        result = self._adapter.upload("/tmp/nonexistent_file_abc123.txt")
        self.assertIsNone(result)

    def test_upload_with_content_type_still_works(self):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pcm") as f:
            f.write(b"\x00" * 10)
            path = f.name
        try:
            result = self._adapter.upload(path, content_type="audio/pcm")
            self.assertIsNotNone(result)
        finally:
            os.unlink(path)
