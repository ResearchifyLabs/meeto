import json
import os
import tempfile
import unittest
from unittest.mock import MagicMock

from meeto.manifest_writer import ManifestWriter


class TestManifestWriter(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.mkdtemp()

    def _make_writer(self, **kwargs):
        defaults = dict(meeting_id="test-meeting", manifests_dir=self._tmpdir)
        defaults.update(kwargs)
        return ManifestWriter(**defaults)

    def test_open_creates_file_path(self):
        w = self._make_writer()
        path = w.open()
        self.assertTrue(path.endswith("_manifest.json"))
        w.close()

    def test_add_participant_and_close_writes_json(self):
        w = self._make_writer(meeting_id="m1")
        w.open()
        w.add_participant(
            "pid1",
            display_name="Alice",
            email="alice@example.com",
            avatar_url="https://img/alice",
            first_seen_at=1000.0,
        )
        result = w.close()
        with open(result["local_path"]) as f:
            manifest = json.load(f)
        self.assertEqual(manifest["meeting_id"], "m1")
        self.assertEqual(len(manifest["participants"]), 1)
        p = manifest["participants"][0]
        self.assertEqual(p["participant_id"], "pid1")
        self.assertEqual(p["display_name"], "Alice")
        self.assertEqual(p["email"], "alice@example.com")

    def test_add_participant_updates_existing(self):
        w = self._make_writer()
        w.open()
        w.add_participant("pid1", display_name="Alice")
        w.add_participant("pid1", email="alice@example.com")
        result = w.close()
        with open(result["local_path"]) as f:
            manifest = json.load(f)
        p = manifest["participants"][0]
        self.assertEqual(p["display_name"], "Alice")
        self.assertEqual(p["email"], "alice@example.com")

    def test_multiple_participants(self):
        w = self._make_writer()
        w.open()
        w.add_participant("pid1", display_name="Alice")
        w.add_participant("pid2", display_name="Bob")
        result = w.close()
        with open(result["local_path"]) as f:
            manifest = json.load(f)
        self.assertEqual(len(manifest["participants"]), 2)

    def test_close_returns_local_path(self):
        w = self._make_writer()
        w.open()
        result = w.close()
        self.assertIsNotNone(result["local_path"])
        self.assertIsNone(result["remote_path"])

    def test_close_with_storage_adapter(self):
        adapter = MagicMock()
        adapter.upload.return_value = "gs://bucket/manifest.json"
        w = self._make_writer(storage_adapter=adapter)
        w.open()
        result = w.close()
        adapter.upload.assert_called_once()
        self.assertEqual(result["remote_path"], "gs://bucket/manifest.json")

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

    def test_participants_property(self):
        w = self._make_writer()
        w.open()
        w.add_participant("pid1", display_name="Alice")
        self.assertIn("pid1", w.participants)
        w.close()

    def test_close_before_open_returns_nones(self):
        w = self._make_writer()
        result = w.close()
        self.assertIsNone(result["local_path"])
        self.assertIsNone(result["remote_path"])
