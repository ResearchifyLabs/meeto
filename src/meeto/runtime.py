"""Stable runtime entrypoint for executing a gmeet worker session."""

import asyncio
import logging
import time
from typing import Optional

from meeto.config.models import WorkerConfig
from meeto.meet.end_detector import check_meeting_ended
from meeto.meet.joiner import join_meet, wait_for_admission
from meeto.pipeline import setup_pipeline
from meeto.state_store import InMemoryMeetingLifecycleStore
from meeto.state_store.base import MeetingLifecycleStore
from meeto.state_store.status import MeetingLifecycleStatus
from meeto.storage import ArtifactStorageAdapter, LocalStorageAdapter

_logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_INTERVAL_SECONDS = 30
DEFAULT_ADMISSION_TIMEOUT_SECONDS = 900.0


async def run_meeting_worker(
    config: WorkerConfig,
    *,
    state_store: Optional[MeetingLifecycleStore] = None,
    heartbeat_interval_seconds: int = DEFAULT_HEARTBEAT_INTERVAL_SECONDS,
    admission_timeout_seconds: float = DEFAULT_ADMISSION_TIMEOUT_SECONDS,
    storage_adapter: Optional[ArtifactStorageAdapter] = None,
) -> None:
    if state_store is None:
        state_store = InMemoryMeetingLifecycleStore()

    if storage_adapter is None:
        storage_adapter = LocalStorageAdapter()

    state_store.update_status(config.meeting_id, status=MeetingLifecycleStatus.JOINING.value)
    _logger.info("GMEET JOB: joining meeting %s at %s", config.meeting_id, config.meet_url)

    session = await join_meet(
        config.meet_url,
        headless=config.join.headless,
        storage_state_path=config.join.storage_state_path,
        storage_adapter=storage_adapter,
    )

    state_store.update_status(
        config.meeting_id,
        status=MeetingLifecycleStatus.WAITING_FOR_ADMISSION.value,
    )
    admitted = await wait_for_admission(session.page, timeout_s=admission_timeout_seconds)
    if not admitted:
        _logger.error("GMEET JOB: timed out waiting for admission to %s", config.meeting_id)
        state_store.update_status(
            config.meeting_id,
            status=MeetingLifecycleStatus.FAILED.value,
            ended_at=time.time(),
        )
        await session.close()
        return

    _logger.info("GMEET JOB: admitted to meeting %s, starting pipeline", config.meeting_id)

    pipeline = await setup_pipeline(
        session,
        meeting_id=config.meeting_id,
        audio=config.audio,
        stt=config.stt,
        storage_adapter=storage_adapter,
    )

    state_store.update_status(config.meeting_id, status=MeetingLifecycleStatus.RECORDING.value)
    _logger.info("GMEET JOB: recording started for %s", config.meeting_id)

    start_time = time.time()
    failed = False
    try:
        while True:
            await asyncio.sleep(heartbeat_interval_seconds)
            state_store.heartbeat(config.meeting_id)

            if await check_meeting_ended(session.page):
                _logger.info("GMEET JOB: meeting ended signal for %s", config.meeting_id)
                break

            elapsed = time.time() - start_time
            if elapsed >= config.duration_seconds:
                _logger.info("GMEET JOB: duration cap reached for %s (%.0fs)", config.meeting_id, elapsed)
                break
    except Exception:
        _logger.exception("GMEET JOB: error in meeting loop for %s", config.meeting_id)
        failed = True
        raise
    finally:
        close_result = await pipeline.close()
        await session.close()
        transcript_result = close_result.get("transcript") if close_result else None
        transcription_path = transcript_result.get("remote_path") if transcript_result else None
        final_status = MeetingLifecycleStatus.FAILED.value if failed else MeetingLifecycleStatus.COMPLETED.value
        state_store.update_status(
            config.meeting_id,
            status=final_status,
            ended_at=time.time(),
            transcription_path=transcription_path,
        )

    _logger.info("GMEET JOB: completed meeting %s", config.meeting_id)
