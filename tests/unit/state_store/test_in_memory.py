import unittest

from meeto.state_store.in_memory import InMemoryMeetingLifecycleStore


class TestInMemoryMeetingLifecycleStore(unittest.TestCase):
    def setUp(self):
        self.store = InMemoryMeetingLifecycleStore()

    def test_create_meeting(self):
        result = self.store.create_meeting("m1", status="joining")
        self.assertEqual(result["meeting_id"], "m1")
        self.assertEqual(result["status"], "joining")
        self.assertIn("created_at", result)
        self.assertIn("updated_at", result)

    def test_create_preserves_created_at(self):
        first = self.store.create_meeting("m1")
        created = first["created_at"]
        second = self.store.create_meeting("m1", status="active")
        self.assertEqual(second["created_at"], created)

    def test_update_status(self):
        self.store.create_meeting("m1")
        self.store.update_status("m1", status="ended", ended_at=999.0)
        meeting = self.store.get_meeting("m1")
        self.assertEqual(meeting["status"], "ended")
        self.assertEqual(meeting["ended_at"], 999.0)

    def test_update_status_with_transcription_path(self):
        self.store.create_meeting("m1")
        self.store.update_status("m1", status="done", transcription_path="/tmp/t.jsonl")
        meeting = self.store.get_meeting("m1")
        self.assertEqual(meeting["transcription_path"], "/tmp/t.jsonl")

    def test_heartbeat(self):
        self.store.create_meeting("m1")
        self.store.heartbeat("m1", worker_id="w1")
        meeting = self.store.get_meeting("m1")
        self.assertIn("last_heartbeat_at", meeting)
        self.assertEqual(meeting["worker_id"], "w1")

    def test_get_meeting_returns_none_for_unknown(self):
        self.assertIsNone(self.store.get_meeting("unknown"))

    def test_get_meeting_returns_copy(self):
        self.store.create_meeting("m1")
        a = self.store.get_meeting("m1")
        b = self.store.get_meeting("m1")
        a["foo"] = "bar"
        self.assertNotIn("foo", b)
