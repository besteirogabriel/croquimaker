from __future__ import annotations

from collections import deque

_QUEUE: deque[dict] = deque()


def enqueue(task: dict) -> int:
    _QUEUE.append(task)
    return len(_QUEUE)


def dequeue() -> dict | None:
    return _QUEUE.popleft() if _QUEUE else None

