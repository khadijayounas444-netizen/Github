---
name: yt-research
description: Scrape YouTube search results into structured metadata (title, author, duration, view count, URL) using yt-dlp — no video downloads. Activates on /yt-research or intent like "find the latest/trending YouTube videos about X", "search YouTube for videos on X", or when gathering a set of YouTube URLs to feed into research/analysis (e.g. NotebookLM).
---

# YouTube Research

Turn a search query into a ranked list of YouTube videos with metadata, ready to
hand off to another tool (e.g. the `notebooklm-pipeline` skill). Uses `yt-dlp` to
read the search-results listing only — **nothing is downloaded**.

## Prerequisite

```bash
pip install yt-dlp
```

## Important: ask for a topic if none is given

If the user asks to "research" / "find trending videos" **without naming a topic**,
ask them what topic they want before running anything. Do not guess a topic.

## Usage

The scraper lives at `scripts/yt_search.py` (relative to this skill).

```bash
# Default: top 25 by relevance, JSON to stdout
python scripts/yt_search.py "horror stories"

# 25 latest videos (newest upload first)
python scripts/yt_search.py "horror stories" -n 25 --sort date

# Human-readable table
python scripts/yt_search.py "quantum computing" -n 10 --format table

# Just the URLs, one per line (easy to pipe into other tools)
python scripts/yt_search.py "lofi beats" -n 5 --format urls
```

### Options

| Flag | Values | Default | Meaning |
|------|--------|---------|---------|
| `query` (positional) | any string | — | The search query |
| `-n`, `--limit` | integer ≥ 1 | `25` | How many videos to return |
| `--sort` | `relevance`, `date`, `views`, `rating` | `relevance` | Result ordering. `date` = newest first (best proxy for "latest") |
| `--format` | `json`, `table`, `urls` | `json` | Output shape |

### JSON output shape

```json
{
  "query": "horror stories",
  "sort": "date",
  "count": 25,
  "videos": [
    {
      "rank": 1,
      "title": "The Night Shift",
      "url": "https://www.youtube.com/watch?v=VIDEOID",
      "video_id": "VIDEOID",
      "author": "Some Channel",
      "channel_url": "https://www.youtube.com/@somechannel",
      "duration_seconds": 754,
      "duration": "12:34",
      "view_count": 128340
    }
  ]
}
```

`view_count` and `duration` may be `null` for some entries (YouTube omits them
from the flat listing for certain videos, e.g. live streams or premieres).

## Notes on "trending" / "latest"

YouTube's own "Trending" tab is not exposed as a stable search query, so this
skill approximates it with search ordering:

- **"latest" →** `--sort date` (newest upload first).
- **"most popular" →** `--sort views`.

If the user specifically wants the platform Trending feed for a region, say so —
that requires a different (region-scoped) endpoint this skill does not cover.

## Handoff to NotebookLM

The `url` field of each result is a canonical `watch?v=` URL that the
`notebooklm-pipeline` skill accepts directly as a `youtube` source. A typical
flow: run this skill to collect URLs, then pass them to that skill to build a
notebook and generate analysis/deliverables.

## Network requirement

`yt-dlp` must be able to reach `www.youtube.com`. In sandboxes with a
restrictive egress policy (e.g. some hosted CI/agent environments), YouTube may
be blocked and the search will fail with a proxy `403`. Run this skill in an
environment with outbound access to YouTube (such as your local machine).
