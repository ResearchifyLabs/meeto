import unittest

from meeto.audio.pcm import downsample_float32, float32_to_pcm16


class TestDownsampleFloat32(unittest.TestCase):
    def test_same_rate_returns_copy(self):
        samples = [0.1, 0.2, 0.3]
        result = downsample_float32(samples, 48000, 48000)
        self.assertEqual(result, samples)
        self.assertIsNot(result, samples)

    def test_half_rate(self):
        samples = [0.0, 1.0, 0.0, 1.0]
        result = downsample_float32(samples, 48000, 24000)
        self.assertEqual(len(result), 2)

    def test_invalid_zero_rate(self):
        with self.assertRaises(ValueError):
            downsample_float32([1.0], 0, 16000)

    def test_upsample_rejected(self):
        with self.assertRaises(ValueError):
            downsample_float32([1.0], 16000, 48000)

    def test_empty_input(self):
        result = downsample_float32([], 48000, 16000)
        self.assertEqual(result, [])


class TestFloat32ToPcm16(unittest.TestCase):
    def test_silence(self):
        result = float32_to_pcm16([0.0, 0.0])
        self.assertEqual(len(result), 4)
        self.assertEqual(result, b"\x00\x00\x00\x00")

    def test_clipping_positive(self):
        result = float32_to_pcm16([2.0])
        expected = float32_to_pcm16([1.0])
        self.assertEqual(result, expected)

    def test_clipping_negative(self):
        result = float32_to_pcm16([-2.0])
        expected = float32_to_pcm16([-1.0])
        self.assertEqual(result, expected)

    def test_output_is_bytes(self):
        result = float32_to_pcm16([0.5, -0.5])
        self.assertIsInstance(result, bytes)
        self.assertEqual(len(result), 4)
