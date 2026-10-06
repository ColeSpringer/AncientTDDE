import threading
import time
from pathlib import Path

import pytest

from ancienttdde.common import worker
from ancienttdde.common.worker import capture_stdout_for_errors, run_module, run_parallel


def test_worker_output_is_returned() -> None:
    assert run_module("platform", label="Platform report").strip()


def test_failed_workers_report_their_label_and_error_output() -> None:
    with pytest.raises(ValueError, match="Missing worker failed: .*No module named"):
        run_module("ancienttdde.missing_worker", label="Missing worker")


def test_a_worker_that_runs_too_long_reports_its_label() -> None:
    with pytest.raises(ValueError, match="Sleeper timed out after 1 s"):
        run_module(
            "timeit",
            "-n",
            "1",
            "-r",
            "1",
            "import time; time.sleep(30)",
            label="Sleeper",
            timeout=1,
        )


def test_worker_processes_stay_within_their_slots_however_tasks_nest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Each worker logs when it ran; the overlap of those intervals is the concurrency.
    (tmp_path / "interval_worker.py").write_text(
        "import sys, time\n"
        "start = time.monotonic()\n"
        "time.sleep(0.3)\n"
        "with open(sys.argv[1], 'a') as log:\n"
        "    log.write(f'{start} {time.monotonic()}\\n')\n"
    )
    log = tmp_path / "intervals.log"
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(worker, "WORKER_SLOTS", threading.BoundedSemaphore(2))

    def run() -> None:
        run_module("interval_worker", str(log), label="Interval worker")

    run_parallel([lambda: run_parallel([run] * 3)] * 2)
    intervals = [tuple(map(float, line.split())) for line in log.read_text().splitlines()]
    assert len(intervals) == 6
    assert max(sum(start <= t < end for start, end in intervals) for t, _ in intervals) == 2


def test_parallel_tasks_return_results_in_task_order() -> None:
    def later() -> int:
        time.sleep(0.1)
        return 1

    assert run_parallel([later, lambda: 2, lambda: 3]) == (1, 2, 3)


def test_every_parallel_task_finishes_before_the_first_failure_is_raised() -> None:
    finished: list[str] = []

    def fail(message: str) -> None:
        raise ValueError(message)

    def slow() -> None:
        time.sleep(0.2)
        finished.append("slow")

    with pytest.raises(ValueError, match="first"):
        run_parallel([lambda: fail("first"), slow, lambda: fail("second")])
    assert finished == ["slow"]


def test_worker_chatter_is_shown_only_when_the_worker_fails(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with capture_stdout_for_errors():
        print("parser progress")
    assert capsys.readouterr().out == ""
    with pytest.raises(RuntimeError, match="boom"), capture_stdout_for_errors():
        print("parser progress")
        raise RuntimeError("boom")
    captured = capsys.readouterr()
    assert captured.out == ""
    assert "parser progress" in captured.err
