import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from enum import Enum

    class StrEnum(str, Enum):
        pass


class MeetingLifecycleStatus(StrEnum):
    QUEUED = "queued"
    JOINING = "joining"
    WAITING_FOR_ADMISSION = "waiting_for_admission"
    RECORDING = "recording"
    COMPLETED = "completed"
    FAILED = "failed"
