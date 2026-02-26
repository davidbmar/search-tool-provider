"""Safe .env file merge — updates existing keys, appends new ones, preserves everything else."""

from __future__ import annotations

import os
import re
import tempfile
from pathlib import Path

# Matches KEY=value lines (with optional export prefix and quoting)
_KV_RE = re.compile(r"^(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)=(.*)$")

# Characters that require quoting in .env values
_NEEDS_QUOTING = re.compile(r'[#\s\'"]')


def _quote_value(value: str) -> str:
    """Wrap value in double quotes if it contains spaces, #, or quotes."""
    if _NEEDS_QUOTING.search(value):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return value


def merge_env_file(path: str | Path, updates: dict[str, str]) -> Path:
    """Merge *updates* into an .env file at *path*.

    - If the file exists, matching keys are updated in-place and new keys
      are appended at the end.  Comments, blank lines, and unrelated keys
      are preserved exactly.
    - If the file does not exist, it is created with one ``KEY=value`` line
      per entry in *updates*.
    - Values containing spaces, ``#``, or quotes are automatically
      double-quoted.
    - Writes are atomic (temp file + rename) to prevent data loss.

    Returns the resolved Path that was written.
    """
    path = Path(path)
    remaining = dict(updates)  # keys we still need to write

    if path.exists():
        lines = path.read_text().splitlines(keepends=True)
        out: list[str] = []
        for line in lines:
            m = _KV_RE.match(line.rstrip("\n\r"))
            if m and m.group(1) in remaining:
                key = m.group(1)
                # Preserve original line ending
                ending = ""
                if line.endswith("\r\n"):
                    ending = "\r\n"
                elif line.endswith("\n"):
                    ending = "\n"
                out.append(f"{key}={_quote_value(remaining.pop(key))}{ending}")
            else:
                out.append(line)

        # Append any keys that weren't already in the file
        if remaining:
            # Ensure there's a trailing newline before we append
            if out and not out[-1].endswith("\n"):
                out.append("\n")
            for key, value in remaining.items():
                out.append(f"{key}={_quote_value(value)}\n")

        content = "".join(out)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        lines_out = [f"{key}={_quote_value(value)}\n" for key, value in updates.items()]
        content = "".join(lines_out)

    # Atomic write: temp file in same directory, then rename
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".env.", suffix=".tmp")
    try:
        os.write(fd, content.encode())
        os.close(fd)
        fd = -1  # mark as closed
        os.replace(tmp, path)
    except BaseException:
        if fd >= 0:
            os.close(fd)
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise

    return path
