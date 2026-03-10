"""Google Meet bot core runtime package."""

import logging

from meeto.runtime import run_meeting_worker

logging.getLogger(__name__).addHandler(logging.NullHandler())

__all__ = ["run_meeting_worker"]
