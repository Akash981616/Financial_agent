"""Event Management and Dispatching for Financial Reconciliation Agent.
Supports LangGraph custom event streaming, SSE (Server-Sent Events) for FastAPI,
and structured event logging.
"""

import uuid
from typing import Dict, Any, Callable, List, Optional
from datetime import datetime
from src.models import ReconciliationEvent

try:
    from langchain_core.callbacks.manager import dispatch_custom_event
    HAS_LANGCHAIN_EVENTS = True
except ImportError:
    HAS_LANGCHAIN_EVENTS = False


class EventDispatcher:
    """Central event dispatcher managing synchronous callbacks, async event queues,
    and LangGraph native custom events.
    """
    def __init__(self):
        self._listeners: List[Callable[[ReconciliationEvent], None]] = []
        self._event_history: List[ReconciliationEvent] = []

    def register_listener(self, listener: Callable[[ReconciliationEvent], None]):
        """Registers a callback for all emitted events."""
        if listener not in self._listeners:
            self._listeners.append(listener)

    def emit(self, event_type: str, stage: str, message: str, data: Optional[Dict[str, Any]] = None) -> ReconciliationEvent:
        """Dispatches an event across all listeners and LangGraph if active."""
        event = ReconciliationEvent(
            event_id=f"evt_{uuid.uuid4().hex[:8]}",
            event_type=event_type,
            timestamp=datetime.utcnow().isoformat(),
            stage=stage,
            message=message,
            data=data or {}
        )
        self._event_history.append(event)

        # 1. Fire local listeners
        for listener in self._listeners:
            try:
                listener(event)
            except Exception as e:
                print(f"[Warning] Event listener failed: {e}")

        # 2. Dispatch to LangGraph streaming events if inside a LangGraph run
        if HAS_LANGCHAIN_EVENTS:
            try:
                dispatch_custom_event(
                    name=event_type,
                    data={
                        "event_id": event.event_id,
                        "stage": stage,
                        "message": message,
                        "data": event.data,
                        "timestamp": event.timestamp
                    }
                )
            except Exception:
                # Not currently running inside an active LangGraph run with dispatch context
                pass

        return event

    def get_history(self) -> List[ReconciliationEvent]:
        return list(self._event_history)

    def clear(self):
        self._event_history.clear()


# Global singleton instance for application-wide event bus
global_event_bus = EventDispatcher()
