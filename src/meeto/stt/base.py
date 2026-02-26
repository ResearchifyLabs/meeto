import abc
from dataclasses import dataclass
from typing import Optional


@dataclass
class TranscriptSegment:
    text: str
    seq: int
    ts_start: Optional[float]
    ts_end: Optional[float]
    speaker: Optional[str]
    is_final: bool
    confidence: Optional[float]
    lang: Optional[str]
    payload: dict


class STTStreamingAdapter(abc.ABC):
    @abc.abstractmethod
    async def connect(self) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def send_audio(self, pcm_bytes: bytes) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def start(self, on_segment) -> None:
        raise NotImplementedError

    @abc.abstractmethod
    async def close(self) -> None:
        raise NotImplementedError
