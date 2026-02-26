"""Typed configuration models for the GMeet worker."""

from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AudioConfig:
    sample_rate: int = 16000
    chunk_ms: int = 20
    debug: bool = False
    dump_enabled: bool = True


@dataclass
class SttConfig:
    provider: Optional[str] = None
    api_key: Optional[str] = None
    diarization: str = "dom"
    extra: dict = field(default_factory=dict)
    connect_retries: int = 4
    connect_initial_delay_s: float = 2.0
    connect_max_delay_s: float = 15.0


@dataclass
class JoinConfig:
    headless: bool = True
    storage_state_path: Optional[str] = None
    disable_mic: bool = True
    disable_camera: bool = True
    join_timeout_ms: int = 90000
    screenshot_dir: Optional[str] = "./screenshots"


@dataclass
class WorkerConfig:
    meeting_id: str
    meet_url: str
    duration_seconds: int = 3600
    audio: AudioConfig = field(default_factory=AudioConfig)
    stt: SttConfig = field(default_factory=SttConfig)
    join: JoinConfig = field(default_factory=JoinConfig)
