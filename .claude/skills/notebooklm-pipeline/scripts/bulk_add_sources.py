#!/usr/bin/env python3
"""Bulk-add YouTube URLs to a NotebookLM notebook via the ``notebooklm`` CLI.

Accepts input in three forms (auto-detected):

1. ``yt-research`` JSON  — an object with a ``videos`` list, each having a
   ``url`` field (i.e. the JSON emitted by the ``yt-research`` skill).
2. A plain list of URLs  — one per line.
3. URLs passed as CLI arguments.

Each URL is added with ``notebooklm source add <url> --type youtube --json``.
Progress is printed to stderr; a machine-readable summary is printed to stdout.

Examples
--------
    # Pipe yt-research JSON straight in, target a specific notebook
    python yt_search.py "horror stories" -n 25 --sort date \
        | python bulk_add_sources.py --notebook nb_abc123

    # Add explicit URLs to the active notebook
    python bulk_add_sources.py https://youtu.be/a https://youtu.be/b

Exit code is non-zero if any source failed to add.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path


def _resolve_notebooklm_cmd() -> list[str]:
    """Find the ``notebooklm`` CLI, preferring the venv running this script.

    On Windows (and inside virtualenvs generally) the ``notebooklm`` console
    script lives in the interpreter's Scripts/bin directory, which is often
    NOT on the system PATH — so a bare ``notebooklm`` lookup fails. Resolve it
    relative to ``sys.executable`` first, then PATH, then fall back to running
    the package as a module with this same interpreter (guaranteed to exist).
    """
    override = os.environ.get("NOTEBOOKLM_CMD")
    if override:
        return [override]
    exe_dir = Path(sys.executable).parent
    for name in ("notebooklm.exe", "notebooklm"):
        candidate = exe_dir / name
        if candidate.exists():
            return [str(candidate)]
    on_path = shutil.which("notebooklm")
    if on_path:
        return [on_path]
    # Last resort: `python -m notebooklm` (the package ships a __main__.py).
    return [sys.executable, "-m", "notebooklm"]


_NOTEBOOKLM_CMD = _resolve_notebooklm_cmd()


def _extract_urls_from_text(text: str) -> list[str]:
    """Pull URLs from either yt-research JSON or a newline-delimited list."""
    text = text.strip()
    if not text:
        return []
    # Try JSON first (yt-research shape or a bare list of urls/objects).
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        # Fall back to one-URL-per-line.
        return [ln.strip() for ln in text.splitlines() if ln.strip()]

    if isinstance(data, dict) and isinstance(data.get("videos"), list):
        return [v.get("url") for v in data["videos"] if isinstance(v, dict) and v.get("url")]
    if isinstance(data, list):
        urls = []
        for item in data:
            if isinstance(item, str):
                urls.append(item)
            elif isinstance(item, dict) and item.get("url"):
                urls.append(item["url"])
        return urls
    return []


def _add_source(url: str, notebook: str | None, timeout: float | None) -> tuple[bool, str]:
    """Run the CLI to add one youtube source. Returns (ok, detail)."""
    cmd = [*_NOTEBOOKLM_CMD, "source", "add", url, "--type", "youtube", "--json"]
    if notebook:
        cmd += ["--notebook", notebook]
    try:
        proc = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
    except FileNotFoundError:
        return False, (
            f"could not run notebooklm CLI ({' '.join(_NOTEBOOKLM_CMD)}); "
            "set NOTEBOOKLM_CMD to its full path"
        )
    except subprocess.TimeoutExpired:
        return False, f"timed out after {timeout}s"

    if proc.returncode == 0:
        source_id = None
        try:
            payload = json.loads(proc.stdout)
            source_id = (payload.get("source") or {}).get("id") or payload.get("id")
        except (json.JSONDecodeError, AttributeError):
            pass
        return True, source_id or "added"

    detail = (proc.stderr or proc.stdout or "").strip().splitlines()
    return False, detail[-1] if detail else f"exit {proc.returncode}"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("urls", nargs="*", help="YouTube URLs (or read from stdin)")
    parser.add_argument(
        "-n", "--notebook", default=None,
        help="Target notebook ID (defaults to the active notebook context)",
    )
    parser.add_argument(
        "--request-timeout", type=float, default=120.0,
        help="Per-source HTTP timeout in seconds passed to the CLI wrapper (default: 120)",
    )
    parser.add_argument(
        "--pause", type=float, default=0.0,
        help="Seconds to sleep between adds, to be gentle on rate limits (default: 0)",
    )
    args = parser.parse_args(argv)

    urls = list(args.urls)
    if not urls and not sys.stdin.isatty():
        urls = _extract_urls_from_text(sys.stdin.read())

    if not urls:
        parser.error("No URLs provided (pass as arguments or pipe via stdin).")

    # De-duplicate while preserving order.
    seen: set[str] = set()
    urls = [u for u in urls if not (u in seen or seen.add(u))]

    results = []
    total = len(urls)
    for i, url in enumerate(urls, start=1):
        sys.stderr.write(f"[{i}/{total}] adding {url} ... ")
        sys.stderr.flush()
        ok, detail = _add_source(url, args.notebook, args.request_timeout)
        sys.stderr.write(("ok: " if ok else "FAILED: ") + detail + "\n")
        results.append({"url": url, "ok": ok, "detail": detail})
        if args.pause and i < total:
            time.sleep(args.pause)

    added = sum(1 for r in results if r["ok"])
    failed = total - added
    json.dump(
        {"total": total, "added": added, "failed": failed, "results": results},
        sys.stdout,
        indent=2,
    )
    sys.stdout.write("\n")
    sys.stderr.write(f"\nDone: {added} added, {failed} failed, out of {total}.\n")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
