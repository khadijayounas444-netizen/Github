---
name: notebooklm-pipeline
description: Drive Google NotebookLM from YouTube URLs to deliverables using the notebooklm-py CLI. Create a notebook, upload YouTube URLs as sources, ask for analysis, and generate infographics (including handwritten/chalkboard style), slide decks, and flashcards. Activates on /notebooklm-pipeline or intent like "send these videos to NotebookLM", "build a notebook from these sources", "have NotebookLM analyze X and make an infographic/slide deck/flashcards".
---

# NotebookLM Research Pipeline

Take a set of YouTube URLs (e.g. from the `yt-research` skill), build a NotebookLM
notebook, get an analysis of the top findings, and produce deliverables —
infographics, slide decks, and flashcards. Wraps the `notebooklm` CLI from
`notebooklm-py`.

> This skill is the second half of a pipeline. Pair it with `yt-research`, which
> produces the YouTube URLs this skill ingests.

## Prerequisites

1. **Install the package** (once):
   ```bash
   pip install "notebooklm-py[browser]"
   ```
2. **Authenticate** (once per session/machine) — see [Authentication](#authentication).
   Every command below requires a logged-in session.

Check auth/context at any time:
```bash
notebooklm status
```

## Authentication

NotebookLM login is interactive (it opens a browser for Google sign-in), so it
must be run by the user in **their own terminal window** — not by the agent:

```bash
notebooklm login
```

The window stays until login is detected, then saves the session automatically.
**Always remind the user to do this in a separate terminal before the first run,**
and wait for them to confirm they are logged in. If a command fails with an
auth error, the fix is to re-run `notebooklm login`.

## The pipeline (step by step)

Run these in order. Every command supports `--json` for machine-readable output;
capture the notebook id from step 1 and reuse it, or use `--use` to make it the
active context so later commands need no `--notebook`.

### 1. Create the notebook

```bash
notebooklm create "Horror Stories — YouTube Research" --use --json
```
`--use` sets it as the active notebook. Grab `active_notebook_id` from the JSON if
you prefer to pass `--notebook <id>` explicitly instead.

### 2. Upload the YouTube URLs as sources

One at a time:
```bash
notebooklm source add "https://www.youtube.com/watch?v=VIDEOID" --type youtube
```

Or in bulk, straight from `yt-research` output, using the helper script in this
skill (`scripts/bulk_add_sources.py`):
```bash
# Pipe yt-research JSON in; it extracts every video URL and adds each one
python /path/to/yt-research/scripts/yt_search.py "horror stories" -n 25 --sort date \
  | python scripts/bulk_add_sources.py --notebook <nb_id>
```
The helper accepts yt-research JSON, a newline-delimited URL list, or URLs as
arguments; it de-duplicates, prints per-URL progress, and exits non-zero if any
add fails. Use `--pause 1` to space out requests if you hit rate limits.

Confirm the sources landed:
```bash
notebooklm source list --notebook <nb_id>
```
Give NotebookLM a short moment to finish ingesting sources before generating
deliverables from them.

### 3. Ask for the analysis of top findings

```bash
notebooklm ask "Analyze these videos and summarize the top findings, themes, and
notable patterns across them. Cite sources." --json
```
`ask` returns an answer with inline citations (`[1]`, `[2]`) mapped to source ids
in the JSON. Use `--save-as-note` to keep the analysis in the notebook. Relay this
analysis to the user before (or alongside) generating visual deliverables.

### 4. Generate deliverables

All `generate` commands take an optional free-text description to steer content
and style, and `--wait` to block until the artifact is ready.

**Infographic** — the description carries any custom look; the closest built-in
style to *handwritten / chalkboard* is `sketch-note`:
```bash
notebooklm generate infographic \
  "Depict the top findings in a hand-drawn chalkboard style: white chalk on a
   dark slate background, handwritten lettering, simple chalk sketches and arrows." \
  --style sketch-note --orientation landscape --detail detailed --wait --json
```
Available `--style` values: `auto`, `sketch-note`, `professional`, `bento-grid`,
`editorial`, `instructional`, `bricks`, `clay`, `anime`, `kawaii`, `scientific`.
For a chalkboard/handwritten result, use `sketch-note` **and** describe the
chalkboard aesthetic in the prompt text (as above).

**Slide deck:**
```bash
notebooklm generate slide-deck "Presentation of the top findings" --wait --json
```

**Flashcards:**
```bash
notebooklm generate flashcards "Key facts and takeaways from the top findings" --wait --json
```

Other generators available: `audio`, `video`, `quiz`, `data-table`, `report`,
`mind-map`.

### 5. Download the results

```bash
# Positional OUTPUT_PATH; a trailing slash / existing dir downloads into it.
notebooklm download infographic --notebook <nb_id> ./out/
notebooklm download slide-deck  --notebook <nb_id> ./out/   # PDF or PPTX
notebooklm download flashcards  --notebook <nb_id> ./out/
```
Use `--all ./out/` to grab every artifact of a type, or `--name "..."` to pick one
by title.

## End-to-end example

User says: *"Find the 25 latest trending videos on horror stories, send them to
NotebookLM, give me the analysis of the top findings, then make a chalkboard-style
infographic of that analysis."*

```bash
# 1. Research (yt-research skill)
python /path/to/yt-research/scripts/yt_search.py "horror stories" -n 25 --sort date > videos.json

# 2. Notebook + sources
NB=$(notebooklm create "Horror Stories — YouTube Research" --use --json | python -c 'import sys,json;print(json.load(sys.stdin)["notebook"]["id"])')
python scripts/bulk_add_sources.py --notebook "$NB" < videos.json

# 3. Analysis
notebooklm ask "Summarize the top findings and themes across these videos, with citations." --json

# 4. Chalkboard infographic of the analysis
notebooklm generate infographic \
  "Hand-drawn chalkboard infographic of the top findings: white chalk on dark
   slate, handwritten text, chalk sketches and arrows." \
  --style sketch-note --detail detailed --wait --json

# 5. Download
notebooklm download infographic --notebook "$NB" ./out/
```

## If the user gives a research command with no topic

The `yt-research` step needs a topic. If the user asks to run the pipeline without
naming one, **ask what topic to research before doing anything.**

## Network requirement

The CLI talks to Google's NotebookLM endpoints; `yt-research` talks to YouTube.
Both require outbound network access to those hosts. In sandboxes with a
restrictive egress policy, these calls may be blocked (proxy `403`). Run the
pipeline where YouTube and Google are reachable (such as your local machine).

## Reference

Full CLI/API docs: <https://github.com/teng-lin/notebooklm-py> (see also the
top-level `SKILL.md` and `docs/` in this repo).
