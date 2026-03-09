"""EventBus implementation for asynchronous event processing."""

import queue
import threading
import uuid
from typing import Callable, Optional
import inspect

import structlog
from injector import Inject

from app.core.events.events import Event
from app.core.events.handlers import EventHandlerRegistry

logger = structlog.getLogger(__name__)


class EventBus:
    """Thread-safe EventBus for asynchronous event processing."""

    def __init__(self, max_queue_size: int = 1000, injector=None):
        """Initialize EventBus.

        Args:
            max_queue_size: Maximum number of events in the queue
            injector: Dependency injector for resolving handler dependencies
        """
        self._queue: queue.Queue = queue.Queue(maxsize=max_queue_size)
        self._registry = EventHandlerRegistry()
        self._worker_thread: Optional[threading.Thread] = None
        self._running = False
        self._injector = injector
        self.logger = logger.bind(
            queue_size=self.queue_size,
            queue_max_size=self._queue.maxsize,
            event_bus_id=uuid.uuid4(),
        )
        self._subscribe_from_registry()

    def _subscribe_from_registry(self):
        from app.core.events import _subscription_registry

        for event_name, handler in _subscription_registry:
            self.subscribe(event_name, handler)

    def start(self) -> None:
        """Start the background worker thread."""
        if self._running:
            self.logger.warning("EventBus start attempted but already running")
            return

        self._running = True
        self._worker_thread = threading.Thread(
            target=self._worker_loop, name="EventBusWorker", daemon=True
        )
        self._worker_thread.start()
        self.logger.info("EventBus worker thread started")

    def publish(self, event: Event) -> bool:
        """Publish an event object to the bus.

        Args:
            event: Event instance to publish

        Returns:
            True if event was queued successfully, False if queue is full
        """
        if not self._running:
            self.logger.warning(
                "Event publish attempted but EventBus not running",
                event_name=event.event_name,
                event_id=str(event.event_id),
            )
            return False

        try:
            self._queue.put_nowait(event)
            self.logger.debug(
                "Event published",
                event_name=event.event_name,
                event_id=str(event.event_id),
            )
            return True
        except queue.Full:
            self.logger.error(
                "Event queue full, dropping event",
                event_name=event.event_name,
                event_id=str(event.event_id),
            )
            return False

    def subscribe(self, event_name: str, handler_func: Callable[[Event], None]) -> None:
        """Subscribe a function as an event handler.

        Args:
            event_name: Name of the event to subscribe to
            handler_func: Function to register as handler
        """
        self._registry.subscribe(event_name, handler_func)
        self.logger.debug(
            "Function handler subscribed to event",
            event_name=event_name,
            handler_name=handler_func.__name__,
            handler_module=handler_func.__module__,
        )

    def _worker_loop(self) -> None:
        self.logger.info("EventBus worker loop started")
        while True:
            event = self._queue.get()  # Blocks forever until an event arrives
            try:
                self._process_event(event)
            finally:
                self._queue.task_done()

    def _process_event(self, event: Event) -> None:
        """Process a single event by dispatching to handlers.

        Args:
            event: Event to process
        """
        handlers = self._registry.get_handlers(event.event_name)

        if not handlers:
            self.logger.debug(
                "No handlers registered for event",
                event_name=event.event_name,
                event_id=str(event.event_id),
            )
            return

        for handler_func in handlers:
            try:
                self._call_handler_with_dependencies(handler_func, event)
            except Exception as e:
                self.logger.error(
                    "Error in event handler",
                    event_name=event.event_name,
                    event_id=str(event.event_id),
                    exception=str(e),
                    handler=handler_func.__name__,
                )

    def _call_handler_with_dependencies(self, handler_func: Callable, event: Event) -> None:
        """Call a handler function with dependency injection if needed.
        
        Args:
            handler_func: The handler function to call
            event: The event to pass to the handler
        """
        if not self._injector:
            # No injector available, call handler directly
            handler_func(event)
            return
            
        # Get function signature
        sig = inspect.signature(handler_func)
        params = sig.parameters
        
        # Build arguments for the handler
        args = {}
        
        for param_name, param in params.items():
            if param_name == 'event':
                args[param_name] = event
            elif param.annotation != inspect.Parameter.empty:
                # Check if this is an Inject[Type] annotation
                annotation = param.annotation
                dependency_type = None
                
                # Handle Inject[Type] pattern
                if hasattr(annotation, '__origin__') and annotation.__origin__ is Inject:
                    dependency_type = annotation.__args__[0]
                # Handle direct type annotations (fallback)
                elif hasattr(annotation, '__module__') and hasattr(annotation, '__name__'):
                    dependency_type = annotation
                
                if dependency_type:
                    try:
                        args[param_name] = self._injector.get(dependency_type)
                        self.logger.debug(f"Injected dependency {dependency_type} for parameter {param_name}")
                    except Exception as e:
                        self.logger.error(f"Failed to inject dependency {dependency_type} for parameter {param_name}: {e}")
                        raise
        
        # Call the handler with resolved dependencies
        try:
            handler_func(**args)
            self.logger.debug(f"Successfully called handler {handler_func.__name__} with {len(args)} arguments")
        except Exception as e:
            self.logger.error(f"Error calling handler {handler_func.__name__}: {e}")
            raise

    @property
    def is_running(self) -> bool:
        """Check if EventBus is running."""
        return self._running

    @property
    def queue_size(self) -> int:
        """Get current queue size."""
        return self._queue.qsize()
