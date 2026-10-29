# What makes the cut, and how to verify it

Built from a year of Angela's edits. When in doubt, cut: a lean issue beats a padded one.

## The bar
- **Novel, one-time, seasonal or marquee** events clear the bar (PV Palooza, Fourth Fridays,
  a festival's last weekend). The test is rarity, not whether it has a date.
- **Recurring series are out** of the Lineup and This Weekend, even on a thin weekend:
  weekly storytimes, open gyms, Music on the Square, Kids Rock, Sounds of the Shores,
  Magical Bridge "Magical Music & Motion" and the monthly Magical Bridge Community Partner Day.
- **Test every candidate for recurrence**, not just its date:
  - Event URL with a number suffix or embedded date (`paint-a-plane-4/`, `bubble_bonanza-2/2026-08-30/`)
    means a repeating program. Hiller uses this pattern; exclude its numbered programs.
  - Check the venue's calendar for the same name on other dates. Rotating acts or partners
    under one series name = recurring.
- **Always excluded:** OFJCC / ICC "Raise the Bar" cohorts (they leak in via aggregators);
  CSA shares, farm subscriptions and other product purchases.
- Scoring guide (for ordering, not a formula to show): family reach 40%, novelty 30%,
  brand fit (community, local institutions, outdoors, arts, Stanford) 20%, quality 10%;
  generic weekly events lose 5 points. Cost is neutral.

## Sections
- **Don't Miss Signups This Week:** only things a reader can sign up for or buy *right now*
  where waiting means missing out: camps, classes, leagues, gymnastics sessions, shows about
  to sell out. Sold out = out (Outside Lands was cut twice). Not on sale yet = out (add it the
  week it goes on sale). Far-off save-the-dates = out.
- **On the Horizon:** up to 3 big upcoming events with tickets or registration open.
  Show each at most once every 3 weeks (`state/shown.json`), except a last-chance mention in
  the final 2 weeks before its deadline.
- **Sunday Standbys:** only when the Lineup has fewer than 3 cards, or Sunday is empty
  after counting multi-day events still running.
- **Big moments:** if a marquee scheduled event lands on the weekend (World Cup final,
  Pokémon Worlds, a meteor shower), add one short callout after the weather line. Confirm the
  date and time first. If in-person is sold out, point to the watch option.
- **Community traditions** with advance RSVP (July 4th parade and picnic, egg hunts, tree
  lightings) always make it, even when the scraper missed them.

## Verify every card (organizer's page, never the aggregator)
Aggregators routinely get these wrong. Confirm each one from `enrich.json` or the browser:
1. **Dates:** every day it runs. Aggregators collapse multi-day festivals to one day
   (Aloha Festival, Belmont Greek Festival, Kings Mountain Art Fair all came through wrong).
2. **Time:** start and end.
3. **Cost:** Funcheap marks paid events FREE (Aloha: $5 + $25 parking). Filoli puts price and
   "reservation required" below the fold ("Redwoods in the Round" was $65; "Free with General
   Admission; reservation required" means you still pay admission).
4. **Registration:** required? deadline? Midpen docent outings close on Eventbrite about
   2:00 PM the day before. A closed registration is a cut, not a caveat.
5. **Age and skill:** Midpen states these in prose ("experienced mountain bike riders,"
   "ages 10+"). Pitch the card to match.
6. **Ticket status:** look for "sold out," "waitlist," "sales ended" in `signals`. A visible
   "Get tickets" button does not mean tickets are available. PACT/ShoWare: also check the
   on-sale date.
7. **The page matches the card:** the link resolves to *this* event, not a sibling page
   (the zoo's $250 private "Animal Experiences" page vs. its free scheduled encounters) or an
   unrelated event picked up from a sidebar (the Pumpkin Weigh-Off linked to a La Honda page).
8. **Location:** use the organizer's town. Midpen preserves get mislabeled (Monte Bello is on
   Page Mill Rd, not Woodside).

If a fact can't be confirmed, cut the item or list it under "Check before sending." Never fill
a gap with something plausible.

## Weather
Only use `weather.json`. If a day says unavailable, the line says so. Never write a
temperature yourself.

## Source notes
- Redwood City: redwoodcity.org blocks scrapers; coverage comes from Funcheap's Redwood City
  page, email (Redwood City Parks and Recreation) and the web sweep.
- Portola Valley: no working calendar; rely on email and the web sweep (PV Palooza, Town
  Picnic, Zotts to Tots, Broom Pull).
- Magical Bridge events appear on the Palo Alto city calendar.
- Angela's Gmail is a source: local senders like Betsy Nash and the Menlo Park city newsletter.
