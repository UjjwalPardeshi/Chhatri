# Final deck and backup video script

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 · A slide that shows a planned feature is used only if that feature is on at the freeze; otherwise the built-today version is used |
| Owner | Omkar Kadam (slides, words, video) with Ujjwal Pardeshi (operator, recording) |
| Audience | The presenter, the operator and whoever records the backup video |
| Related | [Demo runbook](demo-runbook.md) (the clicks) · [DEMO.md](../DEMO.md) (the golden script and numbers) · [Pitch and judge Q&A](pitch-and-judge-qa.md) · [On-site checklist](on-site-checklist.md) · [Build plan](build-plan.md) · [Copy deck](../03-design/copy-deck.md) · [AI evaluation plan](../04-engineering/ai-evaluation-plan.md) · [Business model](../05-business/business-model-and-unit-economics.md) · [Facts and sources](../01-strategy/facts-and-sources.md) · [Competitive landscape](../01-strategy/competitive-landscape.md) |

## TL;DR

- **14 slides.** Slides 1 to 12 are the talk; slides 13 and 14 stay in the back for questions. The 7-minute cut uses slides 1 to 12. The 3-minute cut uses slides 1, 3, 4, 8 and 12.
- **The story, in this order:** the merchant's problem, the claim starting itself, the four stages of the claims journey (understand coverage, submit a document, track, resolve queries), trust (source badges, counterfactual, audit chain), AI with honest labels, the business model with the honest price, honest limits, the ask.
- **Everything on a slide is BUILT today, or is shown only if its feature flag is on at the freeze.** Every slide that depends on planned work has a built-today version (section 4). A half-working screen is never shown.
- **Words:** the key lines from [pitch and judge Q&A](pitch-and-judge-qa.md) section 4 are delivered word for word. No partner is claimed. WhatsApp and the Paytm link are SIMULATED. No AI accuracy number is quoted unless the evaluation page shows it.
- **The backup video** is about 2 minutes: 10 shots with narration (section 5). It plays only if the live demo and the static demo (N7) both fail.
- **The round-1 deck has claims the prototype does not support** (WhatsApp and the Paytm link live, "a few rupees a day", Marathi on the phone). Section 6 lists the corrections to carry into the final deck.

## 1. Ground rules

1. **One honest story.** The deck says what runs as code, what is simulated and what is not measured. The same sentences appear on the slide, in the notes and in the Q&A.
2. **Status words.** BUILT (in the code at commit 86575ea), PLANNED with a build wave (0 to 5, [build plan](build-plan.md)), SIMULATED (a labelled simulator), LIVE (a real service answered, shown by a header badge).
3. **Two versions of a slide when it depends on new work.** "If shipped" is used only when the flag is on and the feature passed the rehearsal on the demo laptop. Otherwise use "Built today". The decision is made once, at the freeze, and written in the rehearsal log ([runbook](demo-runbook.md) section 8).
4. **Never on a slide:** a claim that an insurer or lender has agreed to anything; a URL for the static demo or the video before it exists (the repo owner must deploy it); an AI accuracy figure that the `/evals` page does not show; the word live for anything that shows SIMULATED; "open source" (the repository is public, with no licence yet); a rival team member's name; a fixed freeze clock time or a slot time.
5. **Anil and Ramesh are synthetic personas** in a simulated replay. The slides say so.
6. **Ids** (K1, N1, H13 and so on) are for the team. They are not printed on slides.
7. **Design.** Use the console's colours and type (SPEC §20, [design system](../03-design/design-system.md)). Hindi in Devanagari with English beside it. Any free tool will do for the slides. Export a PDF as the offline copy.
8. **Two windows.** The deck and the console. The operator switches on Omkar's cue words. Every slide that runs live also has a still, for use if the console fails.
9. **Source badges.** The plan calls them verified-by badges. On a slide and aloud, say "source": the badge says where a number came from. It does not claim that an outside body verified it ([copy deck](../03-design/copy-deck.md) section 1.2).

## 2. Run of show

The slot time and length are not announced. Both cuts are ready. Rehearse to land 10 to 15 seconds early.

### 2.1 Seven-minute cut (420 seconds)

| Slide | Beat | Mode | Time | Seconds |
|---|---|---|---|---|
| 1 | Hook: one rainy Tuesday | Slide | 0:00–0:30 | 30 |
| 2 | One line, four stages | Slide | 0:30–0:50 | 20 |
| 3 | The claim starts itself | Live `/live` | 0:50–1:45 | 55 |
| 4 | Anil's money, and why | Live phone | 1:45–2:30 | 45 |
| 5 | Understand the cover, then one photo | Live, scenario illness | 2:30–3:20 | 50 |
| 6 | Track it, resolve it | Live, scenario illness_mismatch and `/claims` | 3:20–4:05 | 45 |
| 7 | Every number shows where it came from | Slide, or the receipt | 4:05–4:35 | 30 |
| 8 | Code decides the money | Live, scenario buy_cover and `/audit` | 4:35–5:15 | 40 |
| 9 | AI that says what it is | Slide, with the header badges | 5:15–5:40 | 25 |
| 10 | Business model and the honest price | Slide | 5:40–6:10 | 30 |
| 11 | What this is not, yet | Slide | 6:10–6:40 | 30 |
| 12 | The ask | Slide | 6:40–7:00 | 20 |
| 13, 14 | Backup slides for questions | Slide | after 7:00 | none |

