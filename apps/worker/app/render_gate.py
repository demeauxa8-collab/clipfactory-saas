"""Render gate — bounds how many ffmpeg renders run at once on a machine.

Rendering is the only CPU/RAM-heavy stage; running 6 at once OOMs the box.
This module exposes a process-wide, task-local semaphore set by the parallel
supervisor. When no semaphore is set (the current sequential worker, tests,
local runs) the gate is a transparent no-op — so importing/using it never
changes existing behaviour.

Usage:
  - supervisor sets the shared semaphore per job task: `set_render_semaphore(sem)`
  - the heavy ffmpeg function is decorated with `@render_gated`

The semaphore lives in a ContextVar, so each asyncio job-task carries its own
reference (set before the pipeline runs) and every render awaited inside that
task acquires the same shared, machine-wide semaphore.
"""

from __future__ import annotations

import asyncio
import functools
from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any, TypeVar

_render_sem: ContextVar[asyncio.Semaphore | None] = ContextVar("render_sem", default=None)

T = TypeVar("T")


def set_render_semaphore(sem: asyncio.Semaphore | None) -> None:
    """Set the machine-wide render semaphore for the current task context."""
    _render_sem.set(sem)


def render_gated(func: Callable[..., Awaitable[T]]) -> Callable[..., Awaitable[T]]:
    """Decorate an async render function so it acquires the render semaphore.

    No-op when no semaphore is set in the context (sequential worker / tests).
    """

    @functools.wraps(func)
    async def wrapper(*args: Any, **kwargs: Any) -> T:
        sem = _render_sem.get()
        if sem is None:
            return await func(*args, **kwargs)
        async with sem:
            return await func(*args, **kwargs)

    return wrapper
