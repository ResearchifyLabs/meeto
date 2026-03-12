import os
import unittest
from unittest.mock import patch

from meeto.config.env_config import worker_config_from_env


class TestWorkerConfigFromEnv(unittest.TestCase):
    _BASE_ENV = {
        "MEETING_ID": "m-123",
        "MEET_URL": "https://meet.google.com/abc-defg-hij",
    }

    def _call_with_env(self, extra_env=None):
        env = dict(self._BASE_ENV)
        if extra_env:
            env.update(extra_env)
        with patch.dict(os.environ, env, clear=True):
            return worker_config_from_env()

    def test_required_fields(self):
        cfg = self._call_with_env()
        self.assertEqual(cfg.meeting_id, "m-123")
        self.assertEqual(cfg.meet_url, "https://meet.google.com/abc-defg-hij")

    def test_missing_meeting_id_raises(self):
        with (
            patch.dict(os.environ, {"MEET_URL": "https://meet.google.com/x"}, clear=True),
            self.assertRaises(KeyError),
        ):
            worker_config_from_env()

    def test_missing_meet_url_raises(self):
        with (
            patch.dict(os.environ, {"MEETING_ID": "m1"}, clear=True),
            self.assertRaises(KeyError),
        ):
            worker_config_from_env()

    def test_defaults(self):
        cfg = self._call_with_env()
        self.assertEqual(cfg.duration_seconds, 3600)
        self.assertEqual(cfg.audio.sample_rate, 16000)
        self.assertEqual(cfg.audio.chunk_ms, 20)
        self.assertFalse(cfg.audio.debug)
        self.assertTrue(cfg.audio.dump_enabled)
        self.assertIsNone(cfg.stt.provider)
        self.assertIsNone(cfg.stt.api_key)
        self.assertEqual(cfg.stt.diarization, "dom")
        self.assertEqual(cfg.stt.connect_retries, 4)
        self.assertTrue(cfg.join.headless)
        self.assertIsNone(cfg.join.storage_state_path)

    def test_custom_values(self):
        cfg = self._call_with_env(
            {
                "DURATION_SECONDS": "600",
                "AUDIO_SAMPLE_RATE": "48000",
                "AUDIO_CHUNK_MS": "40",
                "AUDIO_DEBUG": "true",
                "AUDIO_DUMP_ENABLED": "false",
                "STT_PROVIDER": "deepgram",
                "DEEPGRAM_API_KEY": "dg-key-123",
                "DIARIZATION": "correlation",
                "HEADLESS": "false",
                "MEET_STORAGE_STATE_PATH": "/tmp/state.json",
                "GMEET_STT_CONNECT_RETRIES": "2",
                "GMEET_STT_CONNECT_INITIAL_DELAY_S": "1.0",
                "GMEET_STT_CONNECT_MAX_DELAY_S": "10.0",
            }
        )
        self.assertEqual(cfg.duration_seconds, 600)
        self.assertEqual(cfg.audio.sample_rate, 48000)
        self.assertEqual(cfg.audio.chunk_ms, 40)
        self.assertTrue(cfg.audio.debug)
        self.assertFalse(cfg.audio.dump_enabled)
        self.assertEqual(cfg.stt.provider, "deepgram")
        self.assertEqual(cfg.stt.api_key, "dg-key-123")
        self.assertEqual(cfg.stt.diarization, "correlation")
        self.assertFalse(cfg.join.headless)
        self.assertEqual(cfg.join.storage_state_path, "/tmp/state.json")
        self.assertEqual(cfg.stt.connect_retries, 2)
        self.assertAlmostEqual(cfg.stt.connect_initial_delay_s, 1.0)
        self.assertAlmostEqual(cfg.stt.connect_max_delay_s, 10.0)

    def test_stt_config_json_parsed(self):
        cfg = self._call_with_env({"STT_CONFIG": '{"model": "nova-3"}'})
        self.assertEqual(cfg.stt.extra, {"model": "nova-3"})

    def test_empty_stt_provider_becomes_none(self):
        cfg = self._call_with_env({"STT_PROVIDER": ""})
        self.assertIsNone(cfg.stt.provider)

    def test_empty_api_key_becomes_none(self):
        cfg = self._call_with_env({"DEEPGRAM_API_KEY": ""})
        self.assertIsNone(cfg.stt.api_key)

    def test_empty_storage_state_becomes_none(self):
        cfg = self._call_with_env({"MEET_STORAGE_STATE_PATH": ""})
        self.assertIsNone(cfg.join.storage_state_path)
