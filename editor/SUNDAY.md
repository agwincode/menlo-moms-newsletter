# Sunday refresh runbook (early Sunday morning)

Angela reviews and schedules the issue on Sunday. Before she sits down, refresh what goes stale
between Friday and Sunday, then republish the review page. Don't rewrite the draft.

1. `git pull`; `pip install markdown pillow`. FRIDAY = the date of the newest `drafts/YYYY-MM-DD.md`
   that is 5 days from today. If there is none, notify Angela that Friday's draft is missing and stop.
2. Weather: GitHub refreshed `runs/FRIDAY/weather.json` and the draft's forecast line around 4–5am.
   Check `weather.json` → `fetched` is today; if not, note it under "Check before sending".
3. Ticket and registration status: start the "Enrich picks" workflow for FRIDAY
   (`gh api -X POST repos/agwincode/menlo-moms-newsletter/actions/workflows/enrich.yml/dispatches -f ref=main -f 'inputs[friday]=FRIDAY'`),
   wait for the new `enrich.json` with the Monitor tool (up to 25 minutes), then compare each
   card's `signals` with Friday's: newly sold out, registration closed, cancelled or postponed.
   Add each change to the top of `## Check before sending` in `drafts/FRIDAY.review.md`,
   marked "(new Sunday)". Don't edit the draft itself.
4. `python editor/build_page.py FRIDAY`, then read the artifact in `state/page.json` and publish
   `build/FRIDAY.html` to that same `url`.
5. Commit and push. Send Angela a push notification: "Draft refreshed: weather updated, N new
   ticket changes. <page url>".