**If the cut runs late, drop in this order:** (1) the Zone 9 line and the Z7 panel click on slide 3; (2) the dispute on slide 4; (3) the officer's approval on slide 6, showing only the referred evidence; (4) slide 7 down to one sentence; (5) slide 9 down to one sentence. Never drop slide 11 or slide 12.

### 2.2 Three-minute cut (180 seconds)

| Slide | Beat | Mode | Time | Seconds |
|---|---|---|---|---|
| 1 | Hook | Slide | 0:00–0:30 | 30 |
| 3 | The claim starts itself | Live `/live` | 0:30–1:15 | 45 |
| 4 | Anil's money, and why | Live phone | 1:15–2:10 | 55 |
| 8 | Code decides the money (slide only) | Slide | 2:10–2:40 | 30 |
| 12 | Honest close and the ask | Slide | 2:40–3:00 | 20 |

**Replay timing (both cuts).** The replay from 13:30 to the pause at 17:06 takes about 43 seconds at the default speed, because "Slow near payout" (BUILT) slows 16:58 to 17:06 to 1 simulated minute per second. From 14:00 it takes about 38 seconds, and from 14:30 about 33. The 3-minute cut seeks to 14:30 before Play and the 7-minute cut to 14:00, so the live segment fits its slot. Rehearse both. The Overview's "Watch the storm replay" launcher (BUILT) runs 16:57 to 17:06 in about 9 seconds. Keep it as a last resort, because it skips the build-up.

## 3. The slides

### Slide 1 · One rainy Tuesday (hook)

**Mode:** slide · **7-minute** 0:00–0:30 · **3-minute** 0:00–0:30 · **Message:** a rainy day costs a shop its income, and the instalment still comes out.

**On-slide text**
- Headline: "Rain halves his sales. The instalment still comes out."
- "Anil Jadhav · tea stall · Parel, Mumbai"
- Tag: "Synthetic persona in our simulated replay"
- Three figures: "₹4,380 · his usual Tuesday" / "37% · his ward's sales against expected, for 3 hours" / "₹600 · instalment cut from the evening settlement"
- Footer: "Earlier merchant plans: 30 to 60 days per claim and several documents." Source line: "Source: Assurekit–Paytm case study (A3)".

**Visual:** one-day strip for Tue 19 Aug 2025, 08:00 to 20:00. Grey line: Z7's expected sales. Navy line: actual sales, falling from 14:00. Red band from 14:00 (the alert). A tick at 17:00 and a marker for the ₹600 at the evening settlement. Draw it from the hourly values in the `GET /api/zones/Z7` panel. Fallback still: the overview hero ([desktop-overview.png](../assets/screens/desktop-overview.png)).

**Speaker notes** (the [DEMO.md](../DEMO.md) hook, word for word)
> "Anil runs a tea stall in Parel. On a day of heavy rain his sales fall by more than half, and his ₹600 loan instalment is still cut from his settlement. Getting paid for a day like that has typically taken 30 to 60 days of forms and documents. Paytm already sees his sales fall, as it happens. With Chhatri, the claim starts itself, and he is paid the same evening."

The 30 to 60 days is what the case study reports for Paytm's earlier merchant plans (A3). We have no figure for a current plan's claim time, so do not say "today" or "Paytm's current plan takes".

**Operator:** nothing. Console loaded on the monsoon scenario, paused at 13:30, on `/live`.

**If hidden:** nothing depends on new work.

### Slide 2 · One line, four stages (7-minute only)

**Mode:** slide · **7-minute** 0:30–0:50 · **Message:** Chhatri answers the track's claims journey end to end.

**On-slide text**
- Headline: "Income cover where the claim starts itself"
- Four stages in a row, one line each (use the variant that is on at the freeze):

| Stage | If shipped | Built today |
|---|---|---|
| Understand coverage | "Your cover in plain words. Tap any term." | "The rules and the payout table, in the console" |
| Submit documents | "Rain: nothing to submit. Illness: one photo, checked before it is sent." | "Rain: nothing to submit. Illness: one photo of the slip." |
| Track the claim | "Detected, Checked, Decided, Paid, EDI holiday, with the reason at each step." | "Status chips in the chat, and the case in the claims console." |
| Resolve queries | "Why this amount. Ask a question. A person within 24 hours. A grievance ladder." | "Why this amount. Dispute. A person within 24 hours." |

- Footer: "Hospital cash is our version of the track's health-claims example: income lost while the owner is in hospital."
- The four stage names become a thin footer strip on slides 3 to 8, with the current stage in bold (a "you are here" device, credited on slide 14).

**Visual:** the four-stage strip. No screenshots.

**Speaker notes**
> "The track asks for four stages of a claims journey: understand the cover, submit documents, track the claim, resolve queries. We will walk all four, starting with a claim nobody files."

**Depends on:** N1 and H20 (wave 1), N3 and H15 (wave 2), N5 (wave 3). **If hidden:** use the built column for that row.

### Slide 3 · The claim starts itself

**Mode:** LIVE on `/live` · **7-minute** 0:50–1:45 · **3-minute** 0:30–1:15 · **Message:** a weather alert and a ward-wide sales drop, together, start the claim. Nobody files.

**On-slide text** (shown for the first few seconds, and as the fallback still)
- Headline: "17:00 · three wards · nobody filed anything"
- Three conditions: "A red alert covers the ward" / "Sales below 50% of expected for 3 hours, and below the model's range" / "At least 20 shops in the index"
- Tiles: "3 zones triggered · 312 shops paid · 4 min trigger to money (simulated clock)"
- Footer: "Mumbai monsoon replay · simulated sales · real Open-Meteo rainfall · 6 simulated minutes per second"
- Journey strip: Submit documents, "none needed for an area claim".

