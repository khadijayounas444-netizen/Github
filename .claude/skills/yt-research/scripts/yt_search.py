#!/usr/bin/env python3
"""Scrape YouTube search metadata with yt-dlp (no downloads).

Given a search query, returns metadata for the top N matching videos:
title, uploader/author, duration, view count, and canonical watch URL.

Nothing is downloaded — only the search-results listing is extracted
(``extract_flat``), which is fast and cheap. This is intended as the
first stage of a research pipeline that feeds the URLs to NotebookLM.

Examples
--------
    # 25 most-recent "horror stories" videos, as JSON
    python yt_search.py "horror stories" -n 25 --sort date

    # Top 10 by relevance, human-readable table
    python yt_search.py "quantum computing" -n 10 --format table

    # URLs only (one per line) — handy for piping
    python yt_search.py "lofi" -n 5 --format urls

Output (JSON, the default) is a single object:
    {"query": ..., "sort": ..., "count": N, "videos": [ {...}, ... ]}
Each video has: rank, title, url, video_id, author, channel_url,
duration_seconds, duration, view_count.
"""

from __future__ import annotations

import argparse
import json
import sys
from urllib.parse import quote_plus

try:
    from yt_dlp import YoutubeDL
except ImportError:  # pragma: no cover - dependency guard
    sys.stderr.write(
        "yt-dlp is not installed. Install it with:\n"
        "    pip install yt-dlp\n"
    )
    raise SystemExit(2)


# YouTube search-results sort filters. These are the ``sp`` query-string
# tokens the site itself uses; passing the results URL (rather than the
# ``ytsearch:`` prefix) is the only way to control ordering in yt-dlp.
SORT_FILTERS = {
    "relevance": None,           # site default
    "date": "CAI%3D",            # sort by upload date (newest first)
    "views": "CAM%3D",           # sort by view count
    "rating": "CAE%3D",          # sort by rating
}


def _seconds_to_hms(seconds: object) -> str | None:
    """Render a duration in seconds as H:MM:SS / M:SS."""
    if not isinstance(seconds, (int, float)) or seconds < 0:
        return None
    total = int(seconds)
    hours, rem = divmod(total, 3600)
    minutes, secs = divmod(rem, 60)
    if hours:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes}:{secs:02d}"


def _build_search_target(query: str, sort: str, limit: int) -> str:
    """Return either a ytsearch expression or a results URL with a sort filter."""
    sp = SORT_FILTERS[sort]
    if sp is None:
        # ytsearchN: is the simplest path for relevance ordering.
        return f"ytsearch{limit}:{query}"
    return f"https://www.youtube.com/results?search_query={quote_plus(query)}&sp={sp}"


def search(query: str, limit: int, sort: str) -> list[dict]:
    """Run the search and return a list of normalized video dicts."""
    target = _build_search_target(query, sort, limit)
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": "in_playlist",  # list entries only; do not resolve each video
        "skip_download": True,
        "playlistend": limit,           # cap results when target is a results URL
        "default_search": "ytsearch",
    }

    with YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(target, download=False)

    entries = (info or {}).get("entries") or []
    videos: list[dict] = []
    for rank, entry in enumerate(entries[:limit], start=1):
        if not entry:
            continue
        video_id = entry.get("id")
        url = entry.get("url") or (
            f"https://www.youtube.com/watch?v={video_id}" if video_id else None
        )
        # Normalize to a canonical watch URL when we only got an id/shortlink.
        if video_id and (not url or "watch?v=" not in url):
            url = f"https://www.youtube.com/watch?v={video_id}"
        duration = entry.get("duration")
        videos.append(
            {
                "rank": rank,
                "title": entry.get("title"),
                "url": url,
                "video_id": video_id,
                "author": entry.get("uploader") or entry.get("channel"),
                "channel_url": entry.get("channel_url") or entry.get("uploader_url"),
                "duration_seconds": duration,
                "duration": _seconds_to_hms(duration),
                "view_count": entry.get("view_count"),
            }
        )
    return videos


def _fmt_views(n: object) -> str:
    return f"{n:,}" if isinstance(n, int) else "n/a"


def _print_table(videos: list[dict]) -> None:
    if not videos:
        print("No results.")
        return
    for v in videos:
        print(f"[{v['rank']:>2}] {v['title'] or '(untitled)'}")
        print(
            f"     author: {v['author'] or 'n/a'}  |  "
            f"duration: {v['duration'] or 'n/a'}  |  "
            f"views: {_fmt_views(v['view_count'])}"
        )
        print(f"     {v['url']}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Scrape YouTube search metadata with yt-dlp (no downloads)."
    )
    parser.add_argument("query", help="Search query, e.g. 'horror stories'")
    parser.add_argument(
        "-n", "--limit", type=int, default=25,
        help="Number of videos to return (default: 25)",
    )
    parser.add_argument(
        "--sort", choices=sorted(SORT_FILTERS), default="relevance",
        help="Result ordering (default: relevance). 'date' = newest first.",
    )
    parser.add_argument(
        "--format", choices=["json", "table", "urls"], default="json",
        help="Output format (default: json)",
    )
    args = parser.parse_args(argv)

    if args.limit < 1:
        parser.error("--limit must be >= 1")

    try:
        videos = search(args.query, args.limit, args.sort)
    except Exception as exc:  # noqa: BLE001 - surface any yt-dlp/network error cleanly
        sys.stderr.write(f"Search failed: {exc}\n")
        return 1

    if args.format == "json":
        json.dump(
            {"query": args.query, "sort": args.sort, "count": len(videos), "videos": videos},
            sys.stdout,
            indent=2,
            ensure_ascii=False,
        )
        sys.stdout.write("\n")
    elif args.format == "urls":
        for v in videos:
            if v["url"]:
                print(v["url"])
    else:
        _print_table(videos)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
