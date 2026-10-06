"""Run parser work in child processes and independent tasks side by side."""

import contextlib
import io
import os
import subprocess
import sys
import threading
from collections.abc import Callable, Generator, Iterable
from concurrent.futures import ThreadPoolExecutor
from typing import overload

# Each worker process is CPU-bound, so at most one runs per processor, however tasks nest.
WORKER_SLOTS = threading.BoundedSemaphore(os.process_cpu_count() or 1)


def run_module(module: str, *args: str, label: str, timeout: int = 120) -> str:
    """Run `python -m module` in a fresh interpreter; parser state never leaks between runs.

    The run waits for a free worker slot; its timeout starts once the process does.
    """
    try:
        with WORKER_SLOTS:
            process = subprocess.run(
                [sys.executable, "-m", module, *args],
                stdin=subprocess.DEVNULL,
                capture_output=True,
                text=True,
                timeout=timeout,
                check=False,
            )
    except subprocess.TimeoutExpired as error:
        raise ValueError(f"{label} timed out after {timeout} s") from error
    if process.returncode:
        raise ValueError(f"{label} failed: {process.stderr.strip()}")
    return process.stdout


@overload
def run_parallel[A, B](tasks: tuple[Callable[[], A], Callable[[], B]]) -> tuple[A, B]: ...
@overload
def run_parallel[T](tasks: Iterable[Callable[[], T]]) -> tuple[T, ...]: ...
def run_parallel(tasks: Iterable[Callable[[], object]]) -> tuple[object, ...]:
    """Run independent tasks concurrently and return their results in task order.

    Every task gets a thread; the worker processes they start share WORKER_SLOTS. Every
    task finishes before the first failure, in task order, is raised.
    """
    pending = list(tasks)
    with ThreadPoolExecutor(max_workers=max(len(pending), 1)) as pool:
        futures = [pool.submit(task) for task in pending]
    return tuple(future.result() for future in futures)


@contextlib.contextmanager
def capture_stdout_for_errors() -> Generator[None]:
    """Keep parser chatter off stdout, and show its tail on stderr if the work fails."""
    log = io.StringIO()
    try:
        with contextlib.redirect_stdout(log):
            yield
    except Exception:
        print(log.getvalue()[-18000:], file=sys.stderr)
        raise