**Visual:** the live console. Fallback still: capture `/live` at 17:06 with Z7 selected (the Z7 panel rows: Alert, Sales, Cover, Paid, Total). The stored [desktop-live.png](../assets/screens/desktop-live.png) shows the 08:00 state, so it is not the fallback.

**Speaker notes** (the [DEMO.md](../DEMO.md) and runbook wording)
> "This is Mumbai, ward by ward, in our monsoon replay: real rainfall, simulated shop sales. A red rain alert covers three wards from 14:00. Watch their sales."

(Operator presses Play on "Watch their sales".)

> "The drop held for three hours across all 46 shops in Zone 7, below 50% and below the bottom of the model's range, during the alert. No one filed anything."
>
> "312 shops, paid four minutes after the trigger, with the evening settlement."
>
> "Zone 9 also dipped, but it had no alert. A slow day is not a loss event."

Say "37%", never the round-1 deck's 41%. The clock label reads simulated; the "four minutes" is simulated time.

**Operator:** [runbook](demo-runbook.md) section 3, with one change for timing. Seek to 14:00 (14:30 in the 3-minute cut) before the cue, press Play on the cue, pause at about 17:06, click **Z7**, point at the Zone 9 panel. Keep "Slow near payout" on. If the replay is late, the Overview's "Watch the storm replay" launcher loads the monsoon at 16:57 and pauses at 17:06.

**If hidden:** the projector polish and the moment card (wave 4) are extras. Show the console as it is.

### Slide 4 · Anil's money, and why

**Mode:** LIVE on `/merchant/S-0142` (or the mini-app if it passed rehearsal) · **7-minute** 1:45–2:30 · **3-minute** 1:15–2:10 · **Message:** the merchant is told in his own language, and every number can be checked.

**On-slide text**
- Headline: "₹1,380, with tonight's settlement. No claim needed."
- Formula, large: "½ × ₹4,380 × 63% = ₹1,380"
- Under it: "his usual Tuesday · his area's drop · half the lost sales"
- Instalment line, one of:
  - If the lender-decides wording (X4) shipped: "Chhatri asks his lender to pause tomorrow's ₹600 instalment. The lender decides. In this replay the lender is simulated."
  - Built today: "Tomorrow's ₹600 instalment: paused in the simulation. A real lender would decide."
- Journey strip: Resolve queries, "why this amount".

**Visual:** Anil's phone at 17:05 with the Hindi payout message, the ₹1,380 card, the Soundbox strip and the "why" reply. Re-capture at 17:05 ([phone-merchant.png](../assets/screens/phone-merchant.png) shows 08:00). The Soundbox is simulated and labelled on screen.

**Speaker notes**
> "Anil's phone: ₹1,380, credited with today's settlement, and the Soundbox says it out loud. He asks: 'Why did I get only this much?'"
>
> "His usual Tuesday is ₹4,380, his area fell 63%, and Chhatri pays half the lost sales. Every number can be checked."
>
> "Chhatri also asks his lender to pause tomorrow's ₹600 instalment. In this replay the lender is simulated and says yes. A real lender decides."

7-minute only (the EXPLAINED test, tap **dispute**):
> "Anil says his loss was bigger. Chhatri doesn't argue and doesn't change the amount. It sends the case to a claims officer, who answers within 24 hours."

3-minute only, to close the beat: "Half of ₹4,380 times 63% is ₹1,380. The AI builds the case; code decides the money."

**Operator:** open `/merchant/S-0142`, tap the voice chip **why**, then **dispute** (7-minute). The built chat line says "Tomorrow's ₹600 instalment is paused." until X4 lands. Do not read it as Chhatri's act: use the notes above.

**If hidden:** the phone in the console is the built fallback. The numbers are identical.

### Slide 5 · Understand the cover, then one photo

**Mode:** LIVE, scenario `illness` · **7-minute** 2:30–3:20 · **Message:** stages one and two. The merchant understands the cover and, for illness, submits one photo that is checked before it is sent.

**On-slide text**
- Headline: "One photo of the slip. Checked before it is sent."
- Slip card: "Anil R. Jadhav · KEM Hospital, Parel · admitted 20 Aug · viral fever" (the sample slip, labelled SAMPLE)
- Three checks: "Readable" / "Name matches KYC (ANIL RAMESH JADHAV)" / "Dates match the silent day"
- Result: "½ × ₹4,300 = ₹2,150 a day, capped at ₹1,500 × 1 day = ₹1,500"
- Side note, if shipped: "Before the photo: what is covered, the caps and the 7-day wait, in plain words. Tap any term."
- Journey strip: Understand coverage and Submit documents.

**Visual:** the phone with the check-in, the slip bubble and the decision card. If the pre-check shipped, show its checklist before the decision. The three checks also appear on the decision in the built console.

**Speaker notes** (the DEMO.md and runbook wording)
> "Thursday. Anil's shop had no sales all of Wednesday while his area was normal. Nobody filed a claim: Chhatri checks in first." … "He's in hospital. One photo of the slip." … "The slip reader takes the name and dates; the policy engine checks them against KYC and the silent day. Half his usual Wednesday is ₹2,150, capped at ₹1,500 a day. ₹1,500, credited with today's settlement."

