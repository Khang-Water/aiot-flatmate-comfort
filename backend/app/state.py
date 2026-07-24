import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from itertools import count
from typing import Any


@dataclass(frozen=True, slots=True)
class SseMessage:
    sequence: int
    event: str
    data: dict[str, Any]


class EventBroker:
    """Small in-process fan-out broker for local SSE clients."""

    def __init__(self) -> None:
        self._sequence = count(1)
        self._subscribers: set[asyncio.Queue[SseMessage]] = set()

    def next_sequence(self) -> int:
        return next(self._sequence)

    async def publish(self, event: str, data: dict[str, Any]) -> SseMessage:
        message = SseMessage(self.next_sequence(), event, data)
        for queue in tuple(self._subscribers):
            if queue.full():
                queue.get_nowait()
            queue.put_nowait(message)
        return message

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[SseMessage]]:
        queue: asyncio.Queue[SseMessage] = asyncio.Queue(maxsize=100)
        self._subscribers.add(queue)
        try:
            yield queue
        finally:
            self._subscribers.discard(queue)
