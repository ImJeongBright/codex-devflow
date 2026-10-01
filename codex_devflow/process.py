"""Bounded POSIX process execution; output is streamed to evidence files."""

from dataclasses import asdict, dataclass
import os
from pathlib import Path
import signal
import subprocess
import time


@dataclass
class ProcessResult:
    command: list[str]
    exit_code: int | None
    elapsed_seconds: float
    timed_out: bool
    stdout_path: str
    stderr_path: str
    error: str | None = None

    def to_dict(self):
        return asdict(self)


class ProcessInterrupted(KeyboardInterrupt):
    def __init__(self, result: ProcessResult):
        super().__init__("Process interrupted by signal/user")
        self.result = result


def kill_group(process):
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def run_process(command, cwd, timeout, output_dir, stdin=""):
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stdout_path, stderr_path = output_dir / "stdout.log", output_dir / "stderr.log"
    started = time.monotonic()
    exit_code, timed_out, error = None, False, None
    interrupted = None
    with stdout_path.open("wb") as out, stderr_path.open("wb") as err:
        try:
            process = subprocess.Popen(command, cwd=cwd, stdin=subprocess.PIPE,
                                       stdout=out, stderr=err, start_new_session=True)
            try:
                process.communicate(stdin.encode(), timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                kill_group(process)
            except KeyboardInterrupt as exc:
                kill_group(process)
                interrupted = exc
            except BaseException:
                kill_group(process)
                raise
            exit_code = process.returncode
        except OSError as exc:
            error = str(exc)
            err.write(error.encode())
    result = ProcessResult(list(command), exit_code, time.monotonic() - started,
                         timed_out, str(stdout_path), str(stderr_path), error)
    if interrupted is not None:
        raise ProcessInterrupted(result) from interrupted
    return result