If shipped, add: "Before the photo goes in, he can read what the cover says in plain words. The app checks the photo is readable and shows what it read before anything is decided. If it is not readable, it asks for another photo instead of guessing."

If the vision badge reads SIMULATED, say "the slip reader", never "the AI model read it live".

**Operator:** load **illness**, seek 11:15, Play to the 11:20 check-in, pause, tap **ill**, send the sample slip, then Play (or step 5 minutes) for the credit at +4 minutes and the instalment step at +5. The Overview's "Play the illness claim" launcher (BUILT) loads **illness**, seeks 11:20 and opens Anil's phone with the **ill** chip highlighted, in one click. Rehearse whichever you use.

**Depends on:** N1 coverage explainer and H20 (wave 1), N3 pre-check and H15 (wave 2), N4 voice (wave 2). **If hidden:** the built phone, chips and sample slip. Skip the microphone.

### Slide 6 · Track it, resolve it

**Mode:** LIVE, scenario `illness_mismatch` and `/claims` · **7-minute** 3:20–4:05 · **Message:** stages three and four. The merchant sees where the claim is, and a doubtful claim goes to a person.

**On-slide text**
- Headline: "A name that does not match goes to a person."
- Tracker, if shipped: "Detected, Checked, Decided, Paid, EDI holiday" with the branch "Referred: a claims officer decides". Built today: "Sent to a claims officer · case C-2291".
- Officer evidence: "Slip: Sunil Pawar · KYC: ANIL RAMESH JADHAV · the name check fails · no money moves until a person decides"
- Resolve: "Why this amount · a question · a person within 24 hours". If the grievance ladder shipped, add "Insurer officer, then Bima Bharosa, then the Insurance Ombudsman, with response clocks".
- Journey strip: Track the claim and Resolve queries.

**Visual:** `/claims`, case **C-2291**, evidence view (slip image, extracted name, KYC name, match score, checks). If shipped, the tracker next to it.

**Speaker notes** (the HUMAN test)
> "Same story, but the slip says Sunil Pawar. The name doesn't match Anil's KYC, so no money moves. A claims officer sees the slip, the extracted name, the KYC name and the checks, and approves. The engine re-runs every hard check before it pays."

If shipped, add: "In the app Anil follows the same claim step by step, with the reason at each step." If Ask Chhatri shipped, add: "He can ask a question and get an answer built from the decision's own numbers." Do not mention the grievance ladder unless it is on screen.

**Operator:** load **illness_mismatch**, seek 11:15, Play to 11:20, pause, tap **ill**, send the mismatch slip. Open `/claims`, case C-2291, tap **Approve**, step 5 minutes. The Overview's "Review the slip mismatch" launcher (BUILT) loads **illness_mismatch**, seeks 11:20, sends the voice reply and the mismatch slip, and opens `/claims`, which shortens this.

**Depends on:** N1 tracker (wave 1), N2 (wave 2), N5 and H22 (wave 3). **If hidden:** the built chips and the console.

### Slide 7 · Every number shows where it came from

**Mode:** slide, or the receipt on screen · **7-minute** 4:05–4:35 · **Message:** trust. Sources on every number, a counterfactual on every explanation.

**On-slide text, if shipped**
- Headline: "Every number says where it came from. Every decision says what would have changed it."
- Receipt rows: "Decision: APPROVED, ₹1,380" · "Formula: ½ × ₹4,380 × 63% = ₹1,380" · "Rules: pilot-0.1, with the clause" · "Sales index: 37% (SIMULATED)" · "Alert: A-20250818-01 (SIMULATED)" · "Audit entry: the first 12 characters of its hash"
- Counterfactual (proposed wording, written by the engine, not a language model): "Z9 fell to 61% with no alert. With an alert and 3 hours below 50%, it would have paid."
- Footnote: "A source badge says where a value came from. It does not claim that an outside body verified it."

**On-slide text, built today**
- Headline: "Every panel says what it is, and why Zone 9 got nothing."
- The Z7 panel rows: "Alert · Red alert from 14:00", "Sales · 37% of expected for 3 hours", "Cover · 46 of 46 prepaid", "Paid · 17:04, with the settlement", "Total · ₹58,900 · instalments paused"
- "Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That's a slow day, not a loss event, so Chhatri doesn't pay."

**Visual:** the trust receipt (capture after wave 1), or the Z7 panel and the Zone 9 panel from `/live`.

**Speaker notes, if shipped**
> "Every number on this card says where it came from: the rules version, the sales index, the alert, KYC. Every explanation says what would have changed the outcome, and the engine writes that line, not a language model. Zone 9 got nothing because there was no alert. With an alert and three hours below half, it would have paid."

**Speaker notes, built today**
> "Every number on this panel says what it is: the alert, the sales, the cover, the payment. And Zone 9 says why it got nothing: no alert, so a slow day, not a loss event."

**Depends on:** H13, H14 and the receipt endpoint (wave 1). **If hidden:** the built version.

### Slide 8 · Code decides the money

**Mode:** LIVE for the 7-minute cut (scenario `buy_cover`, then `/audit`); slide only for the 3-minute cut · **7-minute** 4:35–5:15 · **3-minute** 2:10–2:40 · **Message:** who decides the money, three tests that must hold, a chain that can be checked.

