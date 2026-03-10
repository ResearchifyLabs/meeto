"""Streaming STT adapters for the Meet worker."""

from meeto.stt.base import STTStreamingAdapter, TranscriptSegment
from meeto.stt.deepgram import DeepgramStreamingAdapter
from meeto.stt.factory import create_stt_adapter, register_stt

register_stt("deepgram", DeepgramStreamingAdapter)

__all__ = [
    "STTStreamingAdapter",
    "TranscriptSegment",
    "DeepgramStreamingAdapter",
    "create_stt_adapter",
    "register_stt",
]
