"""Event definitions for the EventBus system."""

import uuid
from datetime import datetime
from typing import Any, Dict

from pydantic import BaseModel, Field


class Event(BaseModel):
    """Base class for all events in the system."""

    event_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    event_name: str
    timestamp: datetime = Field(default_factory=datetime.now)
    payload: Dict[str, Any] | None = Field(default_factory=dict)
    context: Dict[str, Any] | None = Field(default_factory=dict)