**On-slide text**
- Headline: "The AI builds the case. Code decides the money."
- The payout-authority table (SPEC §9.4, as the console's `/policy` page shows it):

| Case | Chhatri alone | Goes to a human |
|---|---|---|
| Area drop during an alert, index clear | Pays | Only if the merchant disputes |
| Personal claim, slip matches name and dates | Pays up to the daily cap | Anything above the cap (more than 3 automatic days) |
| Slip unclear or dates don't match | Never | Always |
| Cover bought after an alert | Never | Waiting period applies |

- Three tests: "My loss was bigger than that." EXPLAINED, numbers shown, a human offered · "A hospital slip with a different name" HUMAN, no automatic payout · "Red alert tomorrow. Cover me today." BLOCKED, new cover starts after the waiting period.
- "Audit chain: valid" (live, 7-minute cut).

**Visual:** the `/policy` table; then `/audit` with **Verify chain**.

**Speaker notes, 3-minute cut**
> "Who decides the money? An area drop: Chhatri pays, and a person looks only if the merchant disputes. An unclear slip: a person decides. Cover bought once a storm is forecast never covers that storm. The AI never has authority over money. Code decides."

**Speaker notes, 7-minute cut**
> "Who decides the money? An area drop: Chhatri pays, and a person looks only if the merchant disputes. An unclear slip: a person decides."
>
> "Monday evening, a red alert for tomorrow has just been issued. Ramesh asks for cover. New cover starts after the 7-day waiting period, from 25 August, so it won't apply to tomorrow's alert. He can still buy cover for later."
>
> "Every step is hash-chained, and the chain check reads valid. The AI builds the case; code decides the money."

Ramesh's link shows ₹424.80 for 30 days (₹14.16 a day, from the backtest; pricing is open). Do not quote a price beyond what the screen shows.

**Operator:** load **buy_cover**, open `/merchant/S-0907`, tap **cover**. Then `/audit`, **Verify chain**. If a click misbehaves, the console's built jump for this story loads **buy_cover**, seeks 18:10 and opens `/merchant/S-0907` with the **cover** chip highlighted (it is behind the "Red alert tomorrow. Cover me today." card on the Overview).

**If hidden:** nothing here depends on new work.

### Slide 9 · AI that says what it is

**Mode:** slide, with the header badges visible · **7-minute** 5:15–5:40 · **Message:** AI where it helps, bounded, and labelled.

**On-slide text, if shipped** (show only the chains that are on)
- Headline: "AI that says what it is."
- "Ask Chhatri: Gemini free tier, then Sarvam, then fixed templates"
- "Slip reading: Gemini free tier, then Sarvam Vision, then a person decides"
- "Voice: Sarvam, then browser speech, then tap-to-send chips"
- Badge legend: "LIVE · SIMULATED · FALLBACK. Every reply shows its mode, its provider and, if a backup stepped in, why."
- Rules: "Words, not money: the engine decides." · "Free tiers see synthetic data only." · "Accuracy: not measured yet. Shown on /evals only after a stored run."

**On-slide text, built today**
- Headline: "AI that says what it is."
- "Sarvam speech, chat and vision: LIVE only when our key is set. Otherwise a labelled simulator runs."
- "Intent detection is a word list. The chat model sees only the text the list cannot classify."
- "Words, not money: the engine decides." · "Free tiers see synthetic data only."

**Visual:** the header badges and the provider panel, captured on the demo laptop after the key check, with at least one component showing SIMULATED or FALLBACK, so the labels are seen to work. The stored overview and live screens show "Simulated · 15" in the header.

**Speaker notes** (this is also where the "what is real" disclosure is said)
> "What runs live here: the policy engine, the forecast model, the audit chain and the claims console. [Say that Sarvam speech and slip reading are live only if their badges read LIVE.] Simulated and labelled: shop sales, the alert feed, WhatsApp, the Paytm payment link, KYC, payouts, the lender and the Soundbox. Language models talk to people. They never decide money, and every AI reply shows its mode."

If the provider panel shipped, add: "and, if a backup stepped in, why." If the evaluation page shipped and has a stored run, read the figures off the screen with their n. Never quote a number from the [AI evaluation plan](../04-engineering/ai-evaluation-plan.md): it is a plan, and nothing in it has been measured.

**Depends on:** N2, N3, N4, X6, H26 (wave 2); H25 and `/evals` (wave 3). **If hidden:** the built version.

### Slide 10 · The business model and the honest price

**Mode:** slide · **7-minute** 5:40–6:10 · **Message:** who pays and who earns; the price is the open question.

**On-slide text**
- Headline: "The price is the open question."
- Left, who does what: "A partner insurer would underwrite (to be approached)" · "Paytm Insurance Broking would distribute (IRDAI broker licence)" · "Paytm: sales data, settlement rail, Soundbox" · "The lender grants or refuses the instalment holiday"
- Right, bar chart: the daily premium of each of the 24 zones, from ₹6.93 (Z21) to ₹38.82 (Z8), with a thin line at ₹2 labelled "Paytm's existing merchant plan: under ₹2 a day". Caption: "Prototype prices from simulated sales. Not a quote. Different cover, different trigger."
- Numbers: "Z7, one year: ₹6,796 of premium, about ₹4,418 of expected area payouts, a 65% loss ratio by construction" · "Hospital cash: not priced yet"
- Footer: "The pilot sets the price: a shadow phase first, then a live pilot with stop rules (loss ratio above 90% or below 30%)."

**Visual:** the bar chart, drawn from `backend/artifacts/premiums.json` (24 values, in paise per day). Z3 is ₹14.16 and Z7 is ₹18.62; label those two.

**Speaker notes** (the honest pricing answer)
> "A partner insurer would underwrite, and Paytm's insurance broker would distribute. We priced each zone from our own simulated losses: about seven to thirty-nine rupees a day. Paytm's existing merchant plan costs under two. We don't know whether merchants will pay several times more for income cover that pays the same evening. That is what the pilot is designed to find out. Hospital cash isn't priced yet."

If asked, go to Q52 to Q55 in [pitch and judge Q&A](pitch-and-judge-qa.md). Do not say "a few rupees a day" (the round-1 deck did).

**Depends on:** nothing new. **If hidden:** not applicable.

### Slide 11 · What this is not, yet

**Mode:** slide · **7-minute** 6:10–6:40 · **Message:** the honest limits, said before anyone asks.

**On-slide text**
- Headline: "What this is not, yet."
- "Not tested on real merchants. Sales, alerts, KYC, payouts, the lender, WhatsApp and the Paytm link are simulated and labelled."
- "Not market proof. The backtest uses simulated sales with real rainfall, and its calibration is circular by design."
- "Not agreed with an insurer or a lender."
- "Not measured on real slips."
- Numbers box: "On that replay: real drops paid, 89 of 148 (weather-only trigger: 49 of 148). Payouts with no real drop, 36 of 125 (weather-only: 287 of 336)."
- Small print: "Prototype built 29 Sep–1 Oct (76 commits). Everything since is in the git log. The repository is public. It has no licence yet."

**Visual:** text only, with the backtest table from `/backtest` as an optional inset.

**Speaker notes**
> "We ran the rules over the 2024 and 2025 monsoons: real rainfall, simulated sales. Chhatri paid 89 of 148 real drops against 49 for a weather-only trigger, and 36 of its 125 payouts had no real drop against 287 of 336. The calibration is circular by design: this validates the rules, not the market. No insurer or lender has agreed yet, and slip reading is not measured on real slips."

If asked, the lead is not all rain. Of the 148 real drops, 48 are zone-days of two scripted city-wide shutdown days (one per monsoon) that a rain trigger cannot see, and 50 are slow days with no alert, which Chhatri leaves unpaid by design. On the 50 rain drops, the weather-only trigger paid 47 and Chhatri 41. Go to Q56 and Q57 in the Q&A. Do not claim the backtest proves anything about real merchants.

**Depends on:** nothing. Never cut this slide.

### Slide 12 · The ask

**Mode:** slide · **7-minute** 6:40–7:00 · **3-minute** 2:40–3:00 (spoken close only) · **Message:** a pilot on real merchants.

**On-slide text**
- Headline: "A pilot that tests it on real merchants."
- "1 · A partner insurer and a lender to test the rules with us"
- "2 · Real 2026 monsoon sales, replayed with no payouts, under a data agreement"
- "3 · A shadow phase, then a staged live pilot with stop rules"
- "4 · Merchant data only under purpose-specific consent (DPDP Rules, 2025)"
- "5 · Distribution through Paytm Insurance Broking"
- Close: "Chhatri · the claim starts itself" · "Team Da Goats · Omkar Kadam · Ujjwal Pardeshi" · "Code: github.com/UjjwalPardeshi/Chhatri (public, no licence yet)"
- No URL for the static demo or the video until the repo owner has deployed and the link works.

**Visual:** text only, on the overview's navy ground.

**Speaker notes, 7-minute cut**
> "Chhatri is income cover where the claim starts itself. Paytm already has the live sales, the settlement rail and the lending partners. Our next step is a pilot with a partner insurer and lender, on real sales, with no payouts at first. The code is public on GitHub. Questions?"

**Speaker notes, 3-minute cut**
> "Paytm already has the live sales, the settlement rail and the lending partners. What you saw runs on simulated sales and real rainfall, and no insurer or lender has agreed yet. Our next step is a pilot with both. The claim starts itself."

Say "next step", never "we are working with". Follow the steps in the [go-to-market plan](../05-business/go-to-market-and-pilot-plan.md).

### Slide 13 · Backup: what is real right now

**Mode:** slide, kept up during questions.

**On-slide text**
- "Real code, always: the policy engine, the forecast model, the audit chain, the claims console."
- "Live only when a key is set: Sarvam speech, chat and vision, and Gemini if it shipped. Our only accounts are the Sarvam and Gemini free tiers; we have no WhatsApp or Paytm keys. Read the header badges."
- "Always simulated and labelled: shop sales, alerts, KYC, payouts, the lender, the Soundbox, WhatsApp, the Paytm payment link."
- "Free-tier AI sees synthetic data only."

**Visual:** the header badges, as on the demo laptop at the freeze. Update the Gemini clause to match the badges before the slot.

**Speaker notes:** read it, do not paraphrase. It answers "is that live?" in one glance.

### Slide 14 · Backup: credits and sources

**Mode:** slide, shown on request.

**On-slide text** (project names only, never people; the full list with repository links is in the [competitive landscape](../01-strategy/competitive-landscape.md)). Show only the rows whose idea is on screen at the freeze.

| Project | What we took, or share |
|---|---|
| Nirdesh, SAHAAY, FinSaathi | Journey steps with "you are here" |
| Praman | Source badges, clause citations in answers, the slip pre-check, the grievance router, the honest-wording test, measured test counts |
| One-Tap Credit | A counterfactual in every explanation, clause-grounded answers, no loan offers during distress |
| Vanifi | No loan offers during distress |
| Claim Advocate | The evidence chain, defence against instructions hidden in slips, the merchant confirms what was read |
| FinPath AI | The readiness checklist, the zero-login demo, the what-if panel |
| FINPATH | The readiness checklist, the scam-message warning, the consent activity log |
| Sahaj | Voice confirmation chips, the jargon lens, the next-step bar, the consent activity log, published evaluation |
| Resolve OS | The what-if panel, published evaluation, real operational counts. We share its principle: the model has no authority over money |
| Soundbox Saathi, Rakshak | A mode label on every AI reply, grounded answers |
| AeroFin AI | The jargon lens |

Sources line: "Assurekit–Paytm case study; Paytm Q1 FY27 results; NPR on SEWA; Clarke et al. 2012; Insurance Act 1938 s.64VB; DPDP Rules, 2025; Open-Meteo (CC BY 4.0); DataMeet BMC wards (CC BY-SA 2.5 India)."

FINPATH and FinPath AI are two different projects: say the names exactly.

## 4. Dependencies and fallbacks

Decide each row once, at the freeze, and write it in the rehearsal log.

| Slide | Depends on (wave) | If it is not on at the freeze |
|---|---|---|
| 1 | Nothing new | Not applicable |
| 2 | N1 and H20 (1), N3 and H15 (2), N5 (3) | Use the built column in the stage table |
| 3 | K1 (built). Projector polish and the moment card (4) are extras | The console as it is |
| 4 | K1, K5 (built). N1 receipt and tracker (1). X4 wording (1) | `/merchant/S-0142`, and the built "is paused" line spoken as in slide 4 |
| 5 | N1 explainer (1). N3 pre-check, N4 voice (2) | The built phone, the chips and the sample slip. Skip the microphone |
| 6 | N1 tracker (1). N2 (2). N5 and H22 (3) | The built chips and `/claims` |
| 7 | H13, H14 and the receipt endpoint (1) | The Z7 panel and the Zone 9 sentence |
| 8 | K4, K6, K7 (built) | Not applicable |
| 9 | N2, N3, N4, X6, H26 (2). H25 (3) | The built text: Sarvam only, LIVE only with the key |
| 10 to 12 | Nothing new | Not applicable |
| 13 | X6 provider panel (2), for the Gemini clause | Drop the Gemini clause |
| 14 | Nothing new | Not applicable |

The static demo (N7, wave 5) is built from the same console in mock mode. It needs the repo owner to deploy it. Until it is deployed and the link works, no slide or note carries a URL for it.

## 5. Backup video script (about 2 minutes)

**When it plays:** only if the live demo and the static demo both fail ([runbook](demo-runbook.md) section 6). It is a recording of the real prototype in replay, not an animation.

**How to record**
- Record in wave 5, from the build that will be frozen, on the demo laptop, with the in-process workflow runner. `make demo-check` must pass first. The mock-mode build gives the same numbers and can be used instead.
- Browser at 1280×720, zoom 100%, full-screen window. Click **Enable sound** first so the Soundbox plays. Keep the footer line ("Sales, alerts, KYC, payouts, lender and Soundbox are simulated") in frame in every console shot.
- Record the screen and the narration separately. A free screen recorder and a phone voice memo are enough. Mix in any free editor.
- Burn in English captions from the narration column, because the room may be loud. The Hindi lines are on screen in the product.
- If a feature was hidden at the freeze, delete its shot and lengthen the shots on either side. Never record a half-working screen.
- Keep the file on the demo laptop and on a phone. The repo owner decides where else it is hosted. Add no URL for it to any doc until one exists and the link works.
- Planned length: 1:56. Narration: about 255 words, at 2 to 2.5 words a second.

| Shot | Time | On screen | Caption | Narration |
|---|---|---|---|---|
| 1 | 0:00–0:10 | Title card: "Chhatri" and "Income cover where the claim starts itself" | "Prototype replay · simulated sales · real Open-Meteo rainfall" | "This is Chhatri, from team Da Goats. You are watching a recording of our prototype: shop sales are simulated, the rainfall is real." |
| 2 | 0:10–0:21 | Slide 1 as a still: the day strip and the three figures | "Synthetic persona · ₹4,380 usual Tuesday · ₹600 instalment" | "Anil runs a tea stall in Parel. When heavy rain halves his sales, his ₹600 instalment still comes out. He is a synthetic persona." |
| 3 | 0:21–0:38 | `/live`: a 3-second still of the 14:00 alert, then the Overview's "Watch the storm replay" launcher (16:57 to 17:06 at 1 simulated minute per second). Z7 selected at the end | "Red alert from 14:00 · 17:00 trigger · 17:04 paid · 312 shops · replay clock 6 simulated minutes per second" | "A red alert covers three wards from two o'clock. Their sales stay below half of expected for three hours. At five, the claim starts itself. Nobody files anything. Four simulated minutes later, 312 shops are paid." |
| 4 | 0:38–0:45 | The Zone 9 panel: "Why Zone 9 got nothing" | "Zone 9 · 61% · no alert · no payout" | "Zone 9 dipped too, but no alert covered it. A slow day is not a loss event." |
| 5 | 0:45–0:58 | Anil's phone at 17:05: the Hindi message, the ₹1,380 card, the Soundbox strip, the "why" reply with the formula | "½ × ₹4,380 × 63% = ₹1,380 · Soundbox simulated" | "On Anil's phone: ₹1,380, credited with today's settlement. Why that much? Half of his usual ₹4,380, times the area's 63 percent drop. Every number can be checked." |
| 6 | 0:58–1:12 | Scenario illness: the check-in, the slip, the decision card (with the pre-check checklist if shipped) | "Silent day · one photo · ½ × ₹4,300, capped at ₹1,500 × 1 day = ₹1,500" | "When one shop goes silent, Chhatri checks in first. One photo of the hospital slip; the engine checks the name and dates against KYC. Half his usual day, capped at ₹1,500." |
| 7 | 1:12–1:21 | Scenario illness_mismatch: `/claims`, case C-2291, the evidence | "Name on slip: Sunil Pawar · KYC: ANIL RAMESH JADHAV · referred to a person" | "If the name does not match, no money moves. A claims officer sees the slip and the checks, and decides." |
| 8 | 1:21–1:32 | If shipped: the trust receipt with its sources and the counterfactual line. Otherwise `/audit`, **Verify chain**, then `/policy` | "Every number shows its source · Audit chain: valid" | "Every figure shows its source. Every step is hash-chained, and the chain check reads valid. The AI builds the case; code decides the money." |
| 9 | 1:32–1:42 | The header badges, and the provider panel if shipped | "LIVE only where a key is set · everything else SIMULATED" | "What is live is labelled live. Everything else says simulated: sales, alerts, KYC, payouts, the lender, WhatsApp and the Paytm link." |
| 10 | 1:42–1:56 | Closing card: "What this is not, yet" and "A pilot that tests it on real merchants" | "No insurer or lender has agreed yet · public repository, no licence yet" | "This validates our rules, not the market. No insurer or lender has agreed yet. Next: a pilot with both, on real sales, with no payouts at first. Chhatri: the claim starts itself." |

**Checks before the video is accepted:** every number matches [DEMO.md](../DEMO.md) (₹1,380, 312, ₹4,380, 63%, ₹1,500, C-2291); the simulated labels are readable in every shot; no sentence says live for something simulated; the narration says nothing about partners except that none has agreed.

## 6. Corrections to carry from the round-1 deck

The round-1 deck ([PDF in the repository root](../../Chhatri%20%C2%B7%20Build%20for%20India%20AI%20Hackathon%20%C2%B7%20Track%202.pdf)) was written before the audit. Do not copy these into the final deck.

| Round-1 deck | Say instead |
|---|---|
| Slide 6: "Z7 · 41%" on the live heat map | 37%, which gives the 63% drop and the ₹1,380 payout |
| Slide 13: "What is live: Sarvam voice, the policy engine, WhatsApp, the claims console and the Paytm premium link (staging)" | The wording on slide 13 of this deck. WhatsApp and the Paytm link are SIMULATED; Sarvam is live only with a key |
| Slide 13: "Premium paid with a real Paytm link (staging)" as a goal for 3 October | Drop it. The link is `https://paytm.me/sim-…`, labelled SIMULATED |
| Slide 12: "How it's priced: a few rupees a day" | The price is open. The prototype gives ₹6.93 to ₹38.82 a day on simulated sales |
| Slide 12: "Data for Pi: a live area income index" | Drop it. It is a roadmap idea, not a Paytm product |
| Slide 1: phone header "Hindi, Marathi, English" | "Hindi, English" until Marathi (N8, wave 4) ships |
| Slide 4: "6 · Learn: every payout, dispute and review sharpens the triggers" | Officers see similar past cases, and the backtest reports trigger health. Nothing retrains the triggers |
| Slide 9: "Premium paid through the Paytm MCP server (staging)" and "n8n workflows" | The link is simulated on stage, and the in-process workflow runner is used, so the n8n badge reads SIMULATED |
| Slide 4: "AI reads the slip; name matches KYC; dates match the silent days" | "The slip reader" unless the vision badge reads LIVE |

## 7. Rehearsal checks for the deck

1. **Timing.** Run each cut twice with the operator. The tables in section 2 add up to exactly 7:00 and 3:00, so aim for 6:45 and 2:50. Time the slides and the live segments separately.
2. **Numbers.** Read every number against the golden table in [DEMO.md](../DEMO.md). Zone 7 is 37%.
3. **Words.** Read the notes against the "things never to say" table in [pitch and judge Q&A](pitch-and-judge-qa.md) section 7.
4. **Badges.** Write the LIVE list down before the cut. Slides 9 and 13 must match it.
5. **Flags.** For each row in section 4, record shipped or hidden, and use the matching text.
6. **Assets.** Capture or draw: the day strip (slide 1), `/live` at 17:06 (slide 3), the phone at 17:05 (slide 4), the receipt if shipped (slide 7), the header badges (slides 9 and 13), the premium bar chart (slide 10). Owner: Omkar Kadam. Use stills from the frozen build, not from an earlier one.

## Open questions

1. **Slot.** Which cut do we run when the slot length is announced? Owner: Omkar Kadam.
2. **Tool.** Which free slide tool builds the deck, and who exports the offline PDF? Proposed: Omkar Kadam, any free tool, PDF export after the freeze.
3. **Static demo link.** Slide 12 and the video carry no URL until the repo owner has deployed N7 and the link works. Owner: Ujjwal Pardeshi.
4. **Lender wording.** Slide 4 uses the lender-decides sentence either way. Should the built "is paused" line also change before the final, if X4 does not land? Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v1 · first version: 14-slide outline with on-slide text, visuals, notes and timing for the 7-minute and 3-minute cuts; dependencies and fallbacks; a backup video script of about 2 minutes; corrections to carry from the round-1 deck
