from __future__ import annotations

from croqui_engine.jobs.queue import dequeue


def run_once() -> dict | None:
    return dequeue()

