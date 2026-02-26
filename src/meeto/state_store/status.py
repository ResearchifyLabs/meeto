from enum import StrEnum


class MeetingLifecycleStatus(StrEnum):
    QUEUED = "queued"
    JOINING = "joining"
    WAITING_FOR_ADMISSION = "waiting_for_admission"
    RECORDING = "recording"
    COMPLETED = "completed"
    FAILED = "failed"
