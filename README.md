# Menlo Moms newsletter

Runs itself in the cloud. No laptop, no Airtable, no API credits.

| When (Pacific) | What | Where |
|---|---|---|
| Fri ~8:15 am | **Collect:** load every source in `sources.yaml`, save text snapshots and the forecast for the weekend after next | GitHub Actions → `runs/<friday>/` |
| Fri ~11:45 am | **Edit:** Claude reads the snapshots, your local email and the web; checks each pick on the organizer's page; writes the draft with photos | Claude scheduled task → `drafts/<friday>.md` |
| during edit | **Enrich:** loads each picked event page for photo, price, dates, sold-out status | GitHub Actions, triggered by `picks.json` |
| Sun–Thu ~6:20 am | **Weather:** refreshes the forecast line in upcoming drafts | GitHub Actions |
| Sunday | **You:** review `drafts/<friday>.md` (and `.review.md`), paste into Substack | |
| Thursday | Issue goes out | Substack |

## Sunday review
1. Open the notification link, or `drafts/` on GitHub (renders with photos).
2. Read `<friday>.review.md` first: it lists what to double-check and what got cut.
3. Copy the draft into Substack. The forecast line keeps updating each morning until Thursday.

## Common changes
- **Add or remove a source:** edit `sources.yaml`. Check the next run's `runs/<friday>/summary.md`.
- **Change a rule or the voice:** edit `editor/RULES.md` or `editor/STYLE.md`. The editor reads
  them every run. `editor/LESSONS.md` grows on its own from your edits.
- **Rerun something:** GitHub → Actions → pick the workflow → Run workflow.
- **Failures:** GitHub emails you if the collector fails; the editor's notification says if it
  ran without snapshots.

## Layout
- `collector/` page fetching (`web.py`), the Friday run (`collect.py`), event checks
  (`enrich.py`), forecast (`weather.py`, `refresh_weather.py`)
- `editor/` the editor's runbook and rules
- `runs/<friday>/` snapshots, picks and checks (kept 8 weeks)
- `drafts/` drafts and review notes
- `state/shown.json` when each Don't Miss / On the Horizon item last ran
