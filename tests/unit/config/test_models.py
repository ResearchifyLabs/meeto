import unittest

from meeto.config.models import AudioConfig, JoinConfig, SttConfig, WorkerConfig


class TestAudioConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = AudioConfig()
        self.assertEqual(cfg.sample_rate, 16000)
        self.assertEqual(cfg.chunk_ms, 20)
        self.assertFalse(cfg.debug)
        self.assertTrue(cfg.dump_enabled)

    def test_custom_values(self):
        cfg = AudioConfig(sample_rate=48000, chunk_ms=40, debug=True, dump_enabled=False)
        self.assertEqual(cfg.sample_rate, 48000)
        self.assertEqual(cfg.chunk_ms, 40)
        self.assertTrue(cfg.debug)
        self.assertFalse(cfg.dump_enabled)


class TestSttConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = SttConfig()
        self.assertIsNone(cfg.provider)
        self.assertIsNone(cfg.api_key)
        self.assertEqual(cfg.diarization, "dom")
        self.assertEqual(cfg.extra, {})
        self.assertEqual(cfg.connect_retries, 4)

    def test_extra_is_independent(self):
        a = SttConfig()
        b = SttConfig()
        a.extra["key"] = "value"
        self.assertNotIn("key", b.extra)


class TestJoinConfig(unittest.TestCase):
    def test_defaults(self):
        cfg = JoinConfig()
        self.assertTrue(cfg.headless)
        self.assertIsNone(cfg.storage_state_path)
        self.assertTrue(cfg.disable_mic)
        self.assertTrue(cfg.disable_camera)
        self.assertEqual(cfg.join_timeout_ms, 90000)


class TestWorkerConfig(unittest.TestCase):
    def test_required_fields(self):
        cfg = WorkerConfig(meeting_id="m1", meet_url="https://meet.google.com/abc-def-ghi")
        self.assertEqual(cfg.meeting_id, "m1")
        self.assertEqual(cfg.meet_url, "https://meet.google.com/abc-def-ghi")
        self.assertEqual(cfg.duration_seconds, 3600)

    def test_nested_defaults_are_independent(self):
        a = WorkerConfig(meeting_id="a", meet_url="u")
        b = WorkerConfig(meeting_id="b", meet_url="u")
        a.audio.sample_rate = 8000
        self.assertEqual(b.audio.sample_rate, 16000)
