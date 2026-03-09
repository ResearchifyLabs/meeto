import unittest

from meeto.stt.base import STTStreamingAdapter
from meeto.stt.factory import _REGISTRY, create_stt_adapter, register_stt


class FakeSTT(STTStreamingAdapter):
    def __init__(self, **kwargs):
        self.kwargs = kwargs

    async def connect(self):
        pass

    async def send_audio(self, pcm_bytes):
        pass

    async def start(self, on_segment):
        pass

    async def close(self):
        pass


class TestSTTFactory(unittest.TestCase):
    def setUp(self):
        self._original = dict(_REGISTRY)

    def tearDown(self):
        _REGISTRY.clear()
        _REGISTRY.update(self._original)

    def test_register_and_create(self):
        register_stt("fake", FakeSTT)
        adapter = create_stt_adapter("fake", api_key="k")
        self.assertIsInstance(adapter, FakeSTT)
        self.assertEqual(adapter.kwargs, {"api_key": "k"})

    def test_unknown_provider_raises(self):
        with self.assertRaises(ValueError) as ctx:
            create_stt_adapter("nonexistent")
        self.assertIn("nonexistent", str(ctx.exception))

    def test_register_overwrites(self):
        register_stt("fake", FakeSTT)
        register_stt("fake", FakeSTT)
        self.assertIs(_REGISTRY["fake"], FakeSTT)
