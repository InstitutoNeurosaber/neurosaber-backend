"""Event handlers for the EventBus system."""

from typing import Callable, Dict, List

import structlog

from .events import Event

logger = structlog.get_logger(__name__)


class EventHandlerRegistry:
    """Registry for managing event handler functions."""

    def __init__(
        self,
    ):
        self._handlers: Dict[str, List[Callable[[Event], None]]] = {}

    def subscribe(self, event_name: str, handler_func: Callable[[Event], None]) -> None:
        """Subscribe a function as an event handler.

        Args:
            event_name: Name of the event to subscribe to
            handler_func: Function to register as handler
        """
        if event_name not in self._handlers:
            self._handlers[event_name] = []
        if handler_func in self._handlers[event_name]:
            logger.warning(
                "Handler function already registered for event",
                event_name=event_name,
                handler_func=handler_func,
            )
            return
        self._handlers[event_name].append(handler_func)

    def get_handlers(self, event_name: str) -> List[Callable[[Event], None]]:
        """Get all handler functions for an event.

        Args:
            event_name: Name of the event

        Returns:
            List of handler functions for the event
        """
        return self._handlers.get(event_name, [])

    def clear(self) -> None:
        """Clear all registered handlers."""
        self._handlers.clear()
