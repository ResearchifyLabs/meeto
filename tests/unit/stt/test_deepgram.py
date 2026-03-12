import unittest

from meeto.stt.deepgram import DeepgramStreamingAdapter


class TestDeepgramBuildWsUrl(unittest.TestCase):
    def test_default_params(self):
        adapter = DeepgramStreamingAdapter(api_key="test")
        url = adapter._build_ws_url()
        self.assertIn("wss://api.deepgram.com/v1/listen", url)
        self.assertIn("sample_rate=16000", url)
        self.assertIn("channels=1", url)
        self.assertIn("diarize=true", url)
        self.assertIn("interim_results=true", url)

    def test_custom_sample_rate(self):
        adapter = DeepgramStreamingAdapter(api_key="test", sample_rate=48000, channels=2)
        url = adapter._build_ws_url()
        self.assertIn("sample_rate=48000", url)
        self.assertIn("channels=2", url)


class TestDeepgramParseMessage(unittest.TestCase):
    def _make_payload(self, transcript="hello", speaker=0, is_final=True):
        return {
            "type": "Results",
            "is_final": is_final,
            "channel": {
                "alternatives": [
                    {
                        "transcript": transcript,
                        "confidence": 0.95,
                        "language": "en",
                        "words": [
                            {"word": "hello", "start": 1.0, "end": 1.5, "speaker": speaker},
                        ],
                    }
                ]
            },
        }

    def test_parses_valid_result(self):
        seg = DeepgramStreamingAdapter._parse_message(self._make_payload(), seq=3)
        self.assertIsNotNone(seg)
        self.assertEqual(seg.text, "hello")
        self.assertEqual(seg.seq, 3)
        self.assertTrue(seg.is_final)
        self.assertEqual(seg.speaker, "0")
        self.assertEqual(seg.ts_start, 1.0)
        self.assertEqual(seg.ts_end, 1.5)
        self.assertEqual(seg.confidence, 0.95)
        self.assertEqual(seg.lang, "en")

    def test_ignores_non_results_type(self):
        seg = DeepgramStreamingAdapter._parse_message({"type": "Metadata"}, seq=0)
        self.assertIsNone(seg)

    def test_ignores_empty_transcript(self):
        payload = self._make_payload(transcript="")
        seg = DeepgramStreamingAdapter._parse_message(payload, seq=0)
        self.assertIsNone(seg)

    def test_ignores_whitespace_transcript(self):
        payload = self._make_payload(transcript="   ")
        seg = DeepgramStreamingAdapter._parse_message(payload, seq=0)
        self.assertIsNone(seg)

    def test_handles_no_alternatives(self):
        payload = {"type": "Results", "channel": {"alternatives": []}}
        seg = DeepgramStreamingAdapter._parse_message(payload, seq=0)
        self.assertIsNone(seg)

    def test_handles_no_words(self):
        payload = {
            "type": "Results",
            "is_final": True,
            "channel": {"alternatives": [{"transcript": "hello", "confidence": 0.9, "language": "en", "words": []}]},
        }
        seg = DeepgramStreamingAdapter._parse_message(payload, seq=0)
        self.assertIsNotNone(seg)
        self.assertIsNone(seg.speaker)
        self.assertIsNone(seg.ts_start)
        self.assertIsNone(seg.ts_end)

    def test_interim_result(self):
        seg = DeepgramStreamingAdapter._parse_message(self._make_payload(is_final=False), seq=0)
        self.assertFalse(seg.is_final)

    def test_speaker_none_when_missing(self):
        payload = self._make_payload()
        del payload["channel"]["alternatives"][0]["words"][0]["speaker"]
        seg = DeepgramStreamingAdapter._parse_message(payload, seq=0)
        self.assertIsNone(seg.speaker)

    def test_multi_word_timestamps(self):
        payload = {
            "type": "Results",
            "is_final": True,
            "channel": {
                "alternatives": [
                    {
                        "transcript": "hello world",
                        "confidence": 0.9,
                        "language": "en",
                        "words": [
                            {"word": "hello", "start": 1.0, "end": 1.3, "speaker": 0},
                            {"word": "world", "start": 1.3, "end": 1.8, "speaker": 0},
                        ],
                    }
                ]
            },
        }
        seg = DeepgramStreamingAdapter._parse_message(payload, seq=0)
        self.assertEqual(seg.ts_start, 1.0)
        self.assertEqual(seg.ts_end, 1.8)
