"""
Thread-safe console output for multi-threaded translation.

Design:
  - Worker threads: call tlog(msg) to buffer messages locally (never print).
  - Main thread: after a worker completes, calls flush_tlog() to retrieve
    buffered lines and prints them. This guarantees zero interleaving.
  - ProgressBar: renders inline via \\r refresh, rate-limited to 0.2s,
    auto-disabled when stdout is redirected (not a TTY).
"""

import sys
import time
import threading
import shutil


# ---------------------------------------------------------------------------
# Thread-safe log buffer
# ---------------------------------------------------------------------------

_print_lock = threading.Lock()
_tlocal = threading.local()


def tlog(msg):
    """
    Worker-thread-only: append msg to this thread's local buffer.
    Does NOT write to stdout — the main thread will flush later.
    """
    if not hasattr(_tlocal, "lines"):
        _tlocal.lines = []
    _tlocal.lines.append(str(msg))


def flush_tlog():
    """
    Main-thread-only: retrieve and clear this thread's buffered lines.
    Returns a list of strings (may be empty).
    """
    lines = getattr(_tlocal, "lines", [])
    _tlocal.lines = []
    return lines


def log(msg):
    """
    Main-thread-only thread-safe print.
    Use this for all non-worker output (config display, summaries, etc.).
    """
    with _print_lock:
        print(msg, flush=True)


# ---------------------------------------------------------------------------
# Progress bar
# ---------------------------------------------------------------------------

class ProgressBar:
    """
    Inline progress bar with ETA and status breakdown.

    Renders via \\r refresh when stdout is a TTY; silently degrades to
    no output when stdout is redirected (e.g. piped to a file).
    """

    def __init__(self, total):
        self.total = total
        self.done = 0
        self.status = {"llm": 0, "cache": 0, "remote": 0, "failed": 0}
        self.start = time.monotonic()
        self._last_render = 0.0
        self._enabled = sys.stdout.isatty()

    def update(self, done, status):
        """Call from main thread each time a file completes."""
        self.done = done
        self.status = status
        if not self._enabled:
            return
        now = time.monotonic()
        if now - self._last_render < 0.2 and done < self.total:
            return
        self._last_render = now
        self._render()

    def _render(self):
        elapsed = time.monotonic() - self.start
        pct = self.done / self.total if self.total else 0

        # Build bar (capped at half terminal width, max 30)
        terminal_w = shutil.get_terminal_size().columns
        bar_len = min(terminal_w // 3, 30)
        filled = int(bar_len * pct)
        bar = "=" * filled + "." + " " * (bar_len - filled - 1)

        # ETA
        if self.done:
            eta = elapsed / self.done * (self.total - self.done)
        else:
            eta = 0

        line = (
            f"\r[{self.done}/{self.total}] [{bar}] {pct * 100:3.0f}%"
            f" | LLM {self.status['llm']} 缓存 {self.status['cache']}"
            f" 远程 {self.status['remote']} 失败 {self.status['failed']}"
            f" | {elapsed:4.0f}s / {eta:4.0f}s"
        )

        with _print_lock:
            sys.stdout.write(line.ljust(min(terminal_w, 120)))
            sys.stdout.flush()

    def finish(self):
        """End the \\r line so subsequent output starts on a new line."""
        if self._enabled:
            sys.stdout.write("\n")
            sys.stdout.flush()
