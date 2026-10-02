# Copy deck: every new string for the P0 work

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 · Every new string is PROPOSED and ships in waves 1 to 4 behind feature flags. Built strings are quoted from the code. Marathi is a draft |
| Owner | Omkar Kadam (copy, mini-app) with Ujjwal Pardeshi (catalogue keys, honest-wording checks) |
| Audience | Frontend and backend engineers, designers, the native-speaker reviewer, compliance |
| Related | [Conversation design](conversation-design.md) · [Design system](design-system.md) · [Screens and flows](screens-and-flows.md) · [Merchant mini-app](../02-product/feature-specs/fs-04-merchant-mini-app.md) · [Ask Chhatri](../02-product/feature-specs/fs-05-ask-chhatri.md) · [Explanations, disputes and grievance](../02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md) · [Cover purchase and consent](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md) · [Policy engine and audit](../02-product/feature-specs/fs-09-policy-engine-and-audit.md) · [Policy wording](../02-product/policy-wording-and-cis.md) · [Implementation guide](../04-engineering/implementation-guide.md) · [AI evaluation plan](../04-engineering/ai-evaluation-plan.md) |

## TL;DR

- This deck holds every new string a merchant sees in the P0 work: 668 strings, each with a stable key, English, Hindi and Marathi. It also holds the Marathi drafts of the 51 built catalogue keys (Appendix A) and the English-only strings of the officer console (section 16).
- Everything is P0. It ships in waves 0 to 5 behind feature flags (section 1.4). A feature that is not finished is hidden, never shown half-working, and its strings are not loaded.
- BUILT strings are quoted exactly from `backend/chhatri/conversation/messages.py` (Appendix A) and from the code (Appendix B). Every other string is PROPOSED.
- Marathi is a draft and needs a native speaker's review. New Hindi lines should also be read by a Hindi speaker outside the team before the final.
- Numbers that come from the rules never sit inside a string. A string carries a placeholder, and the rules or the engine's facts fill it. Demo numbers appear only in worked examples, and those rows say so.
- No string promises money or approval. Words such as approved or मंज़ूर appear only in strings that are shown after a decision record exists.
- Keys: UPPER_CASE keys are catalogue keys to add to `messages.py`. Dotted lower-case keys are mini-app and console strings.
- The feature specs point here for final wording. Section 1.7 maps the keys they use to the keys of this deck, and section 1.8 lists the places where this deck chose between two specs.

## 1. How to use this deck

### 1.1 Statuses, keys and languages

| Item | Rule |
|---|---|
| BUILT | The text exists in the code today. English, and Hindi where the catalogue has it, are quoted exactly. Where a row mixes built and new text, the last column says which. |
| PROPOSED | New text for the P0 work. Nothing here is in the code yet, and nothing here may be shown before its wave and its flag are on. |
| Languages | `en`, `hi`, `mr`. The catalogue today has `hi` and `en` only (`LANGUAGES` in `messages.py`). The domain `Language` enum already has `mr`. |
| Catalogue keys | UPPER_CASE, for text the backend renders. Language-specific facts carry a suffix: `{date_en}`, `{date_hi}`, `{date_mr}`. The backend renders all languages at once. |
| Mini-app keys | Dotted lower-case, for text the frontend renders. A plain `{date}` is formatted by the UI in the active language. |
| Chips | Reply-button titles are at most 20 characters and at most 3 per message (WhatsApp limits, BUILT in `whatsapp_payloads.py`). A tapped title is replayed as text, so each chip must classify as intended (section 8.3). |
| Status tokens | LIVE, SIMULATED, FALLBACK and CONFIG are never translated. |

### 1.2 Rules for writing a string

1. One idea per message. Short sentences. Plain words.
2. Respectful आप. Honorific जी after a name in catalogue messages that address the merchant by name. New Hindi and Marathi lines avoid gendered first-person verbs, because the built DISPUTE_ACK uses a masculine form (`भेज रहा हूँ`) while Chhatri is feminine elsewhere. The built line is left as it is (open question 7).
3. No digit inside a string unless it is a placeholder, a clause id such as C4.2, or a worked example that is marked as demo numbers. Rules numbers (7 days, 50%, ₹2,500, 85, 0.80) always arrive through placeholders.
4. A counterfactual names only thresholds that are public in the policy wording, and never suggests editing a document or a name ([fs-09](../02-product/feature-specs/fs-09-policy-engine-and-audit.md) section 9.3).
5. No promise words in English, Hindi or Hinglish (`approv`, `guarantee`, `promis`, `will pay`, `मंज़ूर`, `पक्का`, `मिल जाएंगे` and the other stems in the guard) outside strings that are shown after a decision exists. Those strings are marked in the last column.
6. SIMULATED is written in capitals wherever a source or an action is simulated. Nothing simulated is shown as live.
7. A source chip says where a value came from. It never says that an outside body verified it.
8. Marathi: plain Marathi in Devanagari, ASCII digits, no nukta. Loan words that merchants already use (कवर, प्रीमियम, सेटलमेंट, KYC) stay.

### 1.3 Fact vocabulary

The placeholders used in this deck, and where each value comes from. The engine and the rules API fill them; a template reads only these.

| Placeholder | Meaning | Comes from |
|---|---|---|
| `{alert_id}` | Alert id, such as A-20250818-01 | alert record |
| `{amount}` | Money, formatted with `format_inr`, such as ₹1,380 | decision or payout |
| `{annual_limit}` | Yearly limit as money | `rules.yaml` `annual_limit_rupees` |
| `{area_cap}` | Daily cap of a rain payout as money | `rules.yaml` `area.daily_cap_rupees` |
| `{cap}` | The daily cap that applied, as money | `rules.yaml` (area or personal cap) |
| `{case_id}` | Case id, such as C-2291 | case service |
| `{clause}` | Clause id: C1 to C12, or a sub-clause such as C4.2 | policy wording |
| `{clauses}` | A list of clause chips | citations of the answer |
| `{code}` | A short reference for support, such as an error code | the error response |
| `{condition}` | One condition fragment from section 6.3 | counterfactual |
| `{cyber_helpline}` | National cyber crime helpline number | configuration, to be checked before use |
| `{cyber_portal}` | National cyber crime reporting portal address | configuration, to be checked before use |
| `{date}` | A date in the active language, such as 27 August | UI date formatter |
| `{dates}` | One or more dates, joined with commas, in the language of the text | claim or decision facts |
| `{day}` | A day, such as 19 August, in the language of the text | the audit entry |
| `{days}` | A number of days | configuration or the claim |
| `{decision_id}` | Decision id, such as D-000142 | decision record |
| `{delta}` | A money difference between two engine runs | counterfactual re-run |
| `{drop}` | Area drop in percent, an integer | area trigger |
| `{entries}` | Number of audit entries checked | audit chain check |
| `{first_days}` | Days paid in the first payment | `rules.yaml` `premium.first_payment_days` |
| `{floor_pct}` | Payout floor in percent of the usual level | `rules.yaml` `area.index_floor_pct` |
| `{found}` | Number of slip details that were read | slip read |
| `{half_day}` | Half of the usual day as money | amount breakdown |
| `{heard}` | The words that the speech service heard | voice transcript |
| `{hour_values}` | Hourly index values in a row, such as 59%, 58%, 67% | area trigger |
| `{hours}` | A number of hours: consecutive hours or hours left | `rules.yaml` or the case clock |
| `{index_pct}` | Area sales index in percent | area trigger |
| `{instalment}` | Instalment amount as money | loan record |
| `{issued}` | Alert issue time, date and time | alert record |
| `{label}` | The label of a consent purpose, from section 14.2 | consent record |
| `{limit}` | Yearly limit as money | `rules.yaml` `annual_limit_rupees` |
| `{lookahead_hours}` | Hours ahead in which an alert blocks new cover | `rules.yaml` `cover.alert_lookahead_hours` |
| `{max_auto_days}` | Most days paid without a review | `rules.yaml` `personal.max_auto_days` |
| `{max_mb}` | Image size limit in MB | upload limit in the API |
| `{max_seconds}` | Recording limit in seconds | recorder and API limit |
| `{min_shops}` | Fewest shops for a valid index | `rules.yaml` `area.min_shops_in_index` |
| `{minutes}` | Minutes of the simulated payout delay | `rules.yaml` `payout_rail_delay_minutes` |
| `{n}` | Number of characters of the audit hash shown | receipt setting |
| `{name}` | The merchant's first name, in the language of the text | merchant record |
| `{name_match_min}` | Lowest name match score, such as 85 | `rules.yaml` `personal.name_match_min_score` |
| `{paid_through}` | The date that the premium is paid through | cover record |
| `{paid_to}` | The date that the premium is paid to, in the language of the text | premium record |
| `{paid_total}` | Payouts in the rolling window as money | payout history |
| `{passed}` | Number of checks that passed | decision checks |
| `{per_day}` | Premium a day as money | cover quote |
| `{personal_cap}` | Daily cap of a hospital-cash payout as money | `rules.yaml` `personal.daily_cap_rupees` |
| `{reason}` | A reason line: a built REASON_ text or a fallback reason line | decision or provider status |
| `{result}` | A result fragment, CF_RESULT_APPROVED or CF_RESULT_REFERRED | counterfactual re-run |
| `{rules_version}` | Rules version, such as pilot-0.1 | `rules.yaml` `version` |
| `{seconds}` | Seconds recorded so far | recorder |
| `{seq}` | Number of an audit entry | audit chain check |
| `{share_pct}` | Payout share in percent | `rules.yaml` `payout_share` |
| `{shops}` | Shops counted in the index | area trigger |
| `{sla_hours}` | Hours to reply to a case | `rules.yaml` `dispute_sla_hours` |
| `{starts_on}` | The date that cover starts, in the language of the text | cover quote or record |
| `{time}` | A time of day, or a date and time | the record shown |
| `{time_left}` | Time left on a clock, in hours and minutes | case clock |
| `{total}` | Number of slip details that can be read | slip read |
| `{used}` | Payouts in the rolling window as money | payout history |
| `{valid_from}` | Start of an alert, date and time | alert record |
| `{valid_to}` | End of an alert, date and time | alert record |
| `{value}` | An amount such as ₹1,500 or a date such as 19 August | mention found in a voice question |
| `{version}` | Version of a consent text | consent record |
| `{waiting_days}` | Waiting period in days | `rules.yaml` `cover.waiting_period_days` |
| `{when}` | When an instalment is due: tomorrow, today or a date | loan instalment date |
| `{window_days}` | Rolling window of the yearly limit in days | policy engine |
| `{zone_number}` | Zone number, such as 9 for Z9 | zone id |

### 1.4 Waves

| Wave | What lands | Sections of this deck |
|---|---|---|
| 0 · setup | X1, feature flags, Tailwind v4 and shadcn set-up, key checks | none |
| 1 · demo spine | N1 core (home, coverage explainer with H20, claim tracker H1, trust receipt H2, H3, H13, H14, H21), X4, X7, X2, X3, X5 | 2, 3, 4, 5.1 to 5.3, 6, 7, 8.1, 13.2 (the two dispute lines), 15 (empty, error, SIMULATED, offline) |
| 2 · live AI | N3 with H15 and H16, N2 with H17, H19 and H21, N4 with H18, X6 with H26 | 5.2 (mode), 8.2, 8.3, 9, 10, 11, 12, 15.5, 16 (provider panel rows) |
| 3 · trust and rights | N5 with H22, N6 with H23, X8, H25 | 13, 14 (and 2.4: the notice and boxes) |
| 4 · judge wow | console polish, H24, presenter mode, H8, N8 Marathi | 16 (the other rows), the Marathi column, Appendix A |
| 5 · ship | N7 static build and backup video, full tests, `make demo-check`, rehearsals, freeze 90 minutes before the slot | 15.3 (static demo banner) |

### 1.5 Terms in three languages

One word per idea, in every string. A native speaker confirms the Marathi column first (section 19).

| English | Hindi | Marathi (draft) |
|---|---|---|
| Chhatri | छतरी | छत्री |
| cover (the protection) | कवर | कवर |
| premium | प्रीमियम | प्रीमियम |
| claim | दावा | दावा |
| payout | भुगतान | रक्कम, भरपाई |
| area | इलाका | परिसर |
| shop | दुकान | दुकान |
| usual day | आम दिन | नेहमीचा दिवस |
| sales | बिक्री | विक्री |
| settlement | सेटलमेंट | सेटलमेंट |
| lender | लेंडर | लेंडर |
| instalment | किस्त | हप्ता |
| waiting period | वेटिंग पीरियड | वेटिंग पीरियड |
| slip | पर्ची | पर्ची |
| alert | अलर्ट | अलर्ट |
| limit | सीमा | मर्यादा |
| complaint | शिकायत | तक्रार |
| insurer | बीमा कंपनी | विमा कंपनी |
| our team | हमारी टीम | आमची टीम |

### 1.6 Checks to automate (X7)

These checks can run over the catalogue and this deck. This deck passes every one of them at v1.

- Every key has all three languages, and the three texts use the same placeholders (a `_hi`, `_en` or `_mr` suffix is ignored).
- No digit outside a placeholder, except in rows marked as demo numbers or structural labels.
- No promise stem in a string that is not marked as shown after a decision.
- Chip titles are at most 20 characters, and each replayed title classifies as the intended intent.
- Hindi and Marathi contain Devanagari, and no Latin words other than the whitelist (KYC, Paytm, Sarvam, Gemini, WhatsApp, Soundbox, EDI, UPI, SMS, AI, OTP, PIN, IRDAI, IMD, status tokens and file types).
- Hindi uses the nukta where the catalogue does; Marathi uses none.

### 1.7 Keys that the feature specs use

The feature specs say that the final wording is in this deck. Where a spec has its own key, this table shows the deck key. A key that is the same in both is listed as same.

| Spec | Key in the spec | Key in this deck | Note |
|---|---|---|---|
| Hospital cash claim | `SLIP_*` (27 keys of section 9.2) | same keys, section 12 | SLIP_NOTICE is reworded (1.8) |
| EDI holiday | `HOLIDAY_GRANTED`, `HOLIDAY_GRANTED_TODAY`, `HOLIDAY_GRANTED_ON`, `HOLIDAY_REFUSED`, `HOLIDAY_NO_RESPONSE`, `HOLIDAY_REASON_*` | same keys, section 3.3 | - |
| EDI holiday | button "Ask the lender about this" | `nba.btn.ask_lender` | section 8.1 |
| Mini-app | `tab.home`, `tab.claims`, `tab.help` | `nav.home`, `nav.claims`, `nav.help` | - |
| Mini-app | `home.no_cover` | `COVER_STATUS_NONE` | the catalogue key of the cover spec, section 2.4 |
| Mini-app | `home.open_coverage`, `home.get_cover` | `home.btn.coverage`, `home.btn.buy` | - |
| Mini-app | `home.greeting`, `home.used`, `home.expected` | same keys | - |
| Mini-app | `claims.title`, `claims.empty` | `tracker.title`, `empty.claims` | - |
| Mini-app | `step.detected`, `step.checked`, `step.decided`, `step.paid`, `step.edi` | `tracker.step.detected`, `tracker.step.checked`, `tracker.step.decided`, `tracker.step.paid`, `tracker.step.edi` | the Hindi of the first four is the spec's |
| Mini-app | `step.edi.requested`, `step.edi.none` | `TRACK_EDI_REQUESTED`, `TRACK_EDI_NONE` | - |
| Mini-app | `claim.why`, `claim.receipt`, `claim.dispute` | `tracker.btn.why`, `tracker.btn.receipt`, `tracker.btn.wrong` | - |
| Mini-app | `receipt.title`, `receipt.check_log` | same keys | - |
| Mini-app | `receipt.print`, `receipt.counterfactual` | `receipt.btn.print`, `receipt.row.what_changes` | - |
| Mini-app | `buy.check`, `buy.simulate`, `buy.pay`, `buy.blocked_note` | same keys | - |
| Mini-app | `help.title`, `help.ask`, `lang.title` | `nav.help`, `ask.title`, `lang.label` | - |
| Mini-app | `err.generic`, `err.not_found`, `err.offline_action` | `error.generic`, `error.not_found`, `offline.blocked` | - |
| Mini-app | `offline.banner` | same key | - |
| Mini-app | `about.text` | `help.about.text` | - |
| Mini-app | status labels of section 14.2 | `claim.status.*`, `buy.outcome.ok`, `buy.outcome.blocked` | section 3.1 and section 2.4 |
| Mini-app | next-best-action rule ids of section 12 | `nba.<rule id>` and `nba.<rule id>.btn` | section 8.1 |
| Mini-app | glossary ids of section 11 | `jargon.<id>.term`, `jargon.<id>.what`, `jargon.<id>.example` | section 7 |
| Ask Chhatri | `ASK_HANDOFF`, `ASK_SCAM_WARNING`, `ASK_MENTION_CHIP`, `ASK_MENTION_WORDS`, `ASK_TOO_LONG`, `ASK_VOICE_NOTICE`, `ASK_OFFLINE` | same keys, section 9.2 | ASK_SCAM_WARNING has one clause more (1.8) |
| Ask Chhatri | `next_action` kinds | `next_action.<KIND>` | section 8.2 |
| Ask Chhatri | fallback reason codes | `fb.reason.<CODE>` | section 15.5 |
| Ask Chhatri | voice states: Idle, Notice, Recording, Transcribing, Heard nothing, Confirm, Not available | `voice.state.idle`, `ASK_VOICE_NOTICE`, `voice.state.listening`, `voice.state.processing`, `VOICE_UNCLEAR`, `voice.confirm.intro`, `voice.state.fallback` | section 11; VOICE_UNCLEAR is BUILT (Appendix A) |
| Hospital cash claim | next-action kinds `CONFIRM_FIELDS`, `RETAKE_PHOTO`, `SEND_TO_TEAM` | `SLIP_ACTION_CONFIRM`, `SLIP_ACTION_RETAKE`, `SLIP_ACTION_TEAM` | the button labels of the sheet |
| Explanations, disputes and grievance | ladder steps, states and clocks (no keys in the spec) | `grv.step.<STEP>`, `grv.what.<STEP>`, `grv.state.*`, `grv.clock.*`, `grv.btn.*` | section 13.1 |
| Explanations, disputes and grievance | topics (no keys in the spec) | `grv.topic.<TOPIC>`, `grv.who.<RESPONDENT>` | section 13.2 |
| Explanations, disputes and grievance | `DISPUTE_NO_PAYOUT`, `DISPUTE_ALREADY_OPEN` | same keys, section 13.2 | - |
| Cover purchase and consent | `COVER_STATUS_NONE`, `COVER_BLOCKED_NOW` | same keys, section 2.4 | - |
| Cover purchase and consent | `COVER_NOTICE`, `CONSENT_WITHDRAWN_SALES`, `CONSENT_WITHDRAWN_SLIP`, `CONSENT_WITHDRAWN_SETTLEMENT`, `SLIP_CONSENT_NEEDED` | same keys, section 14 | - |
| Cover purchase and consent | notice module: `notice`, `box.sales`, `box.settlement`, `box.slip`, `tag.required`, `tag.optional`, `hint`, `error.stale` | same keys, section 14.1 | the keys belong to the notice module, not to the app copy |
| Cover purchase and consent | purpose items: label, data used, effect, re-grant (no keys in the spec) | `purpose.<purpose>.label`, `purpose.<purpose>.data_used`, `purpose.<purpose>.effect`, `purpose.<purpose>.regrant` | section 14.2 |
| Cover purchase and consent | screen strings `consent.*`, `slip.held`, `slip.state.*`, `slip.erase*`, `receipt.erased`, `activity.*` | same keys, sections 14.4 to 14.6 | - |
| Cover purchase and consent | activity sentences by audit action, and the three reason phrases | `activity.<audit action>` and `activity.reason.*` | section 14.5 |
| Officer console | console wording of section 14 | `console.*`, section 17 | English only |
| Policy engine | `CF_<CHECK_CODE>` | `CF_IF_<CHECK_CODE>` for a condition, `CF_EXPLAIN_<CHECK_CODE>` for an explanation-only line | section 6.3 and 6.4 |
| Policy engine | `CF_ZONE_NO_TRIGGER`, `CF_AMOUNT_*` | same keys, section 6.4 | - |
| Policy engine | source kinds of section 8.3 | `src.<KIND>` | section 5.1 |

### 1.8 Where this deck chooses between the specs

Two specs sometimes word the same thing in two ways. The deck picks one, so that the engineers have one text, and the owners of the specs can change the pick.

| Topic | What the specs say | What this deck uses | Why, and who can change it |
|---|---|---|---|
| Counterfactual sentence | The mini-app spec frames it as "It would have paid with: ...". The policy engine spec frames it as "If {condition}, {result}." | The engine spec's frame (`CF_FRAME`). The mini-app shows the sentences that the receipt endpoint returns, so one frame serves both. | One frame in one place. The owners of both specs can change it. |
| Source kinds | The mini-app spec lists 10 kinds (RULE, SALES_INDEX, ALERT, COVER, KYC, SLIP, OFFICER, PAYOUT, LENDER, AUDIT). The engine spec lists 13 (RULES, CLAUSE, ALERT, SALES_INDEX, FORECAST, ZONE_BOUND, COVER, PREMIUM, KYC, SLIP, SALES_DAY, PAYOUT_HISTORY, LENDER). | Labels for the 13 kinds of the engine spec, because the engine builds the sources. The officer, the payout and the audit entry have their own receipt rows (`receipt.by.officer`, `receipt.row.paid_at`, `receipt.row.audit`), not source chips. | The two lists name some kinds differently. The owners of both specs should make them one list. |
| Lender refusal in the tracker | The EDI holiday spec shows the reason in words. The mini-app spec shows "Not available. Your instalment is due as usual." and keeps the reason code in the console. | Both lines exist (`TRACK_EDI_REFUSED`, `TRACK_EDI_REFUSED_WHY`). The chat line HOLIDAY_REFUSED already gives the reason in words, so the tracker should not say less than the chat. | Open question 9. A reason in words is not a reason code, so the mini-app rule is not broken by showing it. |
| Wording of a dated instalment | The EDI holiday spec fills one `{when}` with tomorrow's, today's or the one due on a date. With a date this reads badly in both Hindi and English. | Three granted keys (`HOLIDAY_GRANTED`, `HOLIDAY_GRANTED_TODAY`, `HOLIDAY_GRANTED_ON`), as the built pause messages do. HOLIDAY_REFUSED carries a finished phrase in `{when_en}` and `{when_hi}`. | Same pattern as the built catalogue. |
| Alert sentence | The mini-app spec says that when an alert is in force, Chhatri "pays on its own". | "Chhatri checks the numbers on its own" (`nba.alert_notice`). An alert alone pays nothing; the area trigger decides. | A sentence about an alert should not read as a promise. |
| Step name of the instalment holiday | The mini-app spec calls the step "EDI holiday". | "Instalment holiday (EDI)" in the tracker and in the glossary, so a merchant who does not know EDI can read it. | Wording only. The glossary id stays `edi_holiday`. |
| Open and closed dispute | The mini-app spec says "Dispute open" and "Dispute closed. Amount unchanged." | "Question open" and "Question closed. Amount unchanged.", the same word as the button This is wrong and the heading Question about a payout. | A small merchant does not use the word dispute. The case kind stays DISPUTE in the console. |
| Receipt download | The mini-app spec prints the receipt through the browser's print dialog and has no export feature. | One button, Print or save as PDF. There is no Download or Copy button. | No extra export feature. |
| Slip and voice notices | The hospital cash spec says the photo is sent to an AI reading service (Gemini or Sarvam) and asks for sample slips only. The Ask Chhatri spec says the voice is sent to a speech service and asks for the sample sentences only. | "May be sent", "a sample slip, not a real one" and "Please use the sample sentences". With no key set the read is SIMULATED and nothing goes to an outside service, so "is sent" would be untrue. | The notice must be true in both modes (open question 12). |
| Effect of turning off sales data | The cover and consent spec says that any refund follows the cancellation terms. | "Whether anything is returned, and how much, is set by the cancellation terms (C12)." The word refund is a promise stem in the guard, and the planned honest-wording scan would fail the line. | The same meaning, with no promise stem. |
| Scam warning | The Ask Chhatri spec warns about an OTP, PIN or password and about fees. | One more clause: "or asks you to install an app", so that a remote-access message is covered as well. | The remote-access signal is a strong signal in the same spec. |
| Numbers inside a sentence | The mini-app spec writes "within 24 hours" in the sentence of the rule see_dispute_case. | `{sla_hours}`, so that a change of the dispute clock in `rules.yaml` reaches the screen. | No digit is typed into a string (section 1.2). |
| Spec text copied into the deck | The hospital cash spec (section 9.2) and the cover and consent spec (sections 8.3 and 9.10) already carry English and Hindi. | The deck repeats their English and Hindi (except the slip notice and the sales-data effect above) and adds Marathi. If a spec changes its wording, change the deck row in the same commit. | One text for the engineers. The spec tables are the source until the first commit of this deck. |

## 2. Mini-app: shell, home, coverage explainer, buy (N1, wave 1)

The mini-app sits next to the phone on `/merchant/:id`. It is Tailwind v4 with shadcn, scoped to a `.miniapp` root; the console keeps its plain CSS tokens. The language picker offers हिंदी and English from wave 1 and मराठी when N8 is on (wave 4).

### 2.1 Shell and settings

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `nav.home` | Home | होम | मुख्यपृष्ठ | - |
| `nav.claims` | Claims | दावे | दावे | - |
| `nav.help` | Help | मदद | मदत | - |
| `app.name` | Chhatri | छतरी | छत्री | product name; the Hindi spelling follows the catalogue |
| `app.tagline` | Chhatri in Paytm for Business | Paytm for Business में छतरी | Paytm for Business मधील छत्री | - |
| `app.clock` | Demo date and time: {time} | डेमो की तारीख़ और समय: {time} | डेमोची तारीख आणि वेळ: {time} | facts: `time`; the replay clock, shown in the app bar |
| `app.fullscreen` | Open full screen | पूरी स्क्रीन पर खोलें | पूर्ण स्क्रीनवर उघडा | app bar button on the console |
| `lang.label` | Language | भाषा | भाषा | - |
| `lang.hi` | हिंदी | हिंदी | हिंदी | shown in its own script in every language |
| `lang.en` | English | English | English | shown in its own script in every language |
| `lang.mr` | मराठी | मराठी | मराठी | shown only when N8 is switched on |
| `lang.fallback_note` | Some text is shown in Hindi. | कुछ पाठ हिंदी में दिखाया गया है। | काही मजकूर हिंदीत दाखवला आहे. | shown only while Marathi is chosen and some key has no Marathi text yet; the fallback chain is Marathi, Hindi, English |
| `settings.title` | Settings | सेटिंग | सेटिंग | - |
| `settings.sound.off` | Enable sound | आवाज़ चालू करें | आवाज सुरू करा | BUILT; English line is the BUILT console label |
| `settings.sound.on` | Sound on | आवाज़ चालू है | आवाज सुरू आहे | BUILT; English line is the BUILT console label |
| `settings.privacy` | Privacy and consents | प्राइवेसी और सहमतियाँ | गोपनीयता आणि संमती | - |
| `help.about.title` | About this prototype | इस प्रोटोटाइप के बारे में | या प्रोटोटाइपबद्दल | Help row; always shown |
| `help.about.text` | Prototype. Anil Jadhav and every merchant here are synthetic. Anything marked SIMULATED is not real: sales, alerts, KYC, payouts, lender, Soundbox, WhatsApp and the Paytm link. | यह एक प्रोटोटाइप है। अनिल जाधव समेत यहाँ के सभी दुकानदार काल्पनिक हैं। SIMULATED लिखी हर चीज़ असली नहीं है: बिक्री, अलर्ट, KYC, भुगतान, लेंडर, Soundbox, WhatsApp और Paytm लिंक। | हा एक प्रोटोटाइप आहे. अनिल जाधव यांच्यासह येथील सर्व दुकानदार काल्पनिक आहेत. SIMULATED लिहिलेली प्रत्येक गोष्ट खरी नाही: विक्री, अलर्ट, KYC, रक्कम, लेंडर, Soundbox, WhatsApp आणि Paytm लिंक. | the About row of the Help screen; the list of simulated parts matches the status list of the console |

### 2.2 Home and cover card

The status line follows `CoverStatus` (`PENDING_PAYMENT`, `WAITING`, `ACTIVE`, `LAPSED`, `CANCELLED`) and the premium paid-through date. A merchant with no cover sees the catalogue line COVER_STATUS_NONE (section 2.4). No loan, top-up or cross-sell card appears here while an alert covers the merchant's zone, or a claim, a case or a grievance is open (X8, wave 3); buying cover is not a loan offer, so its button stays.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `home.title` | Your cover | आपका कवर | आपले कवर | - |
| `home.greeting` | Hello, {name} ji | नमस्ते, {name} जी | नमस्कार, {name} जी | facts: `name`; the owner's given name; the ji follows the catalogue |
| `cover.status.pending_payment` | Waiting for your first payment | पहले भुगतान का इंतज़ार | पहिल्या पेमेंटची प्रतीक्षा | CoverStatus.PENDING_PAYMENT |
| `cover.status.waiting` | Starts on {date} | {date} से शुरू होगा | {date} पासून सुरू होईल | facts: `date`; CoverStatus.WAITING (inside the waiting period) |
| `cover.status.active` | Active | चालू | सुरू | CoverStatus.ACTIVE and premium paid through today or later |
| `cover.status.active_unpaid` | Active, premium not paid for the coming days | चालू, आगे के दिनों का प्रीमियम जमा नहीं | सुरू, पुढील दिवसांचे प्रीमियम भरलेले नाही | ACTIVE with prepaid_through before today (same meaning as the BUILT COVER_STATUS_UNPAID) |
| `cover.status.lapsed` | Stopped | बंद | बंद | CoverStatus.LAPSED |
| `cover.status.cancelled` | Cancelled | रद्द | रद्द | CoverStatus.CANCELLED |
| `home.row.zone` | Your area | आपका इलाका | आपला परिसर | - |
| `home.row.premium_per_day` | Premium a day | रोज़ का प्रीमियम | रोजचे प्रीमियम | - |
| `home.row.paid_through` | Paid up to | इस तारीख़ तक जमा | या तारखेपर्यंत भरलेले | - |
| `home.row.starts_on` | Cover starts | कवर शुरू | कवर सुरू | - |
| `home.row.instalment` | Loan instalment a day | रोज़ की लोन किस्त | रोजचा कर्जाचा हप्ता | only when the merchant has a loan |
| `home.used` | Used in the last {window_days} days: {used} of {limit} | पिछले {window_days} दिनों में इस्तेमाल: {used} / {limit} | मागील {window_days} दिवसांत वापर: {used} / {limit} | facts: `window_days`, `used`, `limit`; used is the sum of the rolling window; limit is the yearly limit |
| `home.expected` | Expected sales today | आज की अनुमानित बिक्री | आजची अपेक्षित विक्री | from the published expected day, rounded |
| `home.latest` | Your latest claim | आपका ताज़ा दावा | आपला ताजा दावा | hidden when there is no claim |
| `home.btn.coverage` | What am I covered for? | मुझे किस नुकसान का कवर मिलता है? | मला कोणत्या नुकसानीचे कवर मिळते? | opens the coverage explainer |
| `home.btn.buy` | Get cover | कवर लें | कवर घ्या | X8 does not hide it: buying cover is not a loan offer |
| `home.btn.claims` | See my claims | मेरे दावे देखें | माझे दावे पहा | - |
| `home.btn.ask` | Ask Chhatri | छतरी से पूछें | छत्रीला विचारा | hidden until N2 is switched on |
| `home.alert.banner` | Alert {alert_id} · {valid_from} to {valid_to} | अलर्ट {alert_id} · {valid_from} से {valid_to} तक | अलर्ट {alert_id} · {valid_from} ते {valid_to} | facts: `alert_id`, `valid_from`, `valid_to`; title line of the alert banner; the banner also carries the SIMULATED token while alerts are simulated |
| `home.alert.covered` | A weather alert is on for your area. Chhatri is watching your area's sales. You do not need to do anything. | आपके इलाके के लिए मौसम अलर्ट चालू है। छतरी आपके इलाके की बिक्री पर नज़र रख रही है। आपको कुछ करने की ज़रूरत नहीं। | आपल्या परिसरासाठी हवामान अलर्ट सुरू आहे. छत्री आपल्या परिसरातील विक्रीवर लक्ष ठेवत आहे. आपल्याला काही करण्याची गरज नाही. | merchant has active cover and an alert covers the zone |
| `home.alert.not_covered` | A weather alert is on for your area. New cover starts after the waiting period, so it will not apply to this alert. | आपके इलाके के लिए मौसम अलर्ट चालू है। नया कवर वेटिंग पीरियड के बाद शुरू होता है, इसलिए यह इस अलर्ट पर लागू नहीं होगा। | आपल्या परिसरासाठी हवामान अलर्ट सुरू आहे. नवीन कवर वेटिंग पीरियडनंतर सुरू होते, म्हणून ते या अलर्टसाठी लागू होणार नाही. | merchant has no active cover and an alert covers the zone; same meaning as the BUILT COVER_BLOCKED |

### 2.3 Coverage explainer (H20)

The sections follow the mini-app spec: c2 rain and lost sales, c3 hospital cash, c4 how much Chhatri pays, c5 when cover starts, c6 premium and prepaid days, c7 when a claim is not paid, c10 your loan instalment. Each has a clause chip. Numbers come from the rules API (`rules.yaml`, version `pilot-0.1`), never from the strings, and a rules change reaches the screen. Underlined words open the jargon lens (section 7). The rules are illustrative; a partner insurer would set the real terms.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `explain.title` | What am I covered for? | मुझे किस नुकसान का कवर मिलता है? | मला कोणत्या नुकसानीचे कवर मिळते? | heading of the coverage explainer |
| `explain.numbers.title` | Your cover in numbers | आपका कवर, आँकड़ों में | आपले कवर, आकड्यांत | every figure comes from the rules API |
| `explain.num.share` | Chhatri's share of lost sales | खोई हुई बिक्री में छतरी का हिस्सा | गमावलेल्या विक्रीतील छत्रीचा वाटा | value: share_pct as a percentage |
| `explain.num.area_cap` | Daily limit, rain | रोज़ की सीमा, बारिश | रोजची मर्यादा, पाऊस | value: area_cap |
| `explain.num.personal_cap` | Daily limit, hospital cash | रोज़ की सीमा, अस्पताल | रोजची मर्यादा, रुग्णालय | value: personal_cap |
| `explain.num.annual` | Yearly limit | साल की सीमा | वार्षिक मर्यादा | value: annual_limit |
| `explain.num.waiting` | Waiting period | वेटिंग पीरियड | वेटिंग पीरियड | value: waiting_days |
| `explain.num.lookahead` | Alerts checked this far ahead | इतने घंटे आगे तक अलर्ट देखे जाते हैं | इतक्या तास पुढेपर्यंत अलर्ट पाहिले जातात | value: lookahead_hours |
| `explain.num.first_days` | First payment covers | पहला भुगतान इतने दिन के लिए | पहिले पेमेंट इतक्या दिवसांसाठी | value: first_days |
| `explain.c2.title` | Rain and lost sales | बारिश से बिक्री का नुकसान | पावसामुळे विक्रीचे नुकसान | section c2; clause chip C2 |
| `explain.c2.body` | When a weather alert is on, your area's sales stay below {floor_pct}% of the usual level for {hours} hours in a row, and the fall is bigger than an ordinary slow day, Chhatri pays {share_pct}% of your shop's lost sales, worked out from your usual day and the area's drop. The most is {area_cap} a day. You do not need to file anything. | जब मौसम अलर्ट चालू हो, आपके इलाके की बिक्री लगातार {hours} घंटे आम स्तर के {floor_pct}% से नीचे रहे, और गिरावट आम धीमे दिन से ज़्यादा हो, तब छतरी आपकी दुकान की खोई हुई बिक्री का {share_pct}% देती है। यह हिसाब आपके आम दिन और इलाके की गिरावट से बनता है। एक दिन में ज़्यादा से ज़्यादा {area_cap}। आपको दावा नहीं करना पड़ता। | हवामान अलर्ट सुरू असताना आपल्या परिसरातील विक्री सलग {hours} तास नेहमीच्या पातळीच्या {floor_pct}% पेक्षा खाली राहिली, आणि घट नेहमीच्या मंद दिवसापेक्षा जास्त असली, तर छत्री आपल्या दुकानाच्या गमावलेल्या विक्रीच्या {share_pct}% रक्कम देते. हा हिशोब आपला नेहमीचा दिवस आणि परिसरातील घट यावरून ठरतो. दिवसाला जास्तीत जास्त {area_cap}. आपल्याला दावा करावा लागत नाही. | facts: `floor_pct`, `hours`, `share_pct`, `area_cap`; numbers come from the rules API, not from the string |
| `explain.c2.example` | A tea stall usually sells ₹4,380 on a Tuesday. One rainy Tuesday the area's sales fell 63%. Half of the lost sales is ₹1,379.70, which rounds to ₹1,380, so the stall was paid ₹1,380. | एक चाय की दुकान मंगलवार को आम तौर पर ₹4,380 बेचती है। एक बारिश वाले मंगलवार को इलाके की बिक्री 63% गिरी। खोई हुई बिक्री का आधा ₹1,379.70 है, जो ₹1,380 बनता है, इसलिए दुकान को ₹1,380 मिले। | एका चहाच्या दुकानाची मंगळवारी साधारण ₹4,380 विक्री होते. एका पावसाळी मंगळवारी परिसरातील विक्री 63% घटली. गमावलेल्या विक्रीची निम्मी रक्कम ₹1,379.70 आहे, जी ₹1,380 होते, म्हणून दुकानाला ₹1,380 मिळाले. | demo numbers (DEMO.md golden numbers, rules pilot-0.1); past tense on purpose |
| `explain.c3.title` | Hospital cash | अस्पताल में आय का नुकसान | रुग्णालयात असताना उत्पन्नाचे नुकसान | section c3; clause chip C3 |
| `explain.c3.body` | If your shop has no sales for a full day, Chhatri asks if you are okay. If you are in hospital, send one photo of the hospital slip. When the slip checks out, Chhatri pays {share_pct}% of your usual day, up to {personal_cap} a day, for up to {max_auto_days} days. A person looks at anything longer. | अगर आपकी दुकान में पूरे दिन बिक्री न हो, तो छतरी आपसे पूछती है कि सब ठीक है या नहीं। अगर आप अस्पताल में हैं, तो अस्पताल की पर्ची की एक फ़ोटो भेजें। पर्ची ठीक निकलने पर छतरी आपके आम दिन का {share_pct}% देती है, एक दिन में ज़्यादा से ज़्यादा {personal_cap}, और ज़्यादा से ज़्यादा {max_auto_days} दिन तक। इससे लंबे दावे को कोई व्यक्ति देखता है। | आपल्या दुकानात पूर्ण दिवस विक्री झाली नाही, तर छत्री आपल्याला सर्व ठीक आहे का ते विचारते. आपण रुग्णालयात असाल, तर रुग्णालयाच्या पर्चीचा एक फोटो पाठवा. पर्ची तपासणीत बरोबर निघाली, तर छत्री आपल्या नेहमीच्या दिवसाच्या {share_pct}% रक्कम देते, दिवसाला जास्तीत जास्त {personal_cap}, आणि जास्तीत जास्त {max_auto_days} दिवसांपर्यंत. त्यापेक्षा जास्त दिवसांचा दावा एक व्यक्ती तपासते. | facts: `share_pct`, `personal_cap`, `max_auto_days`; numbers come from the rules API, not from the string |
| `explain.c3.example` | A shop usually sells ₹4,300 on a Wednesday. The owner was in hospital and the shop had no sales that day. Half of ₹4,300 is ₹2,150, but the limit is ₹1,500 a day, so ₹1,500 was paid for that day. | एक दुकान बुधवार को आम तौर पर ₹4,300 बेचती है। मालिक अस्पताल में थे और उस दिन दुकान में कोई बिक्री नहीं हुई। ₹4,300 का आधा ₹2,150 है, पर एक दिन की सीमा ₹1,500 है, इसलिए उस दिन के ₹1,500 दिए गए। | एका दुकानाची बुधवारी साधारण ₹4,300 विक्री होते. मालक रुग्णालयात होते आणि त्या दिवशी दुकानात विक्री झाली नाही. ₹4,300 चे निम्मे ₹2,150 आहे, पण दिवसाची मर्यादा ₹1,500 आहे, म्हणून त्या दिवसाचे ₹1,500 दिले गेले. | demo numbers (DEMO.md golden numbers, rules pilot-0.1); past tense on purpose |
| `explain.c4.title` | How much Chhatri pays | छतरी कितना देती है | छत्री किती रक्कम देते | section c4; clause chip C4 |
| `explain.c4.body` | Chhatri pays {share_pct}% of the sales you lost. The most for one day is {area_cap} for rain and {personal_cap} for hospital cash. Hospital cash is paid without a review for up to {max_auto_days} days. All payouts together stop at {annual_limit} in any {window_days} days. | छतरी आपकी खोई हुई बिक्री का {share_pct}% देती है। एक दिन में ज़्यादा से ज़्यादा बारिश के लिए {area_cap} और अस्पताल के लिए {personal_cap}। अस्पताल का भुगतान बिना समीक्षा के ज़्यादा से ज़्यादा {max_auto_days} दिन तक होता है। किसी भी {window_days} दिनों में सारे भुगतान जोड़ने पर {annual_limit} से ज़्यादा नहीं होते। | छत्री आपल्या गमावलेल्या विक्रीच्या {share_pct}% रक्कम देते. एका दिवसासाठी जास्तीत जास्त पावसासाठी {area_cap} आणि रुग्णालयासाठी {personal_cap}. रुग्णालयाची रक्कम पुनरावलोकनाशिवाय जास्तीत जास्त {max_auto_days} दिवसांपर्यंत दिली जाते. कोणत्याही {window_days} दिवसांत सर्व रक्कम जोडल्यावर {annual_limit} पेक्षा जास्त होत नाही. | facts: `share_pct`, `area_cap`, `personal_cap`, `max_auto_days`, `annual_limit`, `window_days`; numbers come from the rules API, not from the string |
| `explain.c5.title` | When cover starts | कवर कब शुरू होता है | कवर केव्हा सुरू होते | section c5; clause chip C5 |
| `explain.c5.body` | A new cover starts {waiting_days} days after you ask. If an alert for your area is on, or was issued and starts within {lookahead_hours} hours, you cannot start cover right away. You can still buy cover for later. Cover bought after an alert was issued never pays for that alert. | नया कवर माँगने के {waiting_days} दिन बाद शुरू होता है। अगर आपके इलाके के लिए अलर्ट चालू है, या जारी हो चुका है और {lookahead_hours} घंटे में शुरू होगा, तो कवर तुरंत शुरू नहीं हो सकता। आगे के लिए कवर आप फिर भी ले सकते हैं। अलर्ट जारी होने के बाद लिया गया कवर उस अलर्ट के लिए कभी भुगतान नहीं करता। | नवीन कवर मागितल्यानंतर {waiting_days} दिवसांनी सुरू होते. आपल्या परिसरासाठी अलर्ट सुरू असेल, किंवा जाहीर झाला असेल आणि {lookahead_hours} तासांत सुरू होणार असेल, तर कवर लगेच सुरू होऊ शकत नाही. पुढील काळासाठी कवर आपण तरीही घेऊ शकता. अलर्ट जाहीर झाल्यानंतर घेतलेले कवर त्या अलर्टसाठी कधीही रक्कम देत नाही. | facts: `waiting_days`, `lookahead_hours`; numbers come from the rules API, not from the string; matches the BUILT COVER_BLOCKED meaning |
| `explain.c5.example` | Ramesh asks on Monday 18 August at 18:00. His cover starts on 25 August. | रमेश सोमवार 18 अगस्त को 18:00 बजे कवर माँगते हैं। उनका कवर 25 अगस्त से शुरू होता है। | रमेश सोमवारी 18 ऑगस्टला 18:00 वाजता कवर मागतात. त्यांचे कवर 25 ऑगस्टपासून सुरू होते. | demo dates: scenario buy_cover, merchant S-0907 |
| `explain.c6.title` | Premium and prepaid days | प्रीमियम और पहले से जमा दिन | प्रीमियम आणि आधी भरलेले दिवस | section c6; clause chip C6 |
| `explain.c6.body` | The first payment covers {first_days} days. After that, the evening settlement takes the next day's premium, with your standing consent. Cover works on the days whose premium was paid in advance. | पहला भुगतान {first_days} दिन के लिए होता है। उसके बाद शाम का सेटलमेंट आपकी स्थायी सहमति से अगले दिन का प्रीमियम काट लेता है। कवर उन्हीं दिनों काम करता है जिनका प्रीमियम पहले से जमा हो। | पहिले पेमेंट {first_days} दिवसांसाठी असते. त्यानंतर संध्याकाळचे सेटलमेंट आपल्या कायम संमतीने पुढील दिवसाचे प्रीमियम कापते. ज्या दिवसांचे प्रीमियम आधी भरलेले असते त्याच दिवसांना कवर लागू होते. | facts: `first_days`; numbers come from the rules API, not from the string |
| `explain.c6.example` | In the demo, Zone 3 costs ₹14.16 a day, so 30 days is ₹424.80. The real price is not decided yet. | डेमो में ज़ोन 3 का प्रीमियम रोज़ ₹14.16 है, इसलिए 30 दिन के ₹424.80 होते हैं। असली कीमत अभी तय नहीं हुई है। | डेमोमध्ये झोन 3 चे प्रीमियम रोज ₹14.16 आहे, म्हणून 30 दिवसांचे ₹424.80 होतात. खरी किंमत अजून ठरलेली नाही. | demo numbers: Z3 premium from the backtest; the real price is a pricing decision still open |
| `explain.c7.title` | When a claim is not paid | दावे का भुगतान कब नहीं होता | दाव्याची रक्कम केव्हा दिली जात नाही | section c7; clause chips C7 and C8 |
| `explain.c7.body` | A claim is not paid when a check that must pass does not pass. The list below gives the reasons Chhatri gives. Anything the system is unsure about goes to a person. That is not a refusal. | जब कोई ज़रूरी जाँच पास नहीं होती, तब दावे का भुगतान नहीं होता। नीचे वे कारण हैं जो छतरी बताती है। जिस बात पर सिस्टम को यकीन न हो, उसे कोई व्यक्ति देखता है। यह इनकार नहीं है। | एखादी आवश्यक तपासणी यशस्वी झाली नाही, तर दाव्याची रक्कम दिली जात नाही. खाली छत्री जी कारणे सांगते ती आहेत. ज्या गोष्टीबद्दल सिस्टमला खात्री नसते ती एक व्यक्ती तपासते. हा नकार नाही. | the list under it is the BUILT REASON_ lines (Appendix A); no exclusion is listed that the engine does not check |
| `explain.c10.title` | Your loan instalment | आपकी लोन किस्त | आपला कर्जाचा हप्ता | section c10; clause chip C10 |
| `explain.c10.body` | After a payout, Chhatri asks your lender to pause your next instalment. The lender decides, not Chhatri. | भुगतान के बाद छतरी आपके लेंडर से आपकी अगली किस्त रोकने को कहती है। फ़ैसला लेंडर का होता है, छतरी का नहीं। | रक्कम दिल्यानंतर छत्री आपल्या लेंडरला आपला पुढचा हप्ता थांबवण्यास सांगते. निर्णय लेंडरचा असतो, छत्रीचा नाही. | ADR 0006 wording: the holiday is the lender's decision |
| `explain.example.title` | Example | उदाहरण | उदाहरण | - |
| `explain.example.sim` | Example from a simulated replay | SIMULATED रीप्ले का उदाहरण | SIMULATED रीप्लेचे उदाहरण | label under every worked example that uses demo numbers |
| `explain.price.covered` | Your price: {per_day} a day. | आपकी कीमत: {per_day} प्रति दिन। | आपली किंमत: {per_day} प्रतिदिन. | facts: `per_day`; a covered merchant sees the price of their own cover |
| `explain.price.uncovered` | You see your price when you tap Get cover. | कवर लें पर टैप करने पर आपको अपनी कीमत दिखेगी। | कवर घ्या वर टॅप केल्यावर आपल्याला आपली किंमत दिसेल. | viewing the explainer never creates a payment link |
| `explain.price.prototype` | Prototype price. The real price is not decided yet. | प्रोटोटाइप की कीमत। असली कीमत अभी तय नहीं हुई है। | प्रोटोटाइपची किंमत. खरी किंमत अजून ठरलेली नाही. | shown beside every price while prices come from simulated sales |
| `explain.no_forms` | Rain claims need no forms. Hospital cash needs one photo of the slip. | बारिश के दावे में कोई फ़ॉर्म नहीं। अस्पताल के दावे में पर्ची की एक फ़ोटो चाहिए। | पावसाच्या दाव्यासाठी फॉर्म नको. रुग्णालयाच्या दाव्यासाठी पर्चीचा एक फोटो लागतो. | - |
| `explain.rules_note` | These are the demo rules ({rules_version}). They are illustrative. A partner insurer would set the real terms. | ये डेमो नियम हैं ({rules_version})। ये सिर्फ़ उदाहरण के लिए हैं। असली शर्तें साझेदार बीमा कंपनी तय करेगी। | हे डेमो नियम आहेत ({rules_version}). ते फक्त उदाहरणासाठी आहेत. खरे नियम भागीदार विमा कंपनी ठरवेल. | facts: `rules_version`; rules.yaml header says: illustrative, to be set with the insurance partner |
| `explain.btn.got_it` | Got it | समझ गया | समजले | - |
| `explain.terms_hint` | Tap an underlined word to see what it means. | किसी रेखांकित शब्द पर टैप करें, उसका मतलब दिखेगा। | अधोरेखित शब्दावर टॅप करा, त्याचा अर्थ दिसेल. | H20 jargon lens |

### 2.4 Get cover

The first button is Check price and start date, so opening the screen never creates a payment link. The first payment is 30 days of premium through a Paytm link. The pay button reads Pay with Paytm while the Paytm component is LIVE and Simulate payment while it is SIMULATED. Cover starts after the waiting period, whatever the quote outcome. A BLOCKED quote (an alert is valid now, or is issued and starts within 72 hours) still offers the link, and the built COVER_BLOCKED and COVER_LINK messages show in the WhatsApp thread. The word Approved is never used for a quote. The consent boxes start unticked and arrive with N6 (wave 3); before that the screen shows buy.consent.notice.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `buy.title` | Get cover | कवर लें | कवर घ्या | heading of the buy screen |
| `buy.intro` | New cover always starts {waiting_days} days after you ask. | नया कवर हमेशा माँगने के {waiting_days} दिन बाद शुरू होता है। | नवीन कवर नेहमी मागितल्यानंतर {waiting_days} दिवसांनी सुरू होते. | facts: `waiting_days`; days from the rules API |
| `buy.check` | Check price and start date | कीमत और शुरू होने की तारीख़ देखें | किंमत आणि सुरू होण्याची तारीख पहा | the first button: a quote is asked only when this is tapped, so opening the screen never creates a payment link |
| `buy.outcome.ok` | Cover starts on {date} | कवर {date} से शुरू होगा | कवर {date} पासून सुरू होईल | facts: `date`; quote outcome OK; the word Approved is never used for a quote |
| `buy.outcome.blocked` | Blocked for now. Cover starts on {date}. | अभी रुका है। कवर {date} से शुरू होगा। | सध्या थांबले आहे. कवर {date} पासून सुरू होईल. | facts: `date`; quote outcome BLOCKED; the link is still offered; the date is the request date plus the waiting period |
| `buy.row.starts` | Cover starts | कवर शुरू | कवर सुरू | - |
| `buy.row.per_day` | Premium a day | रोज़ का प्रीमियम | रोजचे प्रीमियम | - |
| `buy.row.first_payment` | First payment ({first_days} days) | पहला भुगतान ({first_days} दिन) | पहिले पेमेंट ({first_days} दिवस) | facts: `first_days`; numbers from the cover quote |
| `buy.blocked_note` | Cover bought after an alert was issued does not pay for that alert. You can still buy cover for later. | अलर्ट जारी होने के बाद लिया गया कवर उस अलर्ट के लिए भुगतान नहीं करता। आप आगे के लिए कवर फिर भी ले सकते हैं। | अलर्ट जाहीर झाल्यानंतर घेतलेले कवर त्या अलर्टसाठी रक्कम देत नाही. पुढील काळासाठी कवर आपण तरीही घेऊ शकता. | added under a BLOCKED result |
| `buy.consent.notice` | Chhatri uses your sales data to decide claims and set your premium. | छतरी आपकी बिक्री का डेटा दावे तय करने और आपका प्रीमियम बनाने में इस्तेमाल करती है। | छत्री आपला विक्रीचा डेटा दावे ठरवण्यासाठी आणि आपले प्रीमियम ठरवण्यासाठी वापरते. | the one plain line shown on the buy screen until N6 (wave 3) brings the notice and the boxes of section 14.1 |
| `buy.pay` | Pay with Paytm | Paytm से भुगतान करें | Paytm ने पेमेंट करा | shown only when the Paytm component is LIVE; opens the link |
| `buy.simulate` | Simulate payment | भुगतान का सिमुलेशन करें | पेमेंटचे सिम्युलेशन करा | shown instead of buy.pay while the Paytm component is SIMULATED; no URL is opened |
| `buy.pending` | Waiting for your payment. This page updates when it arrives. | आपके भुगतान का इंतज़ार है। भुगतान आते ही यह पेज बदल जाएगा। | आपल्या पेमेंटची प्रतीक्षा आहे. पेमेंट येताच हे पान बदलेल. | - |
| `buy.link.simulated` | SIMULATED payment link. No real money moves. | SIMULATED भुगतान लिंक। असली पैसा नहीं जाता। | SIMULATED पेमेंट लिंक. खरे पैसे जात नाहीत. | shown whenever the payment component is SIMULATED (always in the demo) |
| `buy.paid` | Payment received. | आपका भुगतान आ गया। | पेमेंट मिळाले. | followed by the BUILT status line (COVER_STATUS_STARTS or COVER_STATUS_ACTIVE) |

### 2.5 Catalogue lines for cover (wave 1)

Two new catalogue lines of the cover purchase spec ([fs-07](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md) section 8.3). The five built cover lines (COVER_BLOCKED, COVER_LINK, COVER_LINK_UNAVAILABLE, the three COVER_STATUS lines) are in Appendix A.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `COVER_STATUS_NONE` | No cover yet | अभी कवर नहीं है | अजून कवर नाही | the cover endpoint's status text for a merchant with no cover; the chat keeps following BUY_COVER for that merchant |
| `COVER_BLOCKED_NOW` | New cover starts after the waiting period — from {starts_on_en}. It won't apply to the alert that is in force now. | नया कवर वेटिंग पीरियड के बाद शुरू होता है — {starts_on_hi} से। यह अभी चल रहे अलर्ट पर लागू नहीं होगा। | नवीन कवर वेटिंग पीरियडनंतर सुरू होते — {starts_on_mr} पासून. सध्या लागू असलेल्या अलर्टसाठी ते लागू होणार नाही. | facts: `starts_on`; used when the blocking alert is already in force; COVER_BLOCKED stays for an alert that starts later |

## 3. Claim tracker (H1, wave 1)

Steps are Detected, Checked, Decided, Paid and, for a merchant with a loan, Instalment holiday. A claim can stop at Checked or Decided: REFERRED waits for a person, DECLINED stops, and a DISPUTE is its own item. A step appears only after it has happened, and nothing says Paid before the payout record exists.

### 3.1 Labels

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `tracker.title` | Your claims | आपके दावे | आपले दावे | - |
| `tracker.kind.area` | Rain and lost sales | बारिश से बिक्री का नुकसान | पावसामुळे विक्रीचे नुकसान | - |
| `tracker.kind.personal` | Hospital cash | अस्पताल में आय का नुकसान | रुग्णालयात असताना उत्पन्नाचे नुकसान | - |
| `tracker.kind.dispute` | Question about a payout | भुगतान पर सवाल | रकमेबद्दल प्रश्न | - |
| `tracker.step.detected` | Detected | पता चला | आढळले | - |
| `tracker.step.checked` | Checked | जाँच हुई | तपासले | - |
| `tracker.step.decided` | Decided | फ़ैसला हुआ | निर्णय झाला | - |
| `tracker.step.paid` | Paid | भुगतान हुआ | जमा झाले | - |
| `tracker.step.edi` | Instalment holiday (EDI) | किस्त की छुट्टी (EDI) | हप्त्याची सुट्टी (EDI) | shown only when the merchant has a loan; EDI opens the jargon lens (edi_holiday) |
| `tracker.state.done` | Done | हो गया | झाले | - |
| `tracker.state.now` | In progress | चल रहा है | सुरू आहे | - |
| `tracker.state.waiting` | Waiting | इंतज़ार | प्रतीक्षा | - |
| `tracker.state.na` | Not needed | ज़रूरी नहीं | गरज नाही | - |
| `tracker.state.stopped` | Stopped here | यहीं रुक गया | येथे थांबले | - |
| `tracker.clock.left` | {hours} hours left | {hours} घंटे बाकी | {hours} तास बाकी | facts: `hours`; hours_left from the case clock (due_by minus now) |
| `tracker.clock.due` | Reply due by {time} | जवाब का समय: {time} तक | उत्तराची वेळ: {time} पर्यंत | facts: `time`; case.due_by |
| `tracker.clock.overdue` | Past the time limit | समय सीमा पार | वेळमर्यादा उलटली | due_by is in the past and the case is still OPEN |
| `tracker.btn.receipt` | See receipt | रसीद देखें | पावती पहा | - |
| `tracker.btn.wrong` | This is wrong | यह ग़लत है | हे चुकीचे आहे | opens a DISPUTE case on a paid claim; the officer confirms the payout or rejects the question, and the amount never changes |
| `tracker.btn.why` | Why this amount? | इतने पैसे क्यों? | इतकी रक्कम का? | opens the Why screen of a paid or declined claim |
| `why.title` | Why did I get this amount? | मुझे इतने ही पैसे क्यों मिले? | मला इतकीच रक्कम का मिळाली? | heading of the Why screen; the Hindi line is the demo voice chip |
| `why.numbers` | Your numbers | आपके आँकड़े | आपले आकडे | rows: usual day, area drop or days, share, limit, result; each row carries a source chip |
| `why.no_amount` | No amount yet. A person is checking your claim. | अभी कोई रकम नहीं है। कोई व्यक्ति आपका दावा जाँच रहा है। | अजून कोणतीही रक्कम नाही. एक व्यक्ती आपला दावा तपासत आहे. | a REFERRED decision has no amount; the failing check follows in plain words |
| `tracker.next.after_detected` | Next: Chhatri checks your cover and the numbers. | आगे: छतरी आपका कवर और आँकड़े जाँचती है। | पुढे: छत्री आपले कवर आणि आकडे तपासते. | - |
| `tracker.next.after_checked` | Next: the decision. | आगे: फ़ैसला। | पुढे: निर्णय. | - |
| `tracker.next.referred` | Next: a person decides. You will hear back within {sla_hours} hours. | आगे: कोई व्यक्ति फ़ैसला करेगा। {sla_hours} घंटे में जवाब मिलेगा। | पुढे: एक व्यक्ती निर्णय घेईल. {sla_hours} तासांत उत्तर मिळेल. | facts: `sla_hours`; REFERRED decision with an open case; sla_hours from rules.yaml dispute_sla_hours |
| `tracker.next.after_decided` | Next: the money is credited with the settlement. | आगे: पैसे सेटलमेंट के साथ जमा होते हैं। | पुढे: पैसे सेटलमेंटसोबत जमा होतात. | only after an APPROVED decision exists |
| `tracker.next.after_paid` | Next: if you have a loan, your lender decides about the instalment. | आगे: अगर आपका लोन है, तो किस्त पर लेंडर फ़ैसला करता है। | पुढे: आपले कर्ज असल्यास हप्त्याबद्दल लेंडर निर्णय घेतो. | - |
| `tracker.next.done` | All steps are done. Your receipt is ready. | सभी कदम पूरे हुए। आपकी रसीद तैयार है। | सर्व टप्पे पूर्ण झाले. आपली पावती तयार आहे. | - |
| `tracker.next.declined` | You can ask for the reason or talk to our team. | आप कारण पूछ सकते हैं या हमारी टीम से बात कर सकते हैं। | आपण कारण विचारू शकता किंवा आमच्या टीमशी बोलू शकता. | - |
| `claim.status.approved_pending` | Approved. Credit is on its way. | मंज़ूर। पैसा आने वाला है। | मंजूर. रक्कम येत आहे. | APPROVED and the payout is not credited yet |
| `claim.status.paid` | Paid | भुगतान हुआ | रक्कम दिली गेली | APPROVED and credited |
| `claim.status.referred` | With a claims officer | हमारी टीम देख रही है | आमची टीम पाहत आहे | REFERRED; the Decided step shows this line, and the case chip and the clock sit beside it |
| `claim.status.declined` | Not paid | भुगतान नहीं हुआ | रक्कम दिली गेली नाही | DECLINED |
| `claim.status.waiting_slip` | Waiting for your slip | आपकी पर्ची का इंतज़ार | आपल्या पर्चीची प्रतीक्षा | personal claim waiting for the slip |
| `claim.status.question_open` | Question open | सवाल खुला है | प्रश्न खुला आहे | DISPUTE case OPEN; the mini-app spec calls it Dispute open |
| `claim.status.question_closed` | Question closed. Amount unchanged. | सवाल बंद। रकम वही रही। | प्रश्न बंद. रक्कम तीच राहिली. | DISPUTE case CLOSED; the amount never changes |

### 3.2 Reasons

One line of reason per step. Lines for a failed HARD check use the built REASON_ text (Appendix A); the lines here cover everything else.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `TRACK_DETECTED_AREA` | Your area's sales fell {drop}% during the alert. | अलर्ट के दौरान आपके इलाके की बिक्री {drop}% गिरी। | अलर्ट दरम्यान आपल्या परिसरातील विक्री {drop}% घटली. | facts: `drop`; area claim; drop is an integer percentage |
| `TRACK_DETECTED_PERSONAL` | Your shop had no sales on {dates_en}. | {dates_hi} को आपकी दुकान में कोई बिक्री नहीं हुई। | {dates_mr} रोजी आपल्या दुकानात विक्री झाली नाही. | facts: `dates`; personal claim; silent dates |
| `TRACK_CHECKED_OK` | All {passed} checks passed. | सभी {passed} जाँचें पास हुईं। | सर्व {passed} तपासण्या यशस्वी झाल्या. | facts: `passed`; every check of the claim passed; passed = number of checks that ran |
| `TRACK_CHECKED_FAILED` | A required check did not pass. | एक ज़रूरी जाँच पास नहीं हुई। | एक आवश्यक तपासणी यशस्वी झाली नाही. | a HARD check failed; the next line is the BUILT REASON_ text for that check |
| `TRACK_REFERRED_UNREADABLE` | The slip could not be read clearly. | पर्ची साफ़ नहीं पढ़ी जा सकी। | पर्ची स्पष्ट वाचता आली नाही. | REFERRED because SLIP_READABLE is UNSURE or FAIL (same meaning as BUILT SLIP_TO_HUMAN_UNREADABLE) |
| `TRACK_REFERRED_NAME` | The name on the slip does not match your KYC. | पर्ची का नाम आपके KYC से मेल नहीं खाता। | पर्चीवरील नाव आपल्या KYC शी जुळत नाही. | REFERRED because NAME_MATCHES_KYC is FAIL or UNSURE (same meaning as BUILT SLIP_TO_HUMAN) |
| `TRACK_REFERRED_DATES` | The slip dates do not match the days your shop was closed. | पर्ची की तारीख़ें दुकान बंद रहने के दिनों से मेल नहीं खातीं। | पर्चीवरील तारखा दुकान बंद असलेल्या दिवसांशी जुळत नाहीत. | REFERRED because DATES_MATCH is FAIL or UNSURE (same meaning as BUILT SLIP_TO_HUMAN_DATES) |
| `TRACK_REFERRED_DAYS` | This claim covers more days than are paid automatically. | यह दावा अपने-आप भुगतान के दिनों से ज़्यादा दिनों का है। | हा दावा आपोआप भरपाई देण्याच्या दिवसांपेक्षा जास्त दिवसांचा आहे. | REFERRED because WITHIN_AUTO_LIMIT failed (same meaning as BUILT SLIP_TO_HUMAN_DAYS) |
| `TRACK_DECIDED_AUTO` | Approved {amount} | मंज़ूर {amount} | मंजूर {amount} | facts: `amount`; decision APPROVED, decided_by is not an officer; the mini-app spec shows Approved with the amount |
| `TRACK_DECIDED_OFFICER` | Approved by a claims officer | क्लेम अधिकारी ने मंज़ूर किया | क्लेम अधिकाऱ्याने मंजूर केले | English line is the BUILT badge PAYOUT_CARD_BADGE_OFFICER; decided_by starts with officer:; the amount is shown beside the line, not inside it |
| `TRACK_DECIDED_DECLINED` | Not paid. {reason_en} | भुगतान नहीं हुआ। {reason_hi} | रक्कम दिली गेली नाही. {reason_mr} | facts: `reason`; DECLINED; reason is the BUILT REASON_ text of the first failing HARD check |
| `TRACK_PAID_PENDING` | {amount} is on its way, with the next settlement. | {amount} अगले सेटलमेंट के साथ आ रहे हैं। | {amount} पुढील सेटलमेंटसोबत येत आहे. | facts: `amount`; payout exists and is not CREDITED yet; never shown before the payout record exists; the English detail matches the BUILT card detail with the next settlement |
| `TRACK_PAID_ETA` | Credit in about {minutes} minutes (demo clock). | लगभग {minutes} मिनट में जमा होगा (डेमो घड़ी)। | सुमारे {minutes} मिनिटांत जमा होईल (डेमो घड्याळ). | facts: `minutes`; Paid step while the credit is pending; minutes come from the payout rail delay in the rules |
| `TRACK_PAID_FAILED` | The payout did not go through. Please talk to our team. | भुगतान नहीं हो पाया। कृपया हमारी टीम से बात करें। | रक्कम जमा होऊ शकली नाही. कृपया आमच्या टीमशी बोला. | PayoutStatus.FAILED |
| `TRACK_EDI_REQUESTED` | We asked your lender. The lender decides. | हमने आपके लेंडर से कहा है। फ़ैसला लेंडर का होता है। | आम्ही आपल्या लेंडरला सांगितले आहे. निर्णय लेंडरचा असतो. | EDI step while the request is open |
| `TRACK_EDI_REFUSED` | Not available. Your instalment is due as usual. | उपलब्ध नहीं। आपकी किस्त हमेशा की तरह देय है। | उपलब्ध नाही. आपला हप्ता नेहमीप्रमाणे देय आहे. | EDI step when the lender says no; wording of the mini-app spec; no reason code is shown |
| `TRACK_EDI_REFUSED_WHY` | The lender said no: {reason_en} | लेंडर ने मना किया: {reason_hi} | लेंडरने नकार दिला: {reason_mr} | facts: `reason`; shown under TRACK_EDI_REFUSED only if open question 9 settles on showing the lender's reason in plain words; reason is a HOLIDAY_REASON_ line |
| `TRACK_EDI_NO_RESPONSE` | We could not reach your lender. Your instalment is due as usual. | हम आपके लेंडर तक नहीं पहुँच सके। आपकी किस्त हमेशा की तरह देय है। | आम्ही आपल्या लेंडरपर्यंत पोहोचू शकलो नाही. आपला हप्ता नेहमीप्रमाणे देय आहे. | EDI step when the lender does not answer in time; no retry |
| `TRACK_EDI_NONE` | No loan on file | कोई लोन दर्ज नहीं | कोणतेही कर्ज नोंदलेले नाही | merchant has no loan; the step is skipped |
| `TRACK_DISPUTE_OPEN` | Question open · case {case_id}. You will hear back within {sla_hours} hours. | सवाल खुला है · केस {case_id}। {sla_hours} घंटे में जवाब मिलेगा। | प्रश्न खुला आहे · केस {case_id}. {sla_hours} तासांत उत्तर मिळेल. | facts: `case_id`, `sla_hours`; DISPUTE case with status OPEN |
| `TRACK_DISPUTE_CLOSED` | Our team checked it. The amount paid stays {amount}. | हमारी टीम ने जाँच की। दिया गया भुगतान {amount} ही रहेगा। | आमच्या टीमने तपासले. दिलेली रक्कम {amount} तीच राहील. | facts: `amount`; DISPUTE case CLOSED; a dispute never changes the amount; the BUILT REASON_OFFICER_DISPUTE text follows |

### 3.3 Chat messages for the instalment holiday (X4, wave 1)

The built INSTALMENT_PAUSED line says the instalment is paused and does not say who decided. The holiday is the lender's decision: Chhatri requests it after a payout, under a pre-agreed rule, and the lender grants or refuses. These keys are the ones of the instalment holiday spec ([fs-03](../02-product/feature-specs/fs-03-edi-holiday.md) section 8). They replace INSTALMENT_PAUSED, INSTALMENT_PAUSED_TODAY and INSTALMENT_PAUSED_ON in one commit with the tests and DEMO.md (conversation design, section 10.1). The built lines stay in Appendix A until then. After a refusal, or no answer, the next step is the button nba.btn.ask_lender (section 8.1).

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `HOLIDAY_GRANTED` | Your lender has paused tomorrow's {instalment} instalment. It moves to the end of your loan with no penalty. | आपके लेंडर ने कल की {instalment} की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं। | आपल्या लेंडरने उद्याचा {instalment} चा हप्ता थांबवला आहे. तो आपल्या कर्जाच्या शेवटी जातो, कोणताही दंड नाही. | facts: `instalment`; lender answered yes and the instalment is due tomorrow; replaces INSTALMENT_PAUSED; sent only after the lender's answer |
| `HOLIDAY_GRANTED_TODAY` | Your lender has paused today's {instalment} instalment. It moves to the end of your loan with no penalty. | आपके लेंडर ने आज की {instalment} की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं। | आपल्या लेंडरने आजचा {instalment} चा हप्ता थांबवला आहे. तो आपल्या कर्जाच्या शेवटी जातो, कोणताही दंड नाही. | facts: `instalment`; lender answered yes and the instalment is due today; replaces INSTALMENT_PAUSED_TODAY |
| `HOLIDAY_GRANTED_ON` | Your lender has paused the {instalment} instalment due on {date_en}. It moves to the end of your loan with no penalty. | आपके लेंडर ने {date_hi} की {instalment} की किस्त रोक दी है। वह आपके लोन के अंत में चली जाती है, कोई जुर्माना नहीं। | आपल्या लेंडरने {date_mr} रोजी देय असलेला {instalment} चा हप्ता थांबवला आहे. तो आपल्या कर्जाच्या शेवटी जातो, कोणताही दंड नाही. | facts: `instalment`, `date`; lender answered yes and the instalment is due on another day; replaces INSTALMENT_PAUSED_ON |
| `HOLIDAY_REFUSED` | Your lender could not pause the {instalment} instalment due {when_en}: {reason_en}. It is due as usual. Your payout is not affected. | आपका लेंडर {when_hi} की {instalment} की किस्त नहीं रोक सका: {reason_hi}। वह हमेशा की तरह देय है। आपके भुगतान पर इसका कोई असर नहीं पड़ता। | आपला लेंडर {when_mr} देय असलेला {instalment} चा हप्ता थांबवू शकला नाही: {reason_mr}. तो नेहमीप्रमाणे देय आहे. आपल्या रकमेवर याचा परिणाम होत नाही. | facts: `instalment`, `when`, `reason`; lender answered no with a reason; when_en is tomorrow, today or on 27 August; when_hi is कल, आज or 27 अगस्त; when_mr is उद्या, आज or 27 ऑगस्टला; the EDI holiday spec sketches {when} as tomorrow's, today's or the one due on a date, which does not read right for a date, so this row says due {when} (section 1.8) |
| `HOLIDAY_NO_RESPONSE` | We could not reach your lender about the {instalment} instalment due {when_en}, so it is due as usual. Your payout is not affected. | हम {when_hi} की {instalment} की किस्त के बारे में आपके लेंडर तक नहीं पहुँच सके, इसलिए वह हमेशा की तरह देय है। आपके भुगतान पर इसका कोई असर नहीं पड़ता। | {when_mr} देय असलेल्या {instalment} च्या हप्त्याबद्दल आम्ही आपल्या लेंडरपर्यंत पोहोचू शकलो नाही, म्हणून तो नेहमीप्रमाणे देय आहे. आपल्या रकमेवर याचा परिणाम होत नाही. | facts: `instalment`, `when`; no answer in time; one attempt and no retry, so a late grant can never contradict this message |
| `HOLIDAY_REASON_FLAG_OFF` | this loan is not part of the holiday scheme | यह लोन किस्त की छुट्टी की योजना में शामिल नहीं है | हे कर्ज हप्त्याच्या सुट्टीच्या योजनेत नाही | reason code FLAG_OFF; a fragment that follows a colon in HOLIDAY_REFUSED |
| `HOLIDAY_REASON_NOT_ACTIVE` | the loan is not active | लोन चालू नहीं है | कर्ज सुरू नाही | reason code NOT_ACTIVE |
| `HOLIDAY_REASON_IN_ARREARS` | the loan has an amount overdue | लोन की कुछ रकम बकाया है | कर्जाची काही रक्कम थकीत आहे | reason code IN_ARREARS |
| `HOLIDAY_REASON_NO_ALLOWANCE` | your holiday allowance is used up | आपकी किस्त की छुट्टियों की सीमा पूरी हो चुकी है | आपल्या हप्त्याच्या सुट्ट्यांची मर्यादा संपली आहे | reason code NO_ALLOWANCE |

## 4. Trust receipt (H2, H3, wave 1)

The receipt is for one decision. It exists as a receipt only when the payout is CREDITED; before that the same screen reads as a decision record. It carries the formula (the built EXPLAIN text), where each number came from (section 5), the checks (section 6.1), what would have changed the result (section 6.2), the rules version, the decision time and the first characters of the audit entry. `GET /api/decisions/{decision_id}/receipt` (PLANNED) returns it.

### 4.1 Rows and buttons

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `receipt.title` | Your payout receipt | आपके भुगतान की रसीद | आपल्या रकमेची पावती | only when the payout is CREDITED |
| `receipt.title.record` | Your decision record | आपके फ़ैसले का रिकॉर्ड | आपल्या निर्णयाची नोंद | for REFERRED, DECLINED or not yet credited decisions: no receipt before a payout exists |
| `receipt.row.decision` | Decision | फ़ैसला | निर्णय | value: the decision id and its outcome |
| `receipt.row.rules` | Rules version | नियमों का संस्करण | नियमांची आवृत्ती | value: rules_version, for example pilot-0.1 |
| `receipt.row.decided_at` | Decided | फ़ैसले का समय | निर्णयाची वेळ | - |
| `receipt.row.decided_by` | Decided by | फ़ैसला किसने किया | निर्णय कोणी घेतला | - |
| `receipt.by.engine` | An automatic rules check (code, not AI) | नियमों की अपने-आप जाँच (कोड, AI नहीं) | नियमांची आपोआप तपासणी (कोड, AI नाही) | decided_by is not an officer |
| `receipt.by.officer` | A claims officer | क्लेम अधिकारी | क्लेम अधिकारी | decided_by starts with officer: |
| `receipt.row.formula` | How it was worked out | हिसाब कैसे बना | हिशोब कसा झाला | value: the BUILT formula text (EXPLAIN_AREA_FORMULA or EXPLAIN_PERSONAL frame) |
| `receipt.row.sources` | Where each number came from | हर आँकड़ा कहाँ से आया | प्रत्येक आकडा कुठून आला | value: source badges (section 5) |
| `receipt.row.checks` | Checks | जाँचें | तपासण्या | value: one line per check (section 6.1) |
| `receipt.row.paid_at` | Credited | जमा हुआ | जमा झाले | only when the payout is CREDITED |
| `receipt.row.pending` | Credit pending | जमा होना बाकी | जमा होणे बाकी | payout exists and is not credited |
| `receipt.row.audit` | Audit entry (first {n} characters) | ऑडिट एंट्री (पहले {n} अक्षर) | ऑडिट नोंद (पहिली {n} अक्षरे) | facts: `n`; n is 12 in the PRD (H3) |
| `receipt.row.what_changes` | What would have changed this | क्या बदलने पर नतीजा बदलता | काय बदलले असते तर निकाल बदलला असता | value: counterfactual lines (section 6); engine-written, never by a language model |
| `receipt.row.disagree` | If you disagree | अगर आप सहमत नहीं हैं | आपण सहमत नसल्यास | value: the grievance ladder (section 13) |
| `receipt.btn.print` | Print or save as PDF | प्रिंट करें या PDF बनाएँ | प्रिंट करा किंवा PDF बनवा | uses the browser print dialog; there is no PDF library and no server work |
| `receipt.row.payout` | Payout | भुगतान | रक्कम | value: status, credit time, reference and the SIMULATED token for the payout rail |
| `receipt.row.lender` | Lender's answer | लेंडर का जवाब | लेंडरचे उत्तर | value: the HOLIDAY_ line the lender's answer produced, and the SIMULATED token; hidden when the merchant has no loan |
| `receipt.row.clauses` | Policy clauses used | इस्तेमाल हुए पॉलिसी खंड | वापरलेली पॉलिसी कलमे | value: clause chips (section 5.3) |
| `receipt.check_log` | Check the log | लॉग जाँचें | लॉग तपासा | calls the audit verify route; disabled offline |
| `receipt.log.ok` | Log unbroken, {entries} entries | लॉग सही है, {entries} एंट्री | लॉग अखंड आहे, {entries} नोंदी | facts: `entries`; result of the verify route when the chain is valid |
| `receipt.log.broken` | The log is broken at entry {seq}. | लॉग एंट्री {seq} पर टूटा हुआ है। | लॉग नोंद {seq} वर तुटलेला आहे. | facts: `seq`; a broken chain is never hidden |
| `receipt.print.header` | Chhatri · decision receipt · prototype · SIMULATED data | छतरी · फ़ैसले की रसीद · प्रोटोटाइप · SIMULATED डेटा | छत्री · निर्णयाची पावती · प्रोटोटाइप · SIMULATED डेटा | header of the printed page; the tab bar and the next-action bar are hidden in print |
| `receipt.simulated` | SIMULATED receipt. The data and the payout are not real. | SIMULATED रसीद। डेटा और भुगतान असली नहीं हैं। | SIMULATED पावती. डेटा आणि रक्कम खरी नाही. | printed on the page and in the PDF while any source is SIMULATED (always in the demo) |
| `receipt.footer` | This receipt explains one decision. It is not a policy document. | यह रसीद एक फ़ैसले को समझाती है। यह पॉलिसी का दस्तावेज़ नहीं है। | ही पावती एका निर्णयाचे स्पष्टीकरण देते. हा पॉलिसीचा दस्तऐवज नाही. | - |

### 4.2 Payout card badges

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `badge.card.claim_not_needed` | No claim needed | दावा करने की ज़रूरत नहीं | दावा करण्याची गरज नाही | BUILT; English is the BUILT PAYOUT_CARD_BADGE (area payout card); the catalogue has no Hindi line, so Hindi and Marathi are proposed |
| `badge.card.one_photo` | One photo, no forms | एक फ़ोटो, कोई फ़ॉर्म नहीं | एक फोटो, फॉर्म नाही | BUILT; English is the BUILT PAYOUT_CARD_BADGE_PERSONAL (hospital-cash payout card); Hindi and Marathi are proposed |
| `badge.card.officer` | Approved by a claims officer | क्लेम अधिकारी ने मंज़ूर किया | क्लेम अधिकाऱ्याने मंजूर केले | BUILT; English is the BUILT PAYOUT_CARD_BADGE_OFFICER (payout card after an officer decision); Hindi and Marathi are proposed |

## 5. Verified-by badges (H13, wave 1; modes with X6 and H26, wave 2)

Every rule, number and clause shown to a merchant or an officer carries a source chip: label, time of the record, origin. The label comes from a fixed catalogue, one per source kind (13 kinds, [fs-09](../02-product/feature-specs/fs-09-policy-engine-and-audit.md) section 8.3). An alert's own `source` text follows its label and is data, not copy. A chip never says that an outside body verified the value; the feature is called verified-by, the wording is Source.

### 5.1 Source labels

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `src.RULES` | Chhatri rules {rules_version} | छतरी के नियम {rules_version} | छत्रीचे नियम {rules_version} | facts: `rules_version`; kind RULES; ref is a rules.yaml key; origin CONFIG |
| `src.CLAUSE` | Policy clause {clause} | पॉलिसी का खंड {clause} | पॉलिसीचे कलम {clause} | facts: `clause`; kind CLAUSE; clause is C1 to C12 or a sub-clause such as C4.2; origin CONFIG |
| `src.ALERT` | Weather alert {alert_id} | मौसम अलर्ट {alert_id} | हवामान अलर्ट {alert_id} | facts: `alert_id`; kind ALERT; the alert's own source text follows the label and is data, not copy; origin SIMULATED today |
| `src.SALES_INDEX` | Area sales index | इलाके की बिक्री का हिसाब | परिसरातील विक्रीचा हिशोब | kind SALES_INDEX; origin SIMULATED today |
| `src.FORECAST` | Your usual day, worked out from your past sales | आपका आम दिन, आपकी पिछली बिक्री से निकाला गया | आपला नेहमीचा दिवस, आपल्या मागील विक्रीवरून काढलेला | kind FORECAST (the published expected day, rounded to ₹10); origin SIMULATED today |
| `src.ZONE_BOUND` | Usual range for your area | आपके इलाके का आम दायरा | आपल्या परिसराची नेहमीची श्रेणी | kind ZONE_BOUND (the zone's lower bound); origin CONFIG; the number itself is not copy |
| `src.COVER` | Your cover record | आपके कवर का रिकॉर्ड | आपल्या कवरची नोंद | kind COVER; origin SIMULATED today |
| `src.PREMIUM` | Your premium payment | आपका प्रीमियम भुगतान | आपले प्रीमियम पेमेंट | kind PREMIUM; LIVE only when the payment source is a Paytm adapter, else SIMULATED |
| `src.KYC` | Name on your Paytm account (KYC) | आपके Paytm खाते का नाम (KYC) | आपल्या Paytm खात्यावरील नाव (KYC) | kind KYC; origin SIMULATED today |
| `src.SLIP` | Hospital slip, as read | अस्पताल की पर्ची, जैसी पढ़ी गई | रुग्णालयाची पर्ची, जशी वाचली गेली | kind SLIP; LIVE when the slip source is the live reader, else SIMULATED |
| `src.SALES_DAY` | Your sales for the day | उस दिन की आपकी बिक्री | त्या दिवसाची आपली विक्री | kind SALES_DAY; origin SIMULATED today |
| `src.PAYOUT_HISTORY` | Your earlier payouts | आपको पहले मिले भुगतान | आपल्याला आधी मिळालेली रक्कम | kind PAYOUT_HISTORY; origin SIMULATED today |
| `src.LENDER` | Lender's answer | लेंडर का जवाब | लेंडरचे उत्तर | kind LENDER; origin SIMULATED today |

### 5.2 Chip, origin and mode

Origin is LIVE, SIMULATED or CONFIG. Mode (LIVE, SIMULATED or FALLBACK) belongs to an AI reply (H26). A SIMULATED origin always shows the word. With no keys set, every source except the rules, the clause and the zone bound is SIMULATED. A slip read with a Sarvam key is LIVE.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `chip.tap` | Tap to see where this came from. | यह कहाँ से आया, देखने के लिए टैप करें। | हे कुठून आले ते पाहण्यासाठी टॅप करा. | a chip reads: label, time of the record, origin |
| `badge.source_missing` | Source missing | स्रोत नहीं मिला | स्रोत सापडला नाही | shown in place of a number that has no source; the test run fails when it appears |
| `chip.field.record` | Record | रिकॉर्ड | नोंद | - |
| `chip.field.time` | Time | समय | वेळ | - |
| `chip.field.origin` | Type of source | स्रोत का प्रकार | स्रोताचा प्रकार | - |
| `chip.field.clause` | Policy clause | पॉलिसी का खंड | पॉलिसीचे कलम | - |
| `origin.LIVE` | LIVE | LIVE | LIVE | status token, never translated |
| `origin.SIMULATED` | SIMULATED | SIMULATED | SIMULATED | status token, never translated |
| `origin.CONFIG` | CONFIG | CONFIG | CONFIG | status token, never translated |
| `mode.FALLBACK` | FALLBACK | FALLBACK | FALLBACK | status token for AI replies (H26), never translated; arrives with X6 |
| `origin.LIVE.hint` | A real connection supplied this. | यह असली कनेक्शन से आया है। | हे खऱ्या कनेक्शनमधून आले आहे. | - |
| `origin.SIMULATED.hint` | Demo data. No real money, message or payment moves. | डेमो डेटा। असली पैसा, संदेश या भुगतान नहीं जाता। | डेमो डेटा. खरे पैसे, संदेश किंवा पेमेंट जात नाही. | - |
| `origin.CONFIG.hint` | A fixed setting or document that comes with Chhatri. | यह छतरी के साथ आने वाली तय सेटिंग या दस्तावेज़ है। | ही छत्रीसोबत येणारी निश्चित सेटिंग किंवा कागदपत्र आहे. | - |
| `mode.FALLBACK.hint` | A backup is in use because the usual service was not available. | आम सेवा उपलब्ध नहीं थी, इसलिए बैकअप इस्तेमाल हो रहा है। | नेहमीची सेवा उपलब्ध नव्हती, म्हणून बॅकअप वापरले जात आहे. | - |

### 5.3 Clause chips (H17)

Titles for clauses C1 to C12 of the [policy wording](../02-product/policy-wording-and-cis.md). A chip shows the clause id and this title; a sub-clause such as C4.2 shows under its parent.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `clause.C1` | Words we use | इस्तेमाल हुए शब्द | वापरलेले शब्द | policy wording C1 Definitions |
| `clause.C2` | Rain and lost sales | बारिश से बिक्री का नुकसान | पावसामुळे विक्रीचे नुकसान | C2 Coverage: area income loss |
| `clause.C3` | Hospital cash | अस्पताल में आय का नुकसान | रुग्णालयात असताना उत्पन्नाचे नुकसान | C3 Coverage: hospital-cash income loss |
| `clause.C4` | How much we pay | कितना भुगतान होता है | किती रक्कम मिळते | C4 formula, daily caps, yearly limit, what is not paid |
| `clause.C5` | When cover starts | कवर कब शुरू होता है | कवर केव्हा सुरू होते | C5 waiting period and alert look-ahead |
| `clause.C6` | Premium and paying in advance | प्रीमियम और पहले भुगतान | प्रीमियम आणि आधी पेमेंट | C6 Premium and cash before cover |
| `clause.C7` | What is not covered | क्या कवर नहीं है | काय कवर नाही | C7 Exclusions |
| `clause.C8` | How claims are decided | दावे कैसे तय होते हैं | दावे कसे ठरतात | C8 |
| `clause.C9` | Questions and complaints | सवाल और शिकायतें | प्रश्न आणि तक्रारी | C9 Disputes and grievances |
| `clause.C10` | Instalment holiday: your lender decides | किस्त की छुट्टी: लेंडर तय करता है | हप्त्याची सुट्टी: लेंडर ठरवतो | C10 |
| `clause.C11` | Your data and consent | आपका डेटा और सहमति | आपला डेटा आणि संमती | C11 |
| `clause.C12` | Cancelling and renewing | रद्द करना और नवीनीकरण | रद्द करणे आणि नूतनीकरण | C12 Cancellation, renewal and free look |

## 6. Checks and counterfactuals (H14, wave 1)

### 6.1 Check lines

One line per check in the receipt, in merchant words. A passed check shows the line and the word Passed. A failed HARD check shows the built REASON_ text; a SOFT check that failed or was unsure shows the matching TRACK_REFERRED line (section 3.2). The 14 checks and their severities are in `policy/catalogue.py`: ten HARD, four SOFT.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `chk.status.PASS` | Passed | पास | यशस्वी | - |
| `chk.status.FAIL` | Not met | पूरा नहीं हुआ | पूर्ण झाले नाही | - |
| `chk.status.UNSURE` | Not sure | यकीन नहीं | खात्री नाही | UNSURE sends a SOFT check to a person; the word here is about the check, not about the claim |
| `chk.status.NOT_APPLICABLE` | Not needed | ज़रूरी नहीं | गरज नाही | - |
| `chk.status.WAIVED_BY_OFFICER` | Cleared by a claims officer | क्लेम अधिकारी ने आगे बढ़ाया | क्लेम अधिकाऱ्याने पुढे जाऊ दिले | a SOFT check that an officer accepted |
| `CHK_COVER_IN_FORCE` | Your cover was active | आपका कवर चालू था | आपले कवर सुरू होते | - |
| `CHK_PREMIUM_PREPAID` | The premium was paid in advance | प्रीमियम पहले से जमा था | प्रीमियम आधीच भरलेले होते | - |
| `CHK_COVER_BEFORE_ALERT` | Your cover was bought before the alert | आपका कवर अलर्ट से पहले खरीदा गया था | आपले कवर अलर्टच्या आधी घेतले होते | - |
| `CHK_ALERT_ACTIVE` | A weather alert covered your area | आपके इलाके में मौसम अलर्ट था | आपल्या परिसरात हवामान अलर्ट होता | - |
| `CHK_INDEX_QUORUM` | Enough shops were counted in your area | आपके इलाके में काफ़ी दुकानें गिनी गईं | आपल्या परिसरात पुरेशी दुकाने मोजली गेली | - |
| `CHK_BELOW_FLOOR` | Your area's sales stayed below the payout level | आपके इलाके की बिक्री भुगतान की सीमा से नीचे रही | आपल्या परिसरातील विक्री भरपाईच्या पातळीखाली राहिली | - |
| `CHK_BELOW_MODEL_RANGE` | The drop was bigger than a usual slow day | गिरावट आम धीमे दिन से ज़्यादा थी | घट नेहमीच्या मंद दिवसापेक्षा जास्त होती | - |
| `CHK_SILENCE_VERIFIED` | Our records show no sales in your shop all day | हमारे रिकॉर्ड में आपकी दुकान में पूरे दिन बिक्री नहीं है | आमच्या नोंदींनुसार आपल्या दुकानात दिवसभर विक्री नाही | - |
| `CHK_SLIP_READABLE` | The slip is clear | पर्ची साफ़ है | पर्ची स्पष्ट आहे | - |
| `CHK_NAME_MATCHES_KYC` | The name on the slip matches your Paytm account | पर्ची का नाम आपके Paytm खाते से मेल खाता है | पर्चीवरील नाव आपल्या Paytm खात्याशी जुळते | - |
| `CHK_DATES_MATCH` | The slip dates cover the days your shop was closed | पर्ची की तारीख़ें दुकान बंद रहने के दिनों को कवर करती हैं | पर्चीवरील तारखा दुकान बंद असलेल्या दिवसांना व्यापतात | - |
| `CHK_WITHIN_AUTO_LIMIT` | The number of days is within the automatic limit | दिनों की संख्या अपने-आप भुगतान की सीमा के अंदर है | दिवसांची संख्या आपोआप भरपाईच्या मर्यादेत आहे | - |
| `CHK_NOT_ALREADY_PAID` | These days were not paid before | इन दिनों का भुगतान पहले नहीं हुआ | या दिवसांची रक्कम आधी दिली गेली नाही | - |
| `CHK_WITHIN_ANNUAL_LIMIT` | Within your yearly limit | आपकी साल की सीमा के अंदर | आपल्या वार्षिक मर्यादेत | - |

### 6.2 Counterfactual sentences

The engine writes them. It flips the failing facts, re-runs the real engine, and keeps the sentence only when the re-run result is strictly better ([fs-09](../02-product/feature-specs/fs-09-policy-engine-and-audit.md) section 9). A language model never writes, edits or ranks one. A sentence is built as If {condition}, {result}., with at most two per decision. The footer is always printed under them, so that they are not read as a promise. The placeholders map to the fields of the counterfactual object (`changes[].observed`, `changes[].needed`, `result`), and a test checks that every digit in a rendered sentence appears in those fields.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `CF_TITLE` | What would have changed this | क्या बदलता तो नतीजा बदलता | काय बदलले असते तर निकाल बदलला असता | - |
| `CF_FRAME` | If {condition}, {result}. | अगर {condition}, तो {result}। | {condition}, तर {result}. | facts: `condition`, `result`; joins one condition fragment and one result fragment; two conditions are joined with CF_JOIN_AND |
| `CF_JOIN_AND` | and | और | आणि | - |
| `CF_RESULT_APPROVED` | it would have been paid | भुगतान हो जाता | रक्कम दिली गेली असती | the engine's re-run outcome is APPROVED |
| `CF_RESULT_REFERRED` | a person would have checked it | इसे कोई व्यक्ति जाँचता | ती एका व्यक्तीने तपासली असती | the engine's re-run outcome is REFERRED (better than DECLINED) |
| `CF_FOOTER` | This explains this one decision. A future event is decided by the same checks when it happens. | यह सिर्फ़ इस एक फ़ैसले का कारण बताता है। आगे की किसी घटना का फ़ैसला उस समय इन्हीं जाँचों से होगा। | हे फक्त या एका निर्णयाचे कारण सांगते. भविष्यातील घटनेचा निर्णय तेव्हा त्याच तपासण्यांनी ठरेल. | always printed under counterfactual lines so that they are not read as a promise |

### 6.3 Conditions

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `CF_IF_COVER_IN_FORCE` | your cover had been active on {date_en} | {date_hi} को आपका कवर चालू होता | {date_mr} रोजी आपले कवर सुरू असते | facts: `date`; HARD COVER_IN_FORCE failed; not something the merchant can still change |
| `CF_IF_PREMIUM_PREPAID` | the premium for {date_en} had been paid in advance | {date_hi} का प्रीमियम पहले से जमा होता | {date_mr} चे प्रीमियम आधीच भरलेले असते | facts: `date`; HARD PREMIUM_PREPAID failed |
| `CF_IF_COVER_BEFORE_ALERT` | your cover had been bought before the alert was issued, on {issued_en} | आपका कवर अलर्ट जारी होने ({issued_hi}) से पहले खरीदा गया होता | आपले कवर अलर्ट जाहीर होण्यापूर्वी ({issued_mr}) खरेदी केलेले असते | facts: `issued`; HARD COVER_BEFORE_ALERT failed; issued is the alert's issued_at, date and time |
| `CF_IF_ALERT_ACTIVE` | a weather alert had covered your area for all {hours} hours | पूरे {hours} घंटे आपके इलाके में मौसम अलर्ट होता | सर्व {hours} तास आपल्या परिसरात हवामान अलर्ट असता | facts: `hours`; HARD ALERT_ACTIVE failed; hours is rules area.consecutive_hours |
| `CF_IF_INDEX_QUORUM` | at least {min_shops} shops had been counted in your area (there were {shops}) | आपके इलाके में कम से कम {min_shops} दुकानें गिनी जातीं (गिनी गईं: {shops}) | आपल्या परिसरात किमान {min_shops} दुकाने मोजली गेली असती (मोजलेली: {shops}) | facts: `min_shops`, `shops`; HARD INDEX_QUORUM failed; min_shops is rules area.min_shops_in_index |
| `CF_IF_BELOW_FLOOR` | your area's sales had stayed below {floor_pct}% of the usual level for {hours} hours in a row | आपके इलाके की बिक्री लगातार {hours} घंटे आम स्तर के {floor_pct}% से नीचे रहती | आपल्या परिसरातील विक्री सलग {hours} तास नेहमीच्या पातळीच्या {floor_pct}% पेक्षा खाली राहिली असती | facts: `floor_pct`, `hours`; HARD BELOW_FLOOR failed; floor_pct is rules area.index_floor_pct |
| `CF_IF_BELOW_MODEL_RANGE` | your area's sales had been lower than the usual range for a slow day | आपके इलाके की बिक्री आम धीमे दिन के दायरे से नीचे होती | आपल्या परिसरातील विक्री मंद दिवसाच्या नेहमीच्या श्रेणीपेक्षा कमी असती | HARD BELOW_MODEL_RANGE failed; no number is named, because the zone bound is not public wording (fs-09 guardrail) |
| `CF_IF_SILENCE_VERIFIED` | the claim had covered only the days with no sales ({dates_en}) | दावा सिर्फ़ उन दिनों का होता जिनमें बिक्री नहीं हुई ({dates_hi}) | दावा फक्त ज्या दिवशी विक्री झाली नाही त्या दिवसांचा ({dates_mr}) असता | facts: `dates`; HARD SILENCE_VERIFIED failed; the flip limits the claimed days to the verified silent days, and is dropped when there are none |
| `CF_IF_SLIP_READABLE` | the photo of the hospital document had been clear | अस्पताल के कागज़ की फ़ोटो साफ़ होती | रुग्णालयाच्या कागदाची फोटो स्पष्ट असती | SOFT SLIP_READABLE was UNSURE or FAIL; the only flip the merchant can act on (retake the photo) |
| `CF_IF_NAME_MATCHES_KYC` | the name on the slip had matched the name on your Paytm account (KYC) | पर्ची का नाम आपके Paytm खाते (KYC) के नाम से मेल खाता | पर्चीवरील नाव आपल्या Paytm खात्याच्या (KYC) नावाशी जुळले असते | SOFT NAME_MATCHES_KYC failed; states what happened and never coaches a name or a document; the score stays in the officer view |
| `CF_IF_DATES_MATCH` | the stay on the slip had included {dates_en} | पर्ची में दिखे अस्पताल के समय में {dates_hi} शामिल होते | पर्चीवरील रुग्णालयातील मुक्कामात {dates_mr} यांचा समावेश असता | facts: `dates`; SOFT DATES_MATCH failed; dates are the silent days |
| `CF_IF_WITHIN_AUTO_LIMIT` | the claim had covered {max_auto_days} days or fewer | दावा {max_auto_days} दिन या उससे कम का होता | दावा {max_auto_days} दिवस किंवा त्यापेक्षा कमी दिवसांचा असता | facts: `max_auto_days`; SOFT WITHIN_AUTO_LIMIT failed; max_auto_days is rules personal.max_auto_days |

### 6.4 Lines with no single honest condition, amounts and zones

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `CF_EXPLAIN_NOT_ALREADY_PAID` | {dates_en} had already been paid, and one day is not paid twice. | {dates_hi} का भुगतान पहले हो चुका था, और एक दिन का भुगतान दो बार नहीं होता। | {dates_mr} ची रक्कम आधीच दिली गेली होती, आणि एका दिवसाची रक्कम दोनदा दिली जात नाही. | facts: `dates`; kind EXPLAIN_ONLY for HARD NOT_ALREADY_PAID |
| `CF_EXPLAIN_WITHIN_ANNUAL_LIMIT` | Payouts in the past {window_days} days add up to {paid_total}. With this claim the total would pass the yearly limit of {annual_limit}. | पिछले {window_days} दिनों के सारे भुगतान जोड़ें तो {paid_total} होते हैं। इस दावे को जोड़ने पर कुल रकम साल की सीमा {annual_limit} से ऊपर चली जाती। | मागील {window_days} दिवसांतील रक्कम मिळून {paid_total} आहे. हा दावा जोडल्यास एकूण रक्कम वार्षिक मर्यादा {annual_limit} पेक्षा जास्त होईल. | facts: `window_days`, `paid_total`, `annual_limit`; kind EXPLAIN_ONLY for HARD WITHIN_ANNUAL_LIMIT; window_days is the engine's rolling window |
| `CF_AMOUNT_ONE_POINT` | One more point of area drop would have added about {delta}. | इलाके की गिरावट एक प्रतिशत और होती, तो लगभग {delta} और जुड़ते। | परिसरातील घट आणखी एक टक्का असती, तर सुमारे {delta} जास्त मिळाले असते. | facts: `delta`; kind AMOUNT_SENSITIVITY for an APPROVED area payout; delta is the amount one point higher minus the amount paid |
| `CF_AMOUNT_CAP_BOUND` | Half of your usual day is {half_day}, but the most paid for one day is {cap}, so {amount} was paid. | आपके आम दिन का आधा {half_day} है, पर एक दिन का ज़्यादा से ज़्यादा भुगतान {cap} है, इसलिए {amount} दिए गए। | आपल्या नेहमीच्या दिवसाचे निम्मे {half_day} आहे, पण एका दिवसाची जास्तीत जास्त रक्कम {cap} आहे, म्हणून {amount} दिले गेले. | facts: `half_day`, `cap`, `amount`; kind AMOUNT_SENSITIVITY; shown only when the daily cap is what set the amount |
| `CF_AMOUNT_ONE_DAY` | Each extra qualifying day adds {delta}, up to {max_auto_days} days without a review. | हर अतिरिक्त पात्र दिन के {delta} जुड़ते हैं, बिना समीक्षा के ज़्यादा से ज़्यादा {max_auto_days} दिन तक। | प्रत्येक अतिरिक्त पात्र दिवसाचे {delta} वाढतात, पुनरावलोकनाशिवाय जास्तीत जास्त {max_auto_days} दिवसांपर्यंत. | facts: `delta`, `max_auto_days`; kind AMOUNT_SENSITIVITY for an APPROVED hospital-cash payout |
| `CF_ZONE_NO_TRIGGER` | Zone {zone_number} sales were {index_pct}% of the usual level, with no weather alert. A payout needs an alert for all {hours} hours and every hour below {floor_pct}%. | ज़ोन {zone_number} की बिक्री आम स्तर की {index_pct}% रही और कोई मौसम अलर्ट नहीं था। भुगतान के लिए सभी {hours} घंटे अलर्ट और हर घंटे {floor_pct}% से नीचे बिक्री ज़रूरी है। | झोन {zone_number} ची विक्री नेहमीच्या पातळीच्या {index_pct}% राहिली आणि हवामान अलर्ट नव्हता. भरपाईसाठी सर्व {hours} तास अलर्ट आणि प्रत्येक तासाला {floor_pct}% पेक्षा कमी विक्री आवश्यक आहे. | facts: `zone_number`, `index_pct`, `hours`, `floor_pct`; kind ZONE_NO_TRIGGER; extends the BUILT slow-day sentence (Appendix B); fs-09 proposes a zone_notice field for the merchant card |
| `CF_ZONE_NO_TRIGGER_HOURS` | Hour by hour: {hour_values}. | घंटे-दर-घंटे: {hour_values}। | तासागणिक: {hour_values}. | facts: `hour_values`; console and judge view only; hour_values is a preformatted list such as 59%, 58%, 67% |

## 7. Jargon lens (H20, wave 1)

Fifteen terms with the ids of the mini-app spec ([fs-04](../02-product/feature-specs/fs-04-merchant-mini-app.md) section 11), which is the build contract for the glossary. Each term has a label, a plain explanation and one example. The lens opens from any underlined word in the explainer, the receipt, the tracker and the chat. Examples use the golden demo numbers and say so in the last column; rules numbers arrive through placeholders.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `lens.title` | What does this word mean? | इस शब्द का मतलब क्या है? | या शब्दाचा अर्थ काय? | heading of the lens sheet |
| `lens.plain` | In plain words | सरल शब्दों में | सोप्या शब्दांत | label above the explanation |
| `lens.example` | Example | उदाहरण | उदाहरण | label above the example |
| `lens.close` | Close | बंद करें | बंद करा | closes the sheet; focus returns to the term |
| `lens.footer` | This explains the word in plain language. The policy wording has the exact terms. | यह शब्द को आसान भाषा में समझाता है। सही शर्तें पॉलिसी के शब्दों में हैं। | हे शब्द सोप्या भाषेत समजावते. नेमक्या अटी पॉलिसीच्या शब्दांत आहेत. | shown under every lens card |
| `jargon.waiting_period.term` | Waiting period | वेटिंग पीरियड | वेटिंग पीरियड | id waiting_period; explainer c5, buy screen, BLOCKED message |
| `jargon.waiting_period.what` | A new cover starts {waiting_days} days after you ask. Until then it does not pay. | नया कवर माँगने के {waiting_days} दिन बाद शुरू होता है। तब तक यह भुगतान नहीं करता। | नवीन कवर मागितल्यानंतर {waiting_days} दिवसांनी सुरू होते. तोपर्यंत ते रक्कम देत नाही. | facts: `waiting_days`; days from the rules API |
| `jargon.waiting_period.example` | Ramesh asks on Monday 18 August. His cover starts on 25 August. | रमेश सोमवार 18 अगस्त को कवर माँगते हैं। उनका कवर 25 अगस्त से शुरू होता है। | रमेश सोमवारी 18 ऑगस्टला कवर मागतात. त्यांचे कवर 25 ऑगस्टपासून सुरू होते. | demo dates: scenario buy_cover, merchant S-0907; an acceptance test looks for 25 August |
| `jargon.alert.term` | Weather alert | मौसम अलर्ट | हवामान अलर्ट | id alert; explainer c2 and c5, home banner, receipt |
| `jargon.alert.what` | A weather warning for your area. Cover bought after an alert is issued does not pay for that alert. | आपके इलाके के लिए मौसम की चेतावनी। अलर्ट जारी होने के बाद लिया गया कवर उस अलर्ट के लिए भुगतान नहीं करता। | आपल्या परिसरासाठी हवामानाचा इशारा. अलर्ट जाहीर झाल्यानंतर घेतलेले कवर त्या अलर्टसाठी रक्कम देत नाही. | - |
| `jargon.alert.example` | Alert A-20250818-01 was issued on Monday 18 August at 17:30 for the next day. | अलर्ट A-20250818-01 सोमवार 18 अगस्त को 17:30 बजे अगले दिन के लिए जारी हुआ था। | अलर्ट A-20250818-01 सोमवारी 18 ऑगस्टला 17:30 वाजता पुढील दिवसासाठी जाहीर झाला होता. | demo alert; alerts are SIMULATED today |
| `jargon.expected_day.term` | Your usual day | आपका आम दिन | आपला नेहमीचा दिवस | id expected_day; explainer c2, receipt, home |
| `jargon.expected_day.what` | What Chhatri expects your shop to sell on this day of the week, worked out from your past sales. | हफ़्ते के इस दिन छतरी के हिसाब से आपकी दुकान की आम बिक्री, जो आपकी पिछली बिक्री से निकाली जाती है। | आठवड्याच्या या दिवशी छत्रीच्या हिशोबाने आपल्या दुकानाची साधारण विक्री, जी आपल्या मागील विक्रीवरून काढली जाते. | - |
| `jargon.expected_day.example` | Anil's usual Tuesday: ₹4,380. | अनिल का आम मंगलवार: ₹4,380। | अनिल यांचा नेहमीचा मंगळवार: ₹4,380. | demo number: Anil, S-0142 |
| `jargon.area_drop.term` | Area drop | इलाके की गिरावट | परिसरातील घट | id area_drop; explainer c2, receipt, tracker |
| `jargon.area_drop.what` | How far sales across the shops in your area fell below what was expected, in per cent. | आपके इलाके की दुकानों की बिक्री उम्मीद से कितने प्रतिशत गिरी। | आपल्या परिसरातील दुकानांची विक्री अपेक्षेपेक्षा किती टक्के घटली. | - |
| `jargon.area_drop.example` | On 19 August Zone 7 was at 37% of expected, a 63% drop. | 19 अगस्त को ज़ोन 7 उम्मीद का 37% रहा, यानी 63% की गिरावट। | 19 ऑगस्टला झोन 7 अपेक्षेच्या 37% राहिला, म्हणजे 63% घट. | demo numbers: Z7 at 17:00 |
| `jargon.payout_share.term` | Chhatri's share | छतरी का हिस्सा | छत्रीचा वाटा | id payout_share; explainer c2 and c4, receipt |
| `jargon.payout_share.what` | Chhatri pays {share_pct}% of the sales you lost. | छतरी आपकी खोई हुई बिक्री का {share_pct}% देती है। | छत्री आपल्या गमावलेल्या विक्रीच्या {share_pct}% रक्कम देते. | facts: `share_pct`; share_pct from the rules API |
| `jargon.payout_share.example` | ½ × ₹4,380 × 63% = ₹1,380: half, times your usual day, times the area drop. | ½ × ₹4,380 × 63% = ₹1,380: आधा × आपका आम दिन × इलाके की गिरावट। | ½ × ₹4,380 × 63% = ₹1,380: निम्मे × आपला नेहमीचा दिवस × परिसरातील घट. | demo numbers: the golden payout; the unrounded value is ₹1,379.70 |
| `jargon.daily_cap.term` | Daily limit | रोज़ की सीमा | रोजची मर्यादा | id daily_cap; explainer c4, receipt |
| `jargon.daily_cap.what` | The most Chhatri pays for one day: {area_cap} for rain and {personal_cap} for hospital cash. | एक दिन के लिए छतरी जितना ज़्यादा से ज़्यादा देती है: बारिश के लिए {area_cap} और अस्पताल के लिए {personal_cap}। | एका दिवसासाठी छत्री जास्तीत जास्त जितकी रक्कम देते: पावसासाठी {area_cap} आणि रुग्णालयासाठी {personal_cap}. | facts: `area_cap`, `personal_cap`; caps from the rules API |
| `jargon.daily_cap.example` | Half of a ₹4,300 day is ₹2,150, but the hospital limit is ₹1,500 a day, so ₹1,500 is paid. | ₹4,300 के दिन का आधा ₹2,150 है, पर अस्पताल की रोज़ की सीमा ₹1,500 है, इसलिए ₹1,500 दिए जाते हैं। | ₹4,300 च्या दिवसाचे निम्मे ₹2,150 आहे, पण रुग्णालयाची रोजची मर्यादा ₹1,500 आहे, म्हणून ₹1,500 दिले जातात. | demo numbers: the personal claim |
| `jargon.annual_limit.term` | Yearly limit | साल की सीमा | वार्षिक मर्यादा | id annual_limit; explainer c4, home, receipt |
| `jargon.annual_limit.what` | The most Chhatri pays you in any {window_days} days: {annual_limit}. | किसी भी {window_days} दिनों में छतरी आपको जितना ज़्यादा से ज़्यादा देती है: {annual_limit}। | कोणत्याही {window_days} दिवसांत छत्री आपल्याला जास्तीत जास्त जितकी रक्कम देते: {annual_limit}. | facts: `window_days`, `annual_limit`; window and limit from the rules API |
| `jargon.annual_limit.example` | A claim that would take you over the limit is not paid. | जो दावा आपको सीमा के ऊपर ले जाए, उसका भुगतान नहीं होता। | जो दावा आपल्याला मर्यादेच्या वर नेईल, त्याची रक्कम दिली जात नाही. | engine check WITHIN_ANNUAL_LIMIT |
| `jargon.premium.term` | Premium | प्रीमियम | प्रीमियम | id premium; explainer c6, buy screen, receipt |
| `jargon.premium.what` | The small amount you pay each day for cover. | कवर के लिए आप हर दिन जो थोड़ी रकम देते हैं। | कवरसाठी आपण दररोज भरत असलेली थोडी रक्कम. | - |
| `jargon.premium.example` | In the demo, Zone 3 costs ₹14.16 a day, so 30 days is ₹424.80. The real price is not decided. | डेमो में ज़ोन 3 का प्रीमियम रोज़ ₹14.16 है, इसलिए 30 दिन के ₹424.80। असली कीमत अभी तय नहीं हुई है। | डेमोमध्ये झोन 3 चे प्रीमियम रोज ₹14.16 आहे, म्हणून 30 दिवसांचे ₹424.80. खरी किंमत अजून ठरलेली नाही. | demo numbers: Z3 premium from the backtest |
| `jargon.prepaid_through.term` | Paid up to | इस तारीख़ तक जमा | या तारखेपर्यंत भरलेले | id prepaid_through; home, buy screen |
| `jargon.prepaid_through.what` | Cover works on days whose premium was paid in advance. This is the last paid day. | कवर उन दिनों काम करता है जिनका प्रीमियम पहले से जमा हो। यह आख़िरी जमा दिन है। | ज्या दिवसांचे प्रीमियम आधी भरलेले असते त्या दिवसांना कवर लागू होते. हा शेवटचा भरलेला दिवस आहे. | - |
| `jargon.prepaid_through.example` | Ramesh's ₹424.80 pays for 30 days, 25 August to 23 September. | रमेश के ₹424.80 से 30 दिन का प्रीमियम जमा होता है, 25 अगस्त से 23 सितंबर तक। | रमेश यांच्या ₹424.80 मधून 30 दिवसांचे प्रीमियम भरले जाते, 25 ऑगस्ट ते 23 सप्टेंबर. | demo numbers: the covers_to date is the start date plus 29 days |
| `jargon.settlement.term` | Settlement | सेटलमेंट | सेटलमेंट | id settlement; home, tracker, receipt, PAYOUT_CARD |
| `jargon.settlement.what` | The transfer of your Paytm sales to your bank account. | आपकी Paytm बिक्री का आपके बैंक खाते में जाना। | आपल्या Paytm विक्रीचे आपल्या बँक खात्यात जाणे. | - |
| `jargon.settlement.example` | Anil's ₹1,380 arrived with the settlement at 17:04 (SIMULATED). | अनिल के ₹1,380 17:04 पर सेटलमेंट के साथ आए (SIMULATED)। | अनिल यांचे ₹1,380 17:04 वाजता सेटलमेंटसोबत आले (SIMULATED). | demo numbers; the BUILT PAYOUT_CARD line reads: Credited with today's settlement |
| `jargon.edi_holiday.term` | Instalment holiday (EDI) | किस्त की छुट्टी (EDI) | हप्त्याची सुट्टी (EDI) | id edi_holiday; explainer c10, tracker, receipt, holiday messages |
| `jargon.edi_holiday.what` | If you repay your loan every day (EDI), your lender can pause one day's instalment. The lender decides, not Chhatri. | अगर आप अपना लोन हर दिन की किस्त (EDI) से चुकाते हैं, तो आपका लेंडर एक दिन की किस्त रोक सकता है। फ़ैसला लेंडर का होता है, छतरी का नहीं। | आपण आपले कर्ज रोजच्या हप्त्याने (EDI) फेडत असाल, तर आपला लेंडर एका दिवसाचा हप्ता थांबवू शकतो. निर्णय लेंडरचा असतो, छत्रीचा नाही. | ADR 0006 wording; EDI means equated daily instalment |
| `jargon.edi_holiday.example` | Anil's ₹600 instalment: Chhatri asks, the lender answers. | अनिल की ₹600 की किस्त: छतरी पूछती है, लेंडर जवाब देता है। | अनिल यांचा ₹600 चा हप्ता: छत्री विचारते, लेंडर उत्तर देतो. | demo number: Anil's instalment |
| `jargon.kyc.term` | KYC | KYC | KYC | id kyc; receipt, slip pre-check, referred claims |
| `jargon.kyc.what` | The identity details Paytm already holds about you, such as your name. | आपके बारे में Paytm के पास पहले से मौजूद पहचान की जानकारी, जैसे आपका नाम। | आपल्याबद्दल Paytm कडे आधीपासून असलेली ओळखीची माहिती, उदाहरणार्थ आपले नाव. | - |
| `jargon.kyc.example` | The name on a hospital slip is compared with your KYC name. A score of {name_match_min} or more matches. | अस्पताल की पर्ची का नाम आपके KYC नाम से मिलाया जाता है। {name_match_min} या उससे ज़्यादा स्कोर पर नाम मेल खाता है। | रुग्णालयाच्या पर्चीवरील नावाची आपल्या KYC नावाशी तुलना केली जाते. {name_match_min} किंवा त्यापेक्षा जास्त गुण असतील तर नाव जुळते. | facts: `name_match_min`; name_match_min from the rules API |
| `jargon.referred.term` | With a claims officer | हमारी टीम देख रही है | आमची टीम पाहत आहे | id referred; tracker, receipt |
| `jargon.referred.what` | A person at Chhatri decides. It is not a refusal. You hear back within {sla_hours} hours. | हमारी टीम का कोई व्यक्ति फ़ैसला करेगा। यह इनकार नहीं है। {sla_hours} घंटे में जवाब मिलेगा। | आमच्या टीममधील एक व्यक्ती निर्णय घेईल. हा नकार नाही. {sla_hours} तासांत उत्तर मिळेल. | facts: `sla_hours`; sla_hours from the rules API |
| `jargon.referred.example` | The name "Sunil Pawar" on the slip did not match KYC, so case C-2291 went to an officer. | पर्ची पर नाम "सुनील पवार" KYC से मेल नहीं खाया, इसलिए केस C-2291 अधिकारी के पास गया। | पर्चीवरील "सुनील पवार" हे नाव KYC शी जुळले नाही, म्हणून केस C-2291 अधिकाऱ्याकडे गेला. | demo names and case id: scenario illness_mismatch |
| `jargon.audit_fingerprint.term` | Audit code | ऑडिट कोड | ऑडिट कोड | id audit_fingerprint; receipt |
| `jargon.audit_fingerprint.what` | Each decision is written to a chained log. Changing an old line would break the chain. This code identifies this decision's line. | हर फ़ैसला एक जुड़ी हुई कड़ियों वाले लॉग में लिखा जाता है। पुरानी लाइन बदलने से कड़ी टूट जाती है। यह कोड इस फ़ैसले की लाइन की पहचान है। | प्रत्येक निर्णय जोडलेल्या कड्यांच्या लॉगमध्ये लिहिला जातो. जुनी ओळ बदलली तर साखळी तुटते. हा कोड या निर्णयाच्या ओळीची ओळख आहे. | - |
| `jargon.audit_fingerprint.example` | "Check the log" tells you whether the whole log is unbroken. | "लॉग जाँचें" बताता है कि पूरा लॉग सही है या नहीं। | "लॉग तपासा" सांगते की संपूर्ण लॉग अखंड आहे की नाही. | the button label is receipt.check_log |
| `jargon.rules_version.term` | Rules version | नियमों का संस्करण | नियमांची आवृत्ती | id rules_version; receipt, explainer |
| `jargon.rules_version.what` | The version of the rule book used for this decision. | इस फ़ैसले में इस्तेमाल हुए नियमों का संस्करण। | या निर्णयात वापरलेल्या नियमांची आवृत्ती. | - |
| `jargon.rules_version.example` | For example: {rules_version}. | उदाहरण: {rules_version}। | उदाहरण: {rules_version}. | facts: `rules_version`; rules_version from rules.yaml |

## 8. Next action (H21)

Every screen and every chat answer ends with a clear next step. There is no dead end, and no next action is ever an offer: there is no loan, top-up or cross-sell kind, so X8 holds by construction. The screen bar is wave 1. The chat next action arrives with Ask Chhatri in wave 2.

### 8.1 Screens: a sentence and a button for each rule

Each rule of the next-best-action bar in the mini-app spec ([fs-04](../02-product/feature-specs/fs-04-merchant-mini-app.md) section 12) has a sentence `nba.<rule id>` and a button `nba.<rule id>.btn`. Rule ids, conditions and targets are the spec's. This table holds the words, and its last column says where the rule applies.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `nba.get_cover_from_coverage` | Ready for cover? Check your price and start date. | कवर लेना है? कीमत और शुरू होने की तारीख़ देखें। | कवर घ्यायचे आहे? किंमत आणि सुरू होण्याची तारीख पहा. | sentence of rule get_cover_from_coverage; screen: coverage explainer; merchant has no cover |
| `nba.get_cover_from_coverage.btn` | Get cover | कवर लें | कवर घ्या | button of rule get_cover_from_coverage |
| `nba.see_claims` | See what Chhatri has done for you. | देखिए छतरी ने आपके लिए क्या किया। | छत्रीने आपल्यासाठी काय केले ते पहा. | sentence of rule see_claims; screen: coverage explainer; any claim exists |
| `nba.see_claims.btn` | See my claims | मेरे दावे देखें | माझे दावे पहा | button of rule see_claims |
| `nba.home_from_coverage` | That is all about cover. | कवर के बारे में बस इतना ही। | कवरबद्दल एवढेच. | sentence of rule home_from_coverage; screen: coverage explainer; otherwise |
| `nba.home_from_coverage.btn` | Back to Home | होम पर वापस | मुख्यपृष्ठावर परत | button of rule home_from_coverage |
| `nba.tick_consent` | Tick the boxes marked Needed for cover to go on. | आगे बढ़ने के लिए “कवर के लिए ज़रूरी” वाले बॉक्स चुनें। | पुढे जाण्यासाठी “कवरसाठी आवश्यक” असे लिहिलेले बॉक्स निवडा. | sentence of rule tick_consent; screen: get cover; the consent block is incomplete (wave 3); checked before check_price |
| `nba.tick_consent.btn` | Go to the boxes | बॉक्स पर जाएँ | बॉक्सकडे जा | button of rule tick_consent |
| `nba.check_price` | See your price and start date first. | पहले अपनी कीमत और शुरू होने की तारीख़ देखें। | आधी आपली किंमत आणि सुरू होण्याची तारीख पहा. | sentence of rule check_price; screen: buy; no quote yet; focuses the button |
| `nba.check_price.btn` | Check price and start date | कीमत और शुरू होने की तारीख़ देखें | किंमत आणि सुरू होण्याची तारीख पहा | button of rule check_price |
| `nba.pay` | Pay the first payment to start your cover. | कवर शुरू करने के लिए पहला भुगतान करें। | कवर सुरू करण्यासाठी पहिले पेमेंट करा. | sentence of rule pay; screen: buy; a quote with a link; while the Paytm component is SIMULATED the button reads buy.simulate |
| `nba.pay.btn` | Pay with Paytm | Paytm से भुगतान करें | Paytm ने पेमेंट करा | button of rule pay |
| `nba.home_after_paid` | Payment received. | आपका भुगतान आ गया। | पेमेंट मिळाले. | sentence of rule home_after_paid; screen: buy; paid |
| `nba.home_after_paid.btn` | Back to Home | होम पर वापस | मुख्यपृष्ठावर परत | button of rule home_after_paid |
| `nba.home_when_covered` | You already have cover. | आपके पास पहले से कवर है। | आपल्याकडे आधीपासून कवर आहे. | sentence of rule home_when_covered; screen: buy; the merchant already has cover |
| `nba.home_when_covered.btn` | Back to Home | होम पर वापस | मुख्यपृष्ठावर परत | button of rule home_when_covered |
| `nba.open_latest` | Open your latest claim to see each step. | हर कदम देखने के लिए अपना ताज़ा दावा खोलें। | प्रत्येक टप्पा पाहण्यासाठी आपला ताजा दावा उघडा. | sentence of rule open_latest; screen: claims; the list is not empty |
| `nba.open_latest.btn` | Open the latest claim | ताज़ा दावा खोलें | ताजा दावा उघडा | button of rule open_latest |
| `nba.see_coverage_empty` | No claims yet. See what is covered. | अभी कोई दावा नहीं। देखें क्या कवर है। | अजून कोणताही दावा नाही. काय कवर आहे ते पहा. | sentence of rule see_coverage_empty; screen: claims; the list is empty |
| `nba.see_coverage_empty.btn` | See what is covered | क्या कवर है, देखें | काय कवर आहे ते पहा | button of rule see_coverage_empty |
| `nba.wait_for_officer` | A claims officer is looking at this. You will hear back within {sla_hours} hours. | क्लेम अधिकारी इसे देख रहे हैं। {sla_hours} घंटे में जवाब मिलेगा। | क्लेम अधिकारी हे पाहत आहेत. {sla_hours} तासांत उत्तर मिळेल. | facts: `sla_hours`; sentence of rule wait_for_officer; screen: claim detail; a dispute is open or the claim is referred |
| `nba.wait_for_officer.btn` | Back to claims | दावों पर वापस | दाव्यांकडे परत | button of rule wait_for_officer |
| `nba.see_why` | Your payout of {amount} was credited. See how it was worked out. | आपके {amount} जमा हो गए हैं। देखिए हिसाब कैसे बना। | आपले {amount} जमा झाले आहेत. हिशोब कसा झाला ते पहा. | facts: `amount`; sentence of rule see_why; global list and claim detail; the latest claim is paid |
| `nba.see_why.btn` | Why this amount? | इतने पैसे क्यों? | इतकी रक्कम का? | button of rule see_why |
| `nba.back_to_claims` | That is all for this claim. | इस दावे के बारे में बस इतना ही। | या दाव्याबद्दल एवढेच. | sentence of rule back_to_claims; screen: claim detail; otherwise |
| `nba.back_to_claims.btn` | Back to claims | दावों पर वापस | दाव्यांकडे परत | button of rule back_to_claims |
| `nba.see_receipt` | Keep a receipt of this decision. | इस फ़ैसले की रसीद अपने पास रखें। | या निर्णयाची पावती आपल्याजवळ ठेवा. | sentence of rule see_receipt; screen: why this amount |
| `nba.see_receipt.btn` | See the receipt | रसीद देखें | पावती पहा | button of rule see_receipt |
| `nba.disagree` | Do you disagree? Tell us. | सहमत नहीं हैं? हमें बताइए। | सहमत नाही का? आम्हाला सांगा. | sentence of rule disagree; screen: receipt; the claim is paid; focuses the dispute button on the claim detail |
| `nba.disagree.btn` | This is wrong | यह ग़लत है | हे चुकीचे आहे | button of rule disagree |
| `nba.home_after_language` | Language saved. | भाषा सेव हो गई। | भाषा सेव्ह झाली. | sentence of rule home_after_language; screen: language |
| `nba.home_after_language.btn` | Back to Home | होम पर वापस | मुख्यपृष्ठावर परत | button of rule home_after_language |
| `nba.get_cover_from_consents` | You agree to these when you buy cover. | कवर खरीदते समय आप इन पर सहमति देते हैं। | कवर खरेदी करताना आपण यांना संमती देता. | sentence of rule get_cover_from_consents; screen: consent centre; merchant has no cover (wave 3) |
| `nba.get_cover_from_consents.btn` | Get cover | कवर लें | कवर घ्या | button of rule get_cover_from_consents |
| `nba.see_activity` | See what was used, and when. | देखिए कब क्या इस्तेमाल हुआ। | केव्हा काय वापरले ते पहा. | sentence of rule see_activity; screen: consent centre; otherwise (wave 3) |
| `nba.see_activity.btn` | See what was used | देखें क्या इस्तेमाल हुआ | काय वापरले ते पहा | button of rule see_activity |
| `nba.back_to_consents` | That is what was used so far. | अब तक यही इस्तेमाल हुआ है। | आतापर्यंत एवढेच वापरले आहे. | sentence of rule back_to_consents; screen: consent activity; always (wave 3) |
| `nba.back_to_consents.btn` | My data and consent | मेरा डेटा और सहमति | माझा डेटा आणि संमती | button of rule back_to_consents |
| `nba.see_dispute_case` | Your case is with a claims officer. You will hear back within {sla_hours} hours. | आपका केस क्लेम अधिकारी के पास है। {sla_hours} घंटे में जवाब मिलेगा। | आपला केस क्लेम अधिकाऱ्याकडे आहे. {sla_hours} तासांत उत्तर मिळेल. | facts: `sla_hours`; sentence of rule see_dispute_case; global list 1; a dispute is open |
| `nba.see_dispute_case.btn` | See my case | मेरा केस देखें | माझा केस पहा | button of rule see_dispute_case |
| `nba.see_referred_claim` | A claims officer is checking your claim. | क्लेम अधिकारी आपका दावा जाँच रहे हैं। | क्लेम अधिकारी आपला दावा तपासत आहेत. | sentence of rule see_referred_claim; global list 2; a personal claim is referred |
| `nba.see_referred_claim.btn` | See my claim | मेरा दावा देखें | माझा दावा पहा | button of rule see_referred_claim |
| `nba.send_slip` | Send one photo of your hospital slip. | अपनी अस्पताल की पर्ची की एक फ़ोटो भेजें। | आपल्या रुग्णालयाच्या पर्चीचा एक फोटो पाठवा. | sentence of rule send_slip; global list 3; a personal claim waits for the slip and the slip pre-check is switched on |
| `nba.send_slip.btn` | Send the slip photo | पर्ची की फ़ोटो भेजें | पर्चीचा फोटो पाठवा | button of rule send_slip |
| `nba.see_coverage_waiting` | Your cover starts on {starts_on}. | आपका कवर {starts_on} से शुरू होगा। | आपले कवर {starts_on} पासून सुरू होईल. | facts: `starts_on`; sentence of rule see_coverage_waiting; global list 5; cover is WAITING; same text as the BUILT COVER_STATUS_STARTS |
| `nba.see_coverage_waiting.btn` | See what is covered | क्या कवर है, देखें | काय कवर आहे ते पहा | button of rule see_coverage_waiting |
| `nba.get_cover` | You have no cover yet. | अभी आपके पास कवर नहीं है। | आपल्याकडे अजून कवर नाही. | sentence of rule get_cover; global list 6; no cover |
| `nba.get_cover.btn` | Get cover | कवर लें | कवर घ्या | button of rule get_cover |
| `nba.see_premium` | Your premium is not paid for the coming days. See how it works. | आगे के दिनों का प्रीमियम जमा नहीं है। देखिए यह कैसे काम करता है। | पुढील दिवसांचे प्रीमियम भरलेले नाही. हे कसे चालते ते पहा. | sentence of rule see_premium; global list 7; the premium is due |
| `nba.see_premium.btn` | See how it works | देखें यह कैसे काम करता है | हे कसे चालते ते पहा | button of rule see_premium |
| `nba.alert_notice` | There is an alert for your area. If your area's sales fall, Chhatri checks the numbers on its own. | आपके इलाके के लिए अलर्ट है। इलाके की बिक्री गिरे, तो छतरी अपने-आप आँकड़े जाँचती है। | आपल्या परिसरासाठी अलर्ट आहे. परिसरातील विक्री घटली, तर छत्री आपोआप आकडे तपासते. | sentence of rule alert_notice; global list 8; an alert is in force and the cover is ACTIVE; softened from a sentence that said Chhatri pays on its own |
| `nba.alert_notice.btn` | See what is covered | क्या कवर है, देखें | काय कवर आहे ते पहा | button of rule alert_notice |
| `nba.ask` | Have a question? Ask Chhatri. | कोई सवाल है? छतरी से पूछें। | काही प्रश्न आहे का? छत्रीला विचारा. | sentence of rule ask; global list 9; Ask Chhatri is switched on |
| `nba.ask.btn` | Ask Chhatri | छतरी से पूछें | छत्रीला विचारा | button of rule ask |
| `nba.see_coverage` | See what you are covered for. | देखिए आपको किस नुकसान का कवर मिलता है। | आपल्याला कोणत्या नुकसानीचे कवर मिळते ते पहा. | sentence of rule see_coverage; global list 10; otherwise |
| `nba.see_coverage.btn` | See what is covered | क्या कवर है, देखें | काय कवर आहे ते पहा | button of rule see_coverage |
| `nba.btn.ask_lender` | Ask the lender about this | इस बारे में लेंडर से पूछें | याबद्दल लेंडरला विचारा | next step after HOLIDAY_REFUSED or HOLIDAY_NO_RESPONSE; opens a complaint with topic EDI_HOLIDAY and the lender as respondent |

### 8.2 Chat: the next action of an answer

Every Ask Chhatri answer carries one next action. The backend chooses it from the answer type and the merchant's state, never the model, and the enum is closed ([fs-05](../02-product/feature-specs/fs-05-ask-chhatri.md) section 9). The mini-app and the phone simulator show it as one button.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `next_action.SEE_CLAIM` | See my claim | मेरा दावा देखें | माझा दावा पहा | after WHY_AMOUNT is answered, or a model answer that cites C2, C3, C4, C8 or C10 when the merchant has a decision |
| `next_action.SEE_COVER` | See my cover | मेरा कवर देखें | माझे कवर पहा | after COVER_STATUS is answered, or a model answer that cites C5, C6, C7 or C12 |
| `next_action.GET_COVER` | Get cover | कवर लें | कवर घ्या | after BUY_COVER is answered |
| `next_action.SEND_SLIP` | Send the slip photo | पर्ची की फ़ोटो भेजें | पर्चीचा फोटो पाठवा | after REPORT_ILLNESS while a check-in is open |
| `next_action.TRACK_CASE` | Track my case | केस की स्थिति देखें | केसची स्थिती पहा | after DISPUTE_AMOUNT opens a case |
| `next_action.OPEN_CONSENTS` | See my consents | मेरी सहमति देखें | माझी संमती पहा | after a model answer that cites C11; needs N6 (wave 3), before that ASK_AGAIN |
| `next_action.TALK_TO_TEAM` | Talk to the team | टीम से बात करें | टीमशी बोला | after a hand-off, a clause C9 answer or an out-of-scope question; opens the dispute button, or the complaint ladder once N5 is on |
| `next_action.ASK_AGAIN` | Ask another question | दूसरा सवाल पूछें | दुसरा प्रश्न विचारा | after GREETING, FALLBACK_HELP, a scam warning, a strong injection signal or a simulated answer |

### 8.3 WhatsApp reply buttons (proposed)

The built WhatsApp payload supports up to three reply buttons, with titles of at most 20 characters, and the inbound parser replays a tapped title as text. No catalogue message sets buttons today. This section proposes nine titles for real WhatsApp, where a button cannot open a screen. A title must classify as intended when it is replayed; conversation design section 10.6 lists the intent that each title produces and the message it follows. Two points. A title such as No, not right is read as a dispute (the disagreement list holds not right and सही नहीं), so no title says that. And no title offers a bare OK outside a silent-shop check-in, because AFFIRM and DENY answer nothing else today.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `chip.why` | Why this amount? | इतने पैसे क्यों? | इतकी रक्कम का? | button title, 20 characters at most; after a payout notice, only when a payout was decided today |
| `chip.disagree` | I disagree | यह ग़लत है | हे चुकीचे आहे | button title, 20 characters at most; after a payout notice or an explanation |
| `chip.cover_status` | Is my cover active? | मेरा कवर चालू है? | कवर सुरू आहे का? | button title, 20 characters at most; after FALLBACK_HELP, CHECKIN_OK and PREMIUM_PAID_* |
| `chip.buy` | Buy cover | कवर खरीदें | कवर खरेदी करा | button title, 20 characters at most; after FALLBACK_HELP when the merchant has no cover |
| `chip.buy_again` | Buy cover again | फिर से कवर खरीदें | पुन्हा कवर खरेदी करा | button title, 20 characters at most; after COVER_LINK_UNAVAILABLE |
| `chip.hospital` | I am in hospital | मैं अस्पताल में हूँ | मी रुग्णालयात आहे | button title, 20 characters at most; after CHECKIN_SILENT and CHECKIN_WHAT_HAPPENED |
| `chip.someone_ill` | Someone is ill | कोई बीमार है | कोणीतरी आजारी आहे | button title, 20 characters at most; after CHECKIN_WHAT_HAPPENED |
| `chip.all_fine` | All is fine | सब ठीक है | सगळे ठीक आहे | button title, 20 characters at most; after CHECKIN_SILENT only; AFFIRM answers nothing else today |
| `chip.not_fine` | No, not fine | नहीं, ठीक नहीं | नाही, ठीक नाही | button title, 20 characters at most; after CHECKIN_SILENT only; DENY answers nothing else today |

## 9. Ask Chhatri (N2, H16, H17, wave 2)

Ask Chhatri explains; the rules decide every payout. It answers only from the policy clauses and the merchant's own decisions and cases ([fs-05](../02-product/feature-specs/fs-05-ask-chhatri.md)). Any model text passes the guard before it is shown (conversation design, section 5). When every link of the chain fails, or the guard blocks the reply, the answer is the built FALLBACK_HELP, labelled FALLBACK with the reason of the last failed link. When the model declines, the answer is ASK_HANDOFF. The fixed lines in 9.2 are never model text.

### 9.1 Screen

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `ask.title` | Ask Chhatri | छतरी से पूछें | छत्रीला विचारा | hidden until N2 is switched on |
| `ask.placeholder` | Ask about your cover, a claim or a payout | अपने कवर, दावे या भुगतान के बारे में पूछें | आपल्या कवर, दाव्याबद्दल किंवा रकमेबद्दल विचारा | placeholder of the text box; the box takes at most 500 characters |
| `ask.scope` | You can ask about your cover, your claims and your payouts. | आप अपने कवर, दावों और भुगतानों के बारे में पूछ सकते हैं। | आपण आपले कवर, दावे आणि रक्कम याबद्दल विचारू शकता. | first line of the empty Ask screen |
| `ask.rules_decide` | Chhatri explains. The rules decide every payout, not this assistant. | छतरी समझाती है। हर भुगतान का फ़ैसला नियम करते हैं, यह सहायक नहीं। | छत्री समजावते. प्रत्येक रकमेचा निर्णय नियम घेतात, हा सहाय्यक नाही. | second line of the empty Ask screen |
| `ask.btn.send` | Send | भेजें | पाठवा | disabled while a voice question has an unconfirmed amount or date |
| `ask.btn.cancel` | Cancel | रद्द करें | रद्द करा | while the answer is being prepared |
| `ask.thinking` | Looking at your records… | आपका रिकॉर्ड देखा जा रहा है… | आपली नोंद पाहिली जात आहे… | spinner text |
| `ask.elapsed` | Still working… {seconds} seconds | अभी भी काम चल रहा है… {seconds} सेकंड | अजून काम सुरू आहे… {seconds} सेकंद | facts: `seconds`; shown after 2 seconds of waiting |
| `ask.suggest.title` | You can ask | आप पूछ सकते हैं | आपण विचारू शकता | heading of the suggestion chips in the empty state |
| `ask.suggest.why` | Why did I get this amount? | मुझे इतने पैसे क्यों मिले? | मला ही रक्कम का मिळाली? | the first example of the BUILT FALLBACK_HELP; answered from the decision facts; only when a decision exists |
| `ask.suggest.bigger` | My loss was bigger | मेरा नुकसान ज़्यादा हुआ | माझे नुकसान जास्त झाले | the second example of the BUILT FALLBACK_HELP; tapping it sends the text and, as today, opens a DISPUTE case; hidden when the merchant has no paid decision |
| `ask.suggest.covered` | What is covered? | क्या कवर है? | काय कवर आहे? | answered from clauses C2 and C3 |
| `ask.suggest.starts` | When does my cover start? | मेरा कवर कब शुरू होता है? | माझे कवर केव्हा सुरू होते? | answered from clause C5 and the merchant's cover record |
| `ask.suggest.waiting` | What is the waiting period? | वेटिंग पीरियड क्या है? | वेटिंग पीरियड म्हणजे काय? | answered from clause C5 |
| `ask.suggest.question` | How do I question a payout? | भुगतान पर सवाल कैसे उठाऊँ? | रकमेवर प्रश्न कसा विचारू? | answered from clause C9 |
| `ask.suggest.instalment` | What happens to my loan instalment? | मेरी लोन किस्त का क्या होता है? | माझ्या कर्जाच्या हप्त्याचे काय होते? | answered from clause C10; only when the merchant has a loan |
| `ask.cites.policy` | From the policy: {clauses} | पॉलिसी से: {clauses} | पॉलिसीमधून: {clauses} | facts: `clauses`; clause chips, section 5.3 |
| `ask.based_on` | Based on | इस आधार पर | याच्या आधारे | heading of the facts used, shown with source chips (section 5.1) |
| `ask.details` | Details | ब्योरा | तपशील | opens the details of the answer label |
| `ask.details.provider` | Answered by | जवाब किसने दिया | उत्तर कोणी दिले | value: provider name as it is, for example rules, sarvam or template |
| `ask.details.model` | Model | मॉडल | मॉडेल | value: the model id echoed at run time; empty for rules and templates |
| `ask.details.time` | Time | समय | वेळ | value: the time of the answer |
| `ask.details.reason` | Why a backup was used | बैकअप क्यों इस्तेमाल हुआ | बॅकअप का वापरले गेले | value: one of the fb.reason lines; only on FALLBACK and SIMULATED answers |

### 9.2 Fixed lines

These keys are the ones of the Ask Chhatri spec (section 13.2) with Hindi and Marathi added. ASK_SCAM_WARNING has one clause more than the spec, so that a remote-access message is covered too.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `ASK_HANDOFF` | I don't have an answer to this question. You can ask our team. | इस सवाल का जवाब मेरे पास नहीं है। आप हमारी टीम से पूछ सकते हैं। | या प्रश्नाचे उत्तर माझ्याकडे नाही. आपण आमच्या टीमला विचारू शकता. | the model declined (can_answer is false) or the question is out of scope; the next action is TALK_TO_TEAM |
| `ASK_SCAM_WARNING` | Careful: Chhatri does not ask for your OTP, PIN or password in a chat or on a call, and charges no fee to pay a claim. If a message asks for these, or asks you to install an app, do not reply. | सावधान: छतरी चैट या फ़ोन पर आपसे OTP, PIN या पासवर्ड नहीं माँगती, और दावे का पैसा देने के लिए कोई फ़ीस नहीं लेती। ऐसा संदेश आए, या कोई ऐप इंस्टॉल करने को कहे, तो जवाब न दें। | सावध राहा: छत्री चॅटवर किंवा फोनवर आपल्याकडे OTP, PIN किंवा पासवर्ड मागत नाही, आणि दाव्याची रक्कम देण्यासाठी कोणतीही फी घेत नाही. असा संदेश आला, किंवा एखादे ॲप इन्स्टॉल करायला सांगितले, तर उत्तर देऊ नका. | starts the answer when the scam check fires; the Ask Chhatri spec has the first two sentences, and this row adds the app clause so that a remote-access message is covered too |
| `ASK_MENTION_CHIP` | {value} — is that right? | {value} — सही है? | {value} — बरोबर आहे का? | facts: `value`; one chip for each amount or date found in a voice question (H18); value is formatted like ₹1,500 or 19 August |
| `ASK_MENTION_WORDS` | You said "{heard}". Please type the number. | आपने कहा: "{heard}"। कृपया संख्या लिखकर बताइए। | आपण म्हणालात: "{heard}". कृपया संख्या टाइप करून सांगा. | facts: `heard`; words that the number parser cannot turn into a value; the server never guesses |
| `ASK_TOO_LONG` | Please keep the question shorter. | सवाल थोड़ा छोटा रखिए। | प्रश्न थोडा लहान ठेवा. | over 500 characters |
| `ASK_VOICE_NOTICE` | Your voice may be sent to a speech service (Sarvam or your browser) to be turned into text. Please use the sample sentences. | आपकी आवाज़ को लिखने के लिए किसी स्पीच सेवा (Sarvam या आपका ब्राउज़र) को भेजा जा सकता है। कृपया नमूना वाक्य बोलिए। | आपला आवाज मजकुरात बदलण्यासाठी एखाद्या स्पीच सेवेकडे (Sarvam किंवा आपला ब्राउझर) पाठवला जाऊ शकतो. कृपया नमुना वाक्ये वापरा. | first recording; a demo courtesy, not a consent flow; the consent centre is the pilot answer |
| `ASK_OFFLINE` | There is a connection problem. Please try again in a little while. | कनेक्शन में दिक्कत है। थोड़ी देर बाद फिर कोशिश कीजिए। | कनेक्शनमध्ये अडचण आहे. थोड्या वेळाने पुन्हा प्रयत्न करा. | the app cannot reach the backend; the typed text is kept and a retry button shows |

## 10. Scam warning (H19, wave 2)

The scam check is a word and link check, not a model, so it works with no key. A message is flagged when it has one strong signal (a request for an OTP, PIN, CVV or password, a remote-access tool such as AnyDesk or TeamViewer, or a fee together with a send or pay verb) or two weak signals (a guarantee or a prize, urgency, a short link or an apk file, a request to call a number). The signal lists are in [fs-05](../02-product/feature-specs/fs-05-ask-chhatri.md) section 8 and in conversation design section 10.5. A flagged message gets a banner above the normal answer: scam.title, ASK_SCAM_WARNING, scam.do and scam.note. If the rules also recognise a known question, that answer follows the banner. If they do not, the banner is the whole answer and no model is called. The next action is ASK_AGAIN.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `scam.title` | Be careful. This looks like a scam. | सावधान। यह धोखाधड़ी जैसा लग रहा है। | सावध राहा. हा फसवणुकीचा प्रकार वाटतो. | heading of the banner above the answer |
| `scam.do` | Do not tap its link. Chhatri sends a payment link when you ask to buy cover, not before. | उसके लिंक पर टैप न करें। छतरी भुगतान लिंक तब भेजती है जब आप कवर खरीदने को कहते हैं, उससे पहले नहीं। | त्यातील लिंकवर टॅप करू नका. छत्री पेमेंट लिंक तेव्हा पाठवते जेव्हा आपण कवर खरेदी करायला सांगता, त्याआधी नाही. | the BUILT COVER_LINK is the one link Chhatri sends, and only after BUY_COVER |
| `scam.report` | You can report it to the national cyber crime helpline ({cyber_helpline}) or at {cyber_portal}. | आप इसकी शिकायत राष्ट्रीय साइबर अपराध हेल्पलाइन ({cyber_helpline}) पर या {cyber_portal} पर कर सकते हैं। | आपण याची तक्रार राष्ट्रीय सायबर गुन्हे हेल्पलाइनवर ({cyber_helpline}) किंवा {cyber_portal} येथे करू शकता. | facts: `cyber_helpline`, `cyber_portal`; hidden until the helpline number and the portal address are set in configuration and checked against the official source; they are not written into the string |
| `scam.note` | This is a quick check of the words in the message. It can be wrong. If you are unsure, do not act on it. | यह संदेश के शब्दों की एक त्वरित जाँच है। यह ग़लत भी हो सकती है। शक हो, तो उस पर कुछ न करें। | ही संदेशातील शब्दांची झटपट तपासणी आहे. ती चुकीची असू शकते. खात्री नसेल तर त्यावर काहीही करू नका. | shown under the banner so that a miss is not read as a clearance |

## 11. Voice (N4, H18, wave 2)

### 11.1 States

Six states: idle, listening (the spec calls it recording), processing (transcribing), speaking, error and fallback (not available). The first recording also shows ASK_VOICE_NOTICE, and a transcript with an amount or a date goes through the confirm step of 11.2. The recorder stops itself at the built 30 second limit (`MAX_RECORD_SECONDS`), and the API rejects audio over 5 MB or 30 seconds. Browser speech recognition is not built; the browser voice is used for speaking only. Conversation design section 7.4 draws the states.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `voice.btn.speak` | Speak | बोलिए | बोला | mic button label; tap to start and tap to stop, as the BUILT recorder does; the BUILT aria labels are English only: Record a voice note, Stop and send voice note |
| `voice.btn.stop` | Stop | रोकें | थांबवा | mic button label while listening |
| `voice.btn.listen` | Listen | सुनें | ऐका | button on an answer; plays it with Sarvam voice or the browser voice; the answer text is always shown |
| `voice.state.idle` | Tap the mic and speak. | माइक दबाकर बोलिए। | माइक दाबा आणि बोला. | state idle |
| `voice.state.listening` | Listening… {seconds} of {max_seconds} seconds. Tap to stop. | सुन रहे हैं… {max_seconds} में से {seconds} सेकंड। रोकने के लिए टैप करें। | ऐकत आहे… {max_seconds} पैकी {seconds} सेकंद. थांबवण्यासाठी टॅप करा. | facts: `seconds`, `max_seconds`; state listening (the spec calls it recording); max_seconds is the BUILT recording limit; the BUILT line reads Recording 0:12 / 0:30 |
| `voice.state.processing` | Understanding what you said… | आपकी बात समझी जा रही है… | आपले बोलणे समजून घेतले जात आहे… | state processing (the spec calls it transcribing); a Cancel button shows |
| `voice.state.speaking` | Playing the answer. Tap to stop. | जवाब सुनाया जा रहा है। रोकने के लिए टैप करें। | उत्तर ऐकवले जात आहे. थांबवण्यासाठी टॅप करा. | state speaking (text to speech or the browser voice) |
| `voice.err.denied` | Microphone permission denied or unavailable | माइक की अनुमति नहीं मिली या माइक उपलब्ध नहीं है | माइकची परवानगी मिळाली नाही किंवा माइक उपलब्ध नाही | BUILT; state error; the English line is the BUILT recorder message, the other two are new |
| `voice.err.unsupported` | This browser cannot record audio | यह ब्राउज़र आवाज़ रिकॉर्ड नहीं कर सकता | हा ब्राउझर आवाज रेकॉर्ड करू शकत नाही | BUILT; state error; the English line is the BUILT recorder message, the other two are new |
| `voice.err.fix` | Allow the microphone in your browser settings, or type your message instead. | ब्राउज़र की सेटिंग में माइक की अनुमति दें, या अपना संदेश लिखकर भेजें। | ब्राउझरच्या सेटिंगमध्ये माइकला परवानगी द्या, किंवा आपला संदेश टाइप करून पाठवा. | shown under voice.err.denied; a next step, so the screen is not a dead end; the spec hides the mic and keeps the text box |
| `voice.err.too_long` | That was longer than {max_seconds} seconds. Please say it again, shorter. | यह {max_seconds} सेकंड से लंबा था। कृपया छोटा करके फिर से बोलिए। | हे {max_seconds} सेकंदांपेक्षा मोठे होते. कृपया लहान करून पुन्हा बोला. | facts: `max_seconds`; state error; the BUILT recorder stops at the limit and the API rejects longer audio |
| `voice.state.fallback` | Voice is not available right now. You can type, or tap one of the ready questions. | अभी आवाज़ की सुविधा उपलब्ध नहीं है। आप लिख सकते हैं, या तैयार सवालों में से किसी पर टैप कर सकते हैं। | सध्या आवाजाची सुविधा उपलब्ध नाही. आपण टाइप करू शकता, किंवा तयार प्रश्नांपैकी एकावर टॅप करू शकता. | state fallback (the spec calls it not available); shown with the FALLBACK token and the reason line from section 15.5; the mic is hidden and the text box stays |
| `voice.sim.note` | SIMULATED voice. The words come from the ready-made voice notes. | SIMULATED आवाज़। शब्द तैयार वॉइस नोट से आते हैं। | SIMULATED आवाज. शब्द तयार व्हॉइस नोटमधून येतात. | shown while speech to text is simulated (no key, or the demo chips) |

### 11.2 Confirmation chips for amounts and dates (H18)

The transcript fills an editable text box, and voice never sends on its own. For each amount and each date in the final text the app shows one chip, ASK_MENTION_CHIP, for example ₹1,500 — is that right?, with the buttons Right and Change. Send stays disabled until every chip is confirmed, and the server refuses an unconfirmed voice question with 409. The Hindi word कल means both yesterday and tomorrow, so that chip asks which one, and the server never guesses. Words that the parser cannot turn into a value are not guessed either: the merchant is asked to type the number (ASK_MENTION_WORDS). H18 applies to the mini-app Ask screen. A WhatsApp voice note is answered at once, as today, and an amount heard in it changes nothing.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `voice.transcript.label` | What we heard. You can change it. | हमने यह सुना। आप इसे बदल सकते हैं। | आम्ही हे ऐकले. आपण ते बदलू शकता. | label of the editable text box that the transcript fills; voice never sends on its own |
| `voice.confirm.intro` | Check each amount and date. Then send. | हर रकम और तारीख़ देखिए। फिर भेजिए। | प्रत्येक रक्कम आणि तारीख पहा. मग पाठवा. | shown above the chips when the final text holds at least one amount or date |
| `voice.chip.right` | Right | सही है | बरोबर | button on a chip; confirms that one value |
| `voice.chip.change` | Change | बदलें | बदला | button on a chip; puts the cursor in the text box so the merchant can edit the words |
| `voice.chip.confirmed` | Confirmed | पुष्टि हो गई | पुष्टी झाली | state of a chip after the merchant taps Right |
| `voice.chip.kal.ask` | Did you mean yesterday or tomorrow? | आपका मतलब बीता हुआ कल था या आने वाला कल? | आपल्याला काल म्हणायचे होते की उद्या? | the Hindi word कल means both, so the chip asks; the server never guesses |
| `voice.chip.kal.yesterday` | Yesterday | बीता हुआ कल | काल | option of the कल chip |
| `voice.chip.kal.tomorrow` | Tomorrow | आने वाला कल | उद्या | option of the कल chip |
| `voice.send.hint` | Confirm each amount and date to send. | भेजने के लिए हर रकम और तारीख़ की पुष्टि करें। | पाठवण्यासाठी प्रत्येक रक्कम आणि तारखेची पुष्टी करा. | hint beside the disabled Send button; the server refuses an unconfirmed voice question with 409 mentions_unconfirmed |
| `voice.confirm.rule` | An amount or a date is used only after you confirm it. | कोई रकम या तारीख़ तभी इस्तेमाल होती है जब आप उसकी पुष्टि कर दें। | कोणतीही रक्कम किंवा तारीख आपण पुष्टी केल्यानंतरच वापरली जाते. | shown once under the first chips |

## 12. Slip pre-check (N3, H15, H16, wave 2)

The photo is read and the merchant confirms what was read before any check runs. Keys and wording follow the hospital cash spec ([fs-02](../02-product/feature-specs/fs-02-hospital-cash-claim.md) section 9.2), with the Marathi added. The sheet shows no confidence number and no percentage. Text on the slip is data, never an instruction, and no field can be edited here, so a name or a date cannot be changed. The photo is never judged by the model: the policy engine decides, as it does today.

### 12.1 Sheet, fields, checklist and buttons

The sheet shows the title, the help line, the notice on first use, the fields that were read, three checklist lines (each Passed or Not clear), the question and the buttons.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `SLIP_SHEET_TITLE` | Send your hospital slip | अस्पताल की पर्ची भेजें | रुग्णालयाची पर्ची पाठवा | sheet title |
| `SLIP_SHEET_HELP` | Take one photo of the admission slip, the discharge paper or the bill. Use good light and keep the whole page in view. | भर्ती की पर्ची, छुट्टी का काग़ज़ या बिल की एक फ़ोटो लीजिए। रोशनी में, पूरा पन्ना दिखे। | भरतीची पर्ची, डिस्चार्जचा कागद किंवा बिल यांचा एक फोटो घ्या. चांगल्या प्रकाशात घ्या आणि संपूर्ण पान दिसू द्या. | sheet |
| `SLIP_NOTICE` | The photo may be sent to an AI reading service (Gemini or Sarvam) to be read. Please send a sample slip, not a real one. | पर्ची की फ़ोटो पढ़ने के लिए किसी AI सेवा (Gemini या Sarvam) को भेजी जा सकती है। कृपया नमूना पर्ची भेजिए, असली नहीं। | पर्चीचा फोटो वाचण्यासाठी एखाद्या AI सेवेकडे (Gemini किंवा Sarvam) पाठवला जाऊ शकतो. कृपया नमुना पर्ची पाठवा, खरी नाही. | first upload; names the services the photo can go to when a key is set. With no key the read is SIMULATED |
| `SLIP_READING` | Reading your slip… | पर्ची पढ़ी जा रही है… | पर्ची वाचली जात आहे… | while waiting |
| `SLIP_PRECHECK_SHOW` | We have read your slip. Please check it. Is this right? | पर्ची पढ़ ली गई है। कृपया देख लीजिए, क्या यह सही है? | आम्ही आपली पर्ची वाचली आहे. कृपया पाहा, हे बरोबर आहे का? | READY |
| `SLIP_FIELD_NAME` | Patient | मरीज़ का नाम | रुग्णाचे नाव | field label |
| `SLIP_FIELD_ADMITTED` | Admitted | भर्ती की तारीख़ | भरतीची तारीख | field label |
| `SLIP_FIELD_DISCHARGED` | Discharged | छुट्टी की तारीख़ | डिस्चार्जची तारीख | field label |
| `SLIP_FIELD_HOSPITAL` | Hospital | अस्पताल | रुग्णालय | field label |
| `SLIP_FIELD_NOT_ON_SLIP` | Not on the slip | पर्ची पर नहीं है | पर्चीवर नाही | empty optional slot |
| `SLIP_NOTE_NO_DISCHARGE` | There is no discharge date on the slip. If you are still in hospital, that is normal. | छुट्टी की तारीख़ पर्ची पर नहीं है। अगर आप अभी अस्पताल में हैं, तो यह सामान्य है। | पर्चीवर डिस्चार्जची तारीख नाही. आपण अजून रुग्णालयात असाल, तर हे सामान्य आहे. | discharge empty |
| `SLIP_NOTE_NAME_NOT_LATIN` | The name is not in English letters, so our team will look at it. | नाम अंग्रेज़ी अक्षरों में नहीं है, इसलिए हमारी टीम इसे देखेगी। | नाव इंग्रजी अक्षरांत नाही, म्हणून आमची टीम ते पाहील. | non-Latin name |
| `SLIP_CHECK_READABLE_PASS` | The photo could be read | फ़ोटो साफ़ पढ़ी जा सकी | फोटो स्पष्ट वाचता आला | checklist |
| `SLIP_CHECK_READABLE_WARN` | The photo is not clear | फ़ोटो साफ़ नहीं है | फोटो स्पष्ट नाही | checklist |
| `SLIP_CHECK_NAME_PASS` | The name is on the slip | नाम पर्ची पर दिख रहा है | नाव पर्चीवर दिसत आहे | checklist |
| `SLIP_CHECK_NAME_WARN` | The name is not clear | नाम साफ़ नहीं दिख रहा | नाव स्पष्ट दिसत नाही | checklist |
| `SLIP_CHECK_DATES_PASS` | The admission date is on the slip | भर्ती की तारीख़ पर्ची पर दिख रही है | भरतीची तारीख पर्चीवर दिसत आहे | checklist |
| `SLIP_CHECK_DATES_WARN` | The admission date is not clear | भर्ती की तारीख़ साफ़ नहीं दिख रही | भरतीची तारीख स्पष्ट दिसत नाही | checklist |
| `SLIP_ACTION_CONFIRM` | Yes, this is right | हाँ, सही है | होय, बरोबर आहे | button |
| `SLIP_ACTION_RETAKE` | Send another photo | दूसरी फ़ोटो भेजें | दुसरा फोटो पाठवा | button |
| `SLIP_ACTION_TEAM` | Send to our team | हमारी टीम को भेजें | आमच्या टीमकडे पाठवा | button |

### 12.2 Retake guidance, hand-off and upload errors

One line for each reason that the pre-check can stop on. The first reason that applies wins ([fs-02](../02-product/feature-specs/fs-02-hospital-cash-claim.md) section 7.3.5). The merchant is never told that a read was flagged for odd text: that case shows the same line as a failed read.

| Reason | Line |
|---|---|
| The reader failed or timed out, or the text was flagged | SLIP_NO_READ |
| Not a hospital document | SLIP_RETAKE_DOCUMENT |
| Nothing readable, or confidence below the minimum | SLIP_RETAKE_CLEAR |
| The patient's name is missing | SLIP_RETAKE_NAME |
| The admission date is missing or does not make sense | SLIP_RETAKE_DATE |
| Three photos have been sent | SLIP_PHOTO_LIMIT |

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `SLIP_RETAKE_DOCUMENT` | This does not look like a hospital document. Please send a photo of the admission slip, the discharge paper or the bill. | यह अस्पताल की पर्ची नहीं लग रही। कृपया भर्ती की पर्ची, छुट्टी का काग़ज़ या बिल की फ़ोटो भेजिए। | हे रुग्णालयाचे कागदपत्र वाटत नाही. कृपया भरतीची पर्ची, डिस्चार्जचा कागद किंवा बिल यांचा फोटो पाठवा. | reason 3 |
| `SLIP_RETAKE_CLEAR` | The photo is not clear. Please take it in good light, with the slip flat and fully in view. | फ़ोटो साफ़ नहीं है। रोशनी में, पर्ची सीधी रखकर, पूरी पर्ची की फ़ोटो भेजिए। | फोटो स्पष्ट नाही. कृपया चांगल्या प्रकाशात, पर्ची सरळ ठेवून, संपूर्ण पर्ची दिसेल असा फोटो घ्या. | reasons 4 and 7 |
| `SLIP_RETAKE_NAME` | The patient's name is not clear. Please send a photo where the whole name is in view. | मरीज़ का नाम साफ़ नहीं दिख रहा। नाम वाला हिस्सा पूरा दिखे, ऐसी फ़ोटो भेजिए। | रुग्णाचे नाव स्पष्ट दिसत नाही. संपूर्ण नाव दिसेल असा फोटो पाठवा. | reason 5 |
| `SLIP_RETAKE_DATE` | The admission date is not clear. Please send a photo where the whole date is in view. | भर्ती की तारीख़ साफ़ नहीं दिख रही। तारीख़ वाला हिस्सा पूरा दिखे, ऐसी फ़ोटो भेजिए। | भरतीची तारीख स्पष्ट दिसत नाही. संपूर्ण तारीख दिसेल असा फोटो पाठवा. | reason 6 |
| `SLIP_NO_READ` | We could not read the slip just now. You can send it to our team, who will look at it. | अभी पर्ची पढ़ी नहीं जा सकी। आप इसे हमारी टीम को भेज सकते हैं, वे इसे देखेंगे। | आत्ता पर्ची वाचता आली नाही. आपण ती आमच्या टीमकडे पाठवू शकता. टीम ती पाहील. | reasons 1 and 2 |
| `SLIP_PHOTO_LIMIT` | You have already sent several photos. Please send this one to our team now. | आप पहले भी फ़ोटो भेज चुके हैं। अब इसे हमारी टीम को भेज दीजिए। | आपण यापूर्वीही अनेक फोटो पाठवले आहेत. आता हा आमच्या टीमकडे पाठवा. | photos used up |
| `slip.err.too_big` | The photo is too big. The limit is {max_mb} MB. | फ़ोटो बहुत बड़ी है। सीमा {max_mb} MB है। | फोटो खूप मोठा आहे. मर्यादा {max_mb} MB आहे. | facts: `max_mb`; the app checks the size before upload; max_mb is the BUILT limit for images |
| `slip.err.bad_type` | Please send a JPG, PNG or WebP photo. | कृपया JPG, PNG या WebP फ़ोटो भेजिए। | कृपया JPG, PNG किंवा WebP फोटो पाठवा. | the BUILT file picker accepts image/jpeg, image/png and image/webp |
| `slip.err.damaged` | This photo cannot be opened. Please choose another one. | यह फ़ोटो खुल नहीं सकी। कृपया दूसरी फ़ोटो चुनिए। | हा फोटो उघडता आला नाही. कृपया दुसरा फोटो निवडा. | the file is damaged or is not an image; no retake is used |
| `slip.working` | Checking your claim… | आपका दावा जाँचा जा रहा है… | आपला दावा तपासला जात आहे… | the Deciding state after the merchant confirms; the result comes from the policy engine and the BUILT replies |

## 13. Grievance ladder and respondent router (N5, H22, wave 3)

The first step is built: a DISPUTE case with a 24 hour clock. The other steps are outside Chhatri and are shown so that the merchant knows where to go. Step ids, topics, clocks and the wording of each state follow [fs-06](../02-product/feature-specs/fs-06-explanations-disputes-and-grievance.md) sections 5 to 8. A clock is shown only where a source exists: our own answer time, and the days that the Bima Bharosa portal states. Every other time reads as to be confirmed.

### 13.1 Ladder: steps, states and clocks

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `grv.title` | Complaints and escalation | शिकायत और आगे के कदम | तक्रार आणि पुढचे टप्पे | Help screen row and heading; hidden until N5 is switched on |
| `grv.intro` | If you are not happy with an answer, you can take a complaint up one step at a time. Each step shows its reply time, or says that it is not confirmed yet. | अगर आप किसी जवाब से संतुष्ट नहीं हैं, तो शिकायत को एक-एक कदम ऊपर ले जा सकते हैं। हर कदम के साथ जवाब का समय दिखता है, या यह कि वह अभी तय नहीं है। | एखाद्या उत्तराने समाधान न झाल्यास आपण तक्रार एकेक टप्पा पुढे नेऊ शकता. प्रत्येक टप्प्यासोबत उत्तराची वेळ दिसते, किंवा ती अजून निश्चित नाही असे दिसते. | first lines of the screen |
| `grv.step.PAYTM_DISPUTE` | Our claims officer | हमारा क्लेम अधिकारी | आमचा क्लेम अधिकारी | step PAYTM_DISPUTE; BUILT as the DISPUTE case with a 24 hour clock |
| `grv.step.INSURER_GRO` | The insurer's grievance officer | बीमा कंपनी का शिकायत अधिकारी | विमा कंपनीचा तक्रार अधिकारी | step INSURER_GRO; outside Chhatri; PLANNED (N5) |
| `grv.step.BIMA_BHAROSA` | IRDAI Bima Bharosa portal | IRDAI का बीमा भरोसा पोर्टल | IRDAI चे बीमा भरोसा पोर्टल | step BIMA_BHAROSA; the merchant files it; PLANNED (N5) |
| `grv.step.OMBUDSMAN` | Insurance Ombudsman | बीमा लोकपाल | विमा लोकपाल | step OMBUDSMAN; the merchant files it; PLANNED (N5) |
| `grv.step.LENDER_GRIEVANCE` | The lender's grievance officer | लेंडर का शिकायत अधिकारी | लेंडरचा तक्रार अधिकारी | step LENDER_GRIEVANCE; the ladder of an instalment complaint |
| `grv.step.PAYTM_SUPPORT` | Paytm support | Paytm सपोर्ट | Paytm सपोर्ट | step PAYTM_SUPPORT; the ladder of a payment, app or data complaint |
| `grv.what.PAYTM_DISPUTE` | A person in Chhatri's team looks at the numbers again. | छतरी की टीम का एक व्यक्ति आँकड़े दोबारा देखता है। | छत्रीच्या टीममधील एक व्यक्ती आकडे पुन्हा पाहते. | one line under the step name |
| `grv.what.INSURER_GRO` | The insurer's officer for complaints looks at it. | बीमा कंपनी का शिकायतों का अधिकारी इसे देखता है। | विमा कंपनीचा तक्रारींसाठीचा अधिकारी हे पाहतो. | one line under the step name |
| `grv.what.BIMA_BHAROSA` | IRDAI, the insurance regulator, runs an online portal for complaints. | बीमा नियामक IRDAI शिकायतों के लिए एक ऑनलाइन पोर्टल चलाता है। | विमा नियामक IRDAI तक्रारींसाठी एक ऑनलाइन पोर्टल चालवतो. | one line under the step name |
| `grv.what.OMBUDSMAN` | An official set up under the Insurance Ombudsman Rules to settle insurance complaints. It is free for you. | बीमा लोकपाल नियमों के तहत बना एक अधिकारी, जो बीमा की शिकायतें सुलझाता है। यह आपके लिए मुफ़्त है। | विमा लोकपाल नियमांखाली नेमलेला एक अधिकारी, जो विम्याच्या तक्रारी सोडवतो. हे आपल्यासाठी मोफत आहे. | one line under the step name; free to the policyholder |
| `grv.what.LENDER_GRIEVANCE` | The lender's own officer for complaints about an instalment. | लेंडर का अपना अधिकारी, जो किस्त की शिकायतें देखता है। | लेंडरचा स्वतःचा अधिकारी, जो हप्त्याच्या तक्रारी पाहतो. | one line under the step name |
| `grv.what.PAYTM_SUPPORT` | Paytm's support team for payments, the app and your data. | Paytm की सपोर्ट टीम, जो पेमेंट, ऐप और आपके डेटा के सवाल देखती है। | Paytm ची सपोर्ट टीम, जी पेमेंट, ॲप आणि आपल्या डेटाबद्दलचे प्रश्न पाहते. | one line under the step name |
| `grv.state.here` | You are here | आप यहाँ हैं | आपण येथे आहात | step state ACTIVE |
| `grv.state.next` | Next step | अगला कदम | पुढचा टप्पा | the step after the active one |
| `grv.state.done` | Done | हो गया | झाले | step state DONE |
| `grv.state.locked` | Opens after the step before | पिछले कदम के बाद खुलता है | आधीच्या टप्प्यानंतर उघडते | step state NOT_STARTED |
| `grv.when_next` | You can go to the next step if the answer does not settle it, or if the reply time has passed. | जवाब से बात न सुलझे, या जवाब का समय निकल जाए, तो आप अगले कदम पर जा सकते हैं। | उत्तराने प्रश्न सुटला नाही, किंवा उत्तराची वेळ उलटून गेली, तर आपण पुढच्या टप्प्यावर जाऊ शकता. | escalation is never blocked by Chhatri |
| `grv.outside` | Steps outside Chhatri are shown so that you know where to go. In this demo nothing is sent to them. | छतरी के बाहर के कदम इसलिए दिखाए गए हैं ताकि आपको पता रहे कि कहाँ जाना है। इस डेमो में उन्हें कुछ नहीं भेजा जाता। | छत्रीच्या बाहेरचे टप्पे आपल्याला कुठे जायचे ते कळावे म्हणून दाखवले आहेत. या डेमोमध्ये त्यांना काहीही पाठवले जात नाही. | an honest note: delivery is SIMULATED or SELF_REPORTED for every step outside Chhatri |
| `grv.case` | Case {case_id} | केस {case_id} | केस {case_id} | facts: `case_id`; case id such as C-2291 |
| `grv.contact.placeholder` | Contact details come from the partner. This is a placeholder in the demo. | संपर्क का ब्योरा साझेदार से आएगा। डेमो में यह सिर्फ़ एक नमूना है। | संपर्काचा तपशील भागीदाराकडून येईल. डेमोमध्ये हा फक्त एक नमुना आहे. | contact details of the insurer, lender and Paytm are not invented; the real ones come from the partners at pilot time |
| `grv.bring` | Keep these ready: decision {decision_id} and case {case_id}. | ये तैयार रखें: फ़ैसला {decision_id} और केस {case_id}। | हे तयार ठेवा: निर्णय {decision_id} आणि केस {case_id}. | facts: `decision_id`, `case_id`; shown on the Bima Bharosa step with the portal address from the regulatory document |
| `grv.filed.label` | The date you filed | आपने किस तारीख़ को शिकायत की | आपण कोणत्या तारखेला तक्रार केली | asked when the merchant says they filed with the portal or the Ombudsman; Chhatri cannot file for them |
| `grv.delivery.SELF_REPORTED` | You file this yourself and tell us the date. | यह शिकायत आप ख़ुद करते हैं और हमें तारीख़ बताते हैं। | ही तक्रार आपण स्वतः करता आणि आम्हाला तारीख सांगता. | delivery SELF_REPORTED: the Bima Bharosa and Ombudsman steps |
| `grv.delivery.SIMULATED` | SIMULATED in this demo. Nothing is sent. | इस डेमो में SIMULATED। कुछ भेजा नहीं जाता। | या डेमोमध्ये SIMULATED. काहीही पाठवले जात नाही. | delivery SIMULATED: the insurer, lender and Paytm desks |
| `grv.clock.own` | We reply within {sla_hours} hours. | हम {sla_hours} घंटे में जवाब देते हैं। | आम्ही {sla_hours} तासांत उत्तर देतो. | facts: `sla_hours`; clock OWN_SLA; the live countdown is tracker.clock.left |
| `grv.clock.confirm.insurer` | Response time to be confirmed with the insurer. | जवाब का समय बीमा कंपनी से पूछकर तय होगा। | उत्तराची वेळ विमा कंपनीशी बोलून निश्चित होईल. | clock TO_CONFIRM: no number is shown until a source exists |
| `grv.clock.confirm.lender` | Response time to be confirmed with the lender. | जवाब का समय लेंडर से पूछकर तय होगा। | उत्तराची वेळ लेंडरशी बोलून निश्चित होईल. | clock TO_CONFIRM |
| `grv.clock.confirm.paytm` | Response time to be confirmed. | जवाब का समय अभी तय नहीं है। | उत्तराची वेळ अजून निश्चित नाही. | clock TO_CONFIRM |
| `grv.clock.portal` | The portal says complaints are attended within {days} days. | पोर्टल के अनुसार शिकायतों पर {days} दिन के अंदर ध्यान दिया जाता है। | पोर्टलनुसार तक्रारींवर {days} दिवसांच्या आत लक्ष दिले जाते. | facts: `days`; clock PORTAL_STATED; days is what the portal states and comes from configuration; check it again before use |
| `grv.state.PAYTM_DISPUTE.running` | Our claims officer is looking at this. Answer due in {time_left}. | हमारे क्लेम अधिकारी इसे देख रहे हैं। जवाब {time_left} में आना है। | आमचे क्लेम अधिकारी हे पाहत आहेत. उत्तर {time_left} मध्ये यायचे आहे. | facts: `time_left`; step PAYTM_DISPUTE, clock running; no next step is offered until the case is answered or overdue |
| `grv.state.PAYTM_DISPUTE.answered` | Answered: the decision stands. You can read the numbers again in your receipt. | जवाब दिया गया: फ़ैसला वही रहेगा। आप अपनी रसीद में आँकड़े फिर से देख सकते हैं। | उत्तर दिले: निर्णय तोच राहील. आपण आपल्या पावतीत आकडे पुन्हा पाहू शकता. | step PAYTM_DISPUTE after the officer closed the case; a dispute never changes the amount |
| `grv.state.PAYTM_DISPUTE.overdue` | This is past our {sla_hours}-hour answer time. | यह हमारे {sla_hours} घंटे के जवाब के समय से आगे निकल गया है। | हे आमच्या {sla_hours} तासांच्या उत्तराच्या वेळेपेक्षा पुढे गेले आहे. | facts: `sla_hours`; step PAYTM_DISPUTE, still open after the clock |
| `grv.state.INSURER_GRO.active` | Sent to the insurer's grievance officer (SIMULATED in this demo). Response time to be confirmed with the insurer. | बीमा कंपनी के शिकायत अधिकारी को भेजा गया (इस डेमो में SIMULATED)। जवाब का समय बीमा कंपनी से पूछकर तय होगा। | विमा कंपनीच्या तक्रार अधिकाऱ्याला पाठवले (या डेमोमध्ये SIMULATED). उत्तराची वेळ विमा कंपनीशी बोलून निश्चित होईल. | step INSURER_GRO active |
| `grv.state.BIMA_BHAROSA.active` | You filed on {date}. The portal says complaints are attended within {days} days. Day {n} of {days}. | आपने {date} को शिकायत की। पोर्टल के अनुसार शिकायतों पर {days} दिन के अंदर ध्यान दिया जाता है। {days} में से दिन {n}। | आपण {date} रोजी तक्रार केली. पोर्टलनुसार तक्रारींवर {days} दिवसांच्या आत लक्ष दिले जाते. {days} पैकी दिवस {n}. | facts: `date`, `days`, `n`; step BIMA_BHAROSA active; the count starts from the date the merchant says they filed |
| `grv.state.BIMA_BHAROSA.past` | The portal's stated {days} days have passed. | पोर्टल के बताए {days} दिन बीत चुके हैं। | पोर्टलने सांगितलेले {days} दिवस उलटून गेले आहेत. | facts: `days`; step BIMA_BHAROSA past the stated days; never says that the portal is late |
| `grv.state.OMBUDSMAN.active` | The Insurance Ombudsman service is free. No response time is stated. | बीमा लोकपाल की सेवा मुफ़्त है। जवाब का कोई समय नहीं बताया गया है। | विमा लोकपालांची सेवा मोफत आहे. उत्तराची कोणतीही वेळ सांगितलेली नाही. | step OMBUDSMAN active |
| `grv.state.LENDER_GRIEVANCE.active` | This is the lender's decision. Your request and the lender's answer are in your receipt. Response time to be confirmed with the lender. | यह लेंडर का फ़ैसला है। आपका अनुरोध और लेंडर का जवाब आपकी रसीद में हैं। जवाब का समय लेंडर से पूछकर तय होगा। | हा लेंडरचा निर्णय आहे. आपली विनंती आणि लेंडरचे उत्तर आपल्या पावतीत आहेत. उत्तराची वेळ लेंडरशी बोलून निश्चित होईल. | step LENDER_GRIEVANCE active |
| `grv.state.PAYTM_SUPPORT.active` | With Paytm support. Response time to be confirmed. | Paytm सपोर्ट के पास है। जवाब का समय अभी तय नहीं है। | Paytm सपोर्टकडे आहे. उत्तराची वेळ अजून निश्चित नाही. | step PAYTM_SUPPORT active |
| `grv.btn.to_gro` | Send this to the insurer's grievance officer | इसे बीमा कंपनी के शिकायत अधिकारी को भेजें | हे विमा कंपनीच्या तक्रार अधिकाऱ्याला पाठवा | after PAYTM_DISPUTE is answered or overdue |
| `grv.btn.to_bharosa` | Complain on the Bima Bharosa portal | बीमा भरोसा पोर्टल पर शिकायत करें | बीमा भरोसा पोर्टलवर तक्रार करा | after INSURER_GRO |
| `grv.btn.to_ombudsman` | Approach the Insurance Ombudsman | बीमा लोकपाल के पास जाएँ | विमा लोकपालांकडे जा | after BIMA_BHAROSA |
| `grv.btn.resolved` | Mark as solved | सुलझा हुआ मानें | सुटले म्हणून नोंदवा | on every active step |
| `grv.btn.how` | How to file | शिकायत कैसे करें | तक्रार कशी करावी | opens the portal address and what to keep ready |

### 13.2 Respondent router and the two dispute lines

The router is a fixed table, not a model. The merchant picks a topic, and the table says who answers and which ladder applies. DISPUTE_NO_PAYOUT and DISPUTE_ALREADY_OPEN are the two proposed catalogue keys of the dispute fixes (wave 1).

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `grv.topic.title` | What is your complaint about? | आपकी शिकायत किस बारे में है? | आपली तक्रार कशाबद्दल आहे? | heading of the topic chips |
| `grv.topic.PAYOUT_AMOUNT` | The amount of a payout | भुगतान की रकम | रकमेबद्दल | topic PAYOUT_AMOUNT; respondent insurer |
| `grv.topic.CLAIM_DECLINED` | A claim that was not paid | जिस दावे का भुगतान नहीं हुआ | ज्या दाव्याची रक्कम दिली गेली नाही | topic CLAIM_DECLINED; respondent insurer |
| `grv.topic.CLAIM_SLOW` | A claim that is taking long | जिस दावे में देर हो रही है | ज्या दाव्याला उशीर होत आहे | topic CLAIM_SLOW; respondent insurer; links the open review case and opens no new case |
| `grv.topic.EDI_HOLIDAY` | My loan instalment | मेरी लोन किस्त | माझा कर्जाचा हप्ता | topic EDI_HOLIDAY; respondent lender |
| `grv.topic.PAYMENT_NOT_RECEIVED` | Money did not reach me | पैसे मुझ तक नहीं पहुँचे | पैसे मला मिळाले नाहीत | topic PAYMENT_NOT_RECEIVED; respondent Paytm |
| `grv.topic.PREMIUM_CHARGE` | A premium charge | प्रीमियम की कटौती | प्रीमियमची कपात | topic PREMIUM_CHARGE; respondent Paytm |
| `grv.topic.DATA_OR_CONSENT` | My data or my consent | मेरा डेटा या मेरी सहमति | माझा डेटा किंवा माझी संमती | topic DATA_OR_CONSENT; respondent Paytm |
| `grv.topic.APP_ISSUE` | A problem with the app | ऐप में कोई समस्या | ॲपमधील अडचण | topic APP_ISSUE; respondent Paytm |
| `grv.topic.OTHER` | Something else | कुछ और | आणखी काही | topic OTHER; respondent Paytm, for triage |
| `grv.who.INSURER` | This goes to the insurer. Our claims officer looks first. | यह बीमा कंपनी के पास जाता है। पहले हमारा क्लेम अधिकारी देखता है। | हे विमा कंपनीकडे जाते. आधी आमचा क्लेम अधिकारी पाहतो. | respondent INSURER |
| `grv.who.LENDER` | This goes to your lender. | यह आपके लेंडर के पास जाता है। | हे आपल्या लेंडरकडे जाते. | respondent LENDER |
| `grv.who.PAYTM` | This goes to Paytm support. | यह Paytm सपोर्ट के पास जाता है। | हे Paytm सपोर्टकडे जाते. | respondent PAYTM |
| `grv.text.label` | Tell us in your own words | अपने शब्दों में बताइए | आपल्या शब्दांत सांगा | free text of at most 500 characters |
| `grv.btn.submit` | Send | भेजें | पाठवा | opens the complaint |
| `grv.router.note` | This is a guide. If you are not sure, choose Something else. | यह एक मार्गदर्शक है। समझ न आए, तो कुछ और चुनें। | हे एक मार्गदर्शन आहे. खात्री नसेल तर आणखी काही निवडा. | the respondent split is a working assumption that the partners must confirm |
| `DISPUTE_NO_PAYOUT` | Our team looked at your question. No payout has been made on your account yet, so there is no amount to change. Your claim tracker shows why. | हमारी टीम ने आपका सवाल देखा। आपके खाते में अभी कोई भुगतान नहीं हुआ है, इसलिए बदलने के लिए कोई रकम नहीं है। आपके दावों के ट्रैकर में कारण दिखता है। | आमच्या टीमने आपला प्रश्न पाहिला. आपल्या खात्यावर अजून कोणतीही रक्कम दिली गेलेली नाही, म्हणून बदलण्यासाठी कोणतीही रक्कम नाही. आपल्या दाव्यांच्या ट्रॅकरमध्ये कारण दिसते. | proposed catalogue key of the dispute fixes: a dispute when the merchant has no decision to question |
| `DISPUTE_ALREADY_OPEN` | Your question is already with our team. See case {case_id}. | आपका सवाल पहले से हमारी टीम के पास है। केस {case_id} देखिए। | आपला प्रश्न आधीच आमच्या टीमकडे आहे. केस {case_id} पहा. | facts: `case_id`; proposed catalogue key of the dispute fixes: a second question while a case is open |

## 14. Notice and consent centre (N6, H23, wave 3)

Consent is for one purpose, and it can be withdrawn. There are three purposes: sales data, slip reading and the premium taken from the daily settlement. The log lists what was done with the merchant's data, for which purpose and when. A slip is erased on request; the decision on the claim stays on record, and the activity log is never edited. Keys and wording follow the cover purchase and consent spec ([fs-07](../02-product/feature-specs/fs-07-cover-purchase-and-consent.md) sections 8.3 and 9.10), with the Marathi added.

### 14.1 Notice and boxes on the buy screen

The keys without a dot prefix belong to the notice module of the backend. The notice is versioned; the boxes start unticked; the two boxes marked Needed for cover must be ticked to continue. Until this wave the buy screen shows the single line buy.consent.notice (section 2.4).

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `COVER_NOTICE` | By paying you agree that Chhatri uses your sales data to decide claims and set your premium, and takes the next day's premium from your daily settlement after this payment. You can change this in the app under Help, My data and consent. | भुगतान करके आप मानते हैं कि छतरी आपकी बिक्री के डेटा से दावे तय करेगी और प्रीमियम तय करेगी, और इस भुगतान के बाद आपके रोज़ के सेटलमेंट से अगले दिन का प्रीमियम काटेगी। आप इसे ऐप में मदद, मेरा डेटा और सहमति में बदल सकते हैं। | पैसे भरून आपण मान्य करता की छत्री आपल्या विक्रीच्या डेटावरून दावे ठरवेल आणि प्रीमियम ठरवेल, आणि या पेमेंटनंतर आपल्या रोजच्या सेटलमेंटमधून पुढच्या दिवसाचे प्रीमियम घेईल. हे आपण ॲपमध्ये मदत, माझा डेटा आणि संमती येथे बदलू शकता. | Sent after COVER_LINK when a link exists and the flag is on |
| `notice` | Before you pay: Chhatri uses your sales data to decide claims and set your premium. After the first payment, Chhatri takes the next day's premium from your daily settlement. Chhatri reads a hospital slip when you send one, for that claim alone. You can turn each of these off in the app under Help, My data and consent. This is a prototype with simulated data. | भुगतान से पहले: छतरी आपकी बिक्री के डेटा से दावे तय करती है और प्रीमियम तय करती है। पहले भुगतान के बाद छतरी आपके रोज़ के सेटलमेंट से अगले दिन का प्रीमियम काटती है। अस्पताल की पर्ची छतरी तब पढ़ती है जब आप भेजें, और सिर्फ़ उसी दावे के लिए। आप इनमें से हर एक को ऐप में मदद, मेरा डेटा और सहमति में बंद कर सकते हैं। यह एक प्रोटोटाइप है और डेटा काल्पनिक है। | पैसे भरण्यापूर्वी: छत्री आपल्या विक्रीच्या डेटावरून दावे ठरवते आणि प्रीमियम ठरवते. पहिल्या पेमेंटनंतर छत्री आपल्या रोजच्या सेटलमेंटमधून पुढच्या दिवसाचे प्रीमियम घेते. आपण रुग्णालयाची पर्ची पाठवल्यास छत्री ती वाचते, फक्त त्या दाव्यासाठी. यापैकी प्रत्येक गोष्ट आपण ॲपमध्ये मदत, माझा डेटा आणि संमती येथे बंद करू शकता. हा प्रोटोटाइप आहे आणि यातील डेटा सिम्युलेटेड आहे. | S3 notice above the checkboxes; versioned by the notice module |
| `box.sales` | I agree: Chhatri may use my sales data to decide claims and set my premium. | मैं सहमत हूँ: छतरी मेरी बिक्री का डेटा दावे तय करने और प्रीमियम तय करने में इस्तेमाल कर सकती है। | मी सहमत आहे: छत्री माझ्या विक्रीचा डेटा दावे ठरवण्यासाठी आणि प्रीमियम ठरवण्यासाठी वापरू शकते. | checkbox, unticked at the start; required for cover |
| `box.settlement` | I agree: after the first payment, Chhatri may take the next day's premium from my daily settlement. | मैं सहमत हूँ: पहले भुगतान के बाद छतरी मेरे रोज़ के सेटलमेंट से अगले दिन का प्रीमियम काट सकती है। | मी सहमत आहे: पहिल्या पेमेंटनंतर छत्री माझ्या रोजच्या सेटलमेंटमधून पुढच्या दिवसाचे प्रीमियम घेऊ शकते. | checkbox, unticked at the start; required for cover |
| `box.slip` | I agree: Chhatri may read a hospital slip when I send one. | मैं सहमत हूँ: जब मैं अस्पताल की पर्ची भेजूँ, छतरी उसे पढ़ सकती है। | मी सहमत आहे: मी रुग्णालयाची पर्ची पाठवली, तर छत्री ती वाचू शकते. | checkbox, unticked at the start; optional |
| `tag.required` | Needed for cover | कवर के लिए ज़रूरी | कवरसाठी आवश्यक | tag beside a required checkbox |
| `tag.optional` | Optional | ज़रूरी नहीं | ऐच्छिक | tag beside an optional checkbox |
| `hint` | Tick the two boxes marked Needed for cover to continue. | आगे बढ़ने के लिए “कवर के लिए ज़रूरी” वाले दोनों बॉक्स चुनें। | पुढे जाण्यासाठी “कवरसाठी आवश्यक” असे लिहिलेले दोन्ही बॉक्स निवडा. | shown while a required box is unticked |
| `error.stale` | The notice changed. Please read it again. | सूचना बदल गई है। कृपया उसे फिर से पढ़ें। | सूचना बदलली आहे. कृपया ती पुन्हा वाचा. | the notice version changed between viewing and paying |

### 14.2 Purposes

Each purpose has a label, what is used, what happens when it is turned off, and how to turn it on again. The effect texts get their numbers from the rules and the cover.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `purpose.sales.label` | Use my sales data to decide claims and set my premium | मेरी बिक्री का डेटा दावे तय करने और प्रीमियम तय करने में इस्तेमाल करें | माझा विक्रीचा डेटा दावे ठरवण्यासाठी आणि प्रीमियम ठरवण्यासाठी वापरा | sales: label of the purpose |
| `purpose.sales.data_used` | Daily and hourly sales totals from your Paytm settlement. Soundbox activity, to see whether your shop was open. | आपके Paytm सेटलमेंट से रोज़ और घंटे की बिक्री का कुल योग। Soundbox की गतिविधि, यह देखने के लिए कि दुकान खुली थी या नहीं। | आपल्या Paytm सेटलमेंटमधील रोजची आणि तासाची एकूण विक्री. दुकान उघडे होते का हे पाहण्यासाठी Soundbox ची हालचाल. | sales: what is used for this purpose |
| `purpose.sales.effect` | Your cover is cancelled today. Chhatri stops checking your sales, so no new claims are made for you, and your sales are left out of your area's index. Claims already decided stay on record. Whether anything is returned, and how much, is set by the cancellation terms (C12). To get cover again you buy again and wait {waiting_days} days. | आपका कवर आज रद्द हो जाएगा। छतरी आपकी बिक्री देखना बंद कर देगी, इसलिए आपके लिए कोई नया दावा नहीं बनेगा, और आपकी बिक्री आपके इलाके के इंडेक्स से बाहर हो जाएगी। तय हो चुके दावे रिकॉर्ड में रहेंगे। कुछ लौटाया जाए या नहीं, और कितना, यह रद्द करने की शर्तों (C12) से तय होता है। दोबारा कवर के लिए आपको फिर से खरीदना होगा और {waiting_days} दिन रुकना होगा। | आपले कवर आज रद्द होईल. छत्री आपली विक्री पाहणे बंद करेल, त्यामुळे आपल्यासाठी नवीन दावे तयार होणार नाहीत आणि आपली विक्री आपल्या परिसराच्या इंडेक्समधून वगळली जाईल. ठरलेले दावे नोंदीत राहतील. काही परत केले जाते का आणि किती, हे रद्द करण्याच्या अटींनुसार (C12) ठरते. पुन्हा कवर हवे असल्यास आपल्याला पुन्हा खरेदी करावी लागेल आणि {waiting_days} दिवस थांबावे लागेल. | facts: `waiting_days`; sales: what happens when the merchant turns it off; {waiting_days} is filled from the rules |
| `purpose.sales.regrant` | To turn this on again, buy cover again. | इसे दोबारा चालू करने के लिए फिर से कवर खरीदें। | हे पुन्हा सुरू करण्यासाठी पुन्हा कवर खरेदी करा. | sales: how to turn it on again |
| `purpose.slip.label` | Read my hospital slip to check a claim | दावा जाँचने के लिए मेरी अस्पताल की पर्ची पढ़ें | दावा तपासण्यासाठी माझी रुग्णालयाची पर्ची वाचा | slip: label of the purpose |
| `purpose.slip.data_used` | The photo of the slip you send. Five details read from it: patient name, admission date, discharge date, hospital name, document type. | आपकी भेजी पर्ची की फ़ोटो। उससे पढ़ी गई पाँच जानकारियाँ: मरीज़ का नाम, भर्ती की तारीख़, छुट्टी की तारीख़, अस्पताल का नाम, काग़ज़ का प्रकार। | आपण पाठवलेल्या पर्चीचा फोटो. त्यातून वाचलेली पाच माहिती: रुग्णाचे नाव, भरतीची तारीख, डिस्चार्जची तारीख, रुग्णालयाचे नाव, कागदाचा प्रकार. | slip: what is used for this purpose |
| `purpose.slip.effect` | Chhatri stops reading slips, so no new hospital-cash claim can be made. Your cover and premium stay as they are. Slips already stored stay until you erase them. | छतरी पर्चियाँ पढ़ना बंद कर देगी, इसलिए अस्पताल-कैश का नया दावा नहीं बन सकेगा। आपका कवर और प्रीमियम जैसे हैं वैसे ही रहेंगे। जमा हो चुकी पर्चियाँ तब तक रहेंगी जब तक आप उन्हें मिटा न दें। | छत्री पर्च्या वाचणे बंद करेल, त्यामुळे हॉस्पिटल कॅशचा नवीन दावा करता येणार नाही. आपले कवर आणि प्रीमियम जसे आहेत तसेच राहतील. साठवलेल्या पर्च्या आपण मिटवेपर्यंत राहतील. | slip: what happens when the merchant turns it off |
| `purpose.slip.regrant` | To turn this on again, send a slip in the app and agree when asked. | इसे दोबारा चालू करने के लिए ऐप में पर्ची भेजें और पूछे जाने पर हामी भरें। | हे पुन्हा सुरू करण्यासाठी ॲपमध्ये पर्ची पाठवा आणि विचारल्यावर संमती द्या. | slip: how to turn it on again |
| `purpose.settlement.label` | Take the next day's premium from my daily settlement | मेरे रोज़ के सेटलमेंट से अगले दिन का प्रीमियम काटें | माझ्या रोजच्या सेटलमेंटमधून पुढच्या दिवसाचे प्रीमियम घ्या | settlement: label of the purpose |
| `purpose.settlement.data_used` | Your day's collections, to check they cover the premium. The premium amount for your zone. | आपके दिन की कमाई, यह देखने के लिए कि प्रीमियम निकल सकता है। आपके ज़ोन का प्रीमियम। | आपल्या दिवसाची जमा रक्कम, प्रीमियम निघू शकते का हे पाहण्यासाठी. आपल्या झोनचे प्रीमियम. | settlement: what is used for this purpose |
| `purpose.settlement.effect` | Chhatri stops taking the premium from your settlement. Your cover keeps working through {paid_through}, the date you have paid for. After that the premium is due, and a claim for a later day is not paid until you pay again with a link. | छतरी आपके सेटलमेंट से प्रीमियम काटना बंद कर देगी। आपका कवर {paid_through} तक चलता रहेगा, यानी जिस तारीख़ तक आपने भुगतान किया है। उसके बाद प्रीमियम बाकी होगा, और बाद के दिन का दावा तब तक नहीं मिलेगा जब तक आप लिंक से फिर भुगतान नहीं करते। | छत्री आपल्या सेटलमेंटमधून प्रीमियम घेणे बंद करेल. आपले कवर {paid_through} पर्यंत चालू राहील, म्हणजे ज्या तारखेपर्यंत आपण पैसे भरले आहेत. त्यानंतर प्रीमियम बाकी राहील, आणि नंतरच्या दिवसाचा दावा आपण लिंकने पुन्हा पैसे भरेपर्यंत दिला जात नाही. | facts: `paid_through`; settlement: what happens when the merchant turns it off; {paid_through} is the date the merchant has paid for |
| `purpose.settlement.regrant` | To turn this on again, pay with a new link and agree when asked. | इसे दोबारा चालू करने के लिए नए लिंक से भुगतान करें और पूछे जाने पर हामी भरें। | हे पुन्हा सुरू करण्यासाठी नव्या लिंकने पैसे भरा आणि विचारल्यावर संमती द्या. | settlement: how to turn it on again |

### 14.3 Chat lines

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `CONSENT_WITHDRAWN_SALES` | {name_en} ji, you turned off the use of your sales data. Your cover is cancelled and no new claims will be made. To get cover again, buy again in the app. | {name_hi} जी, आपने बिक्री के डेटा का इस्तेमाल बंद कर दिया। आपका कवर रद्द हो गया है और कोई नया दावा नहीं बनेगा। दोबारा कवर के लिए ऐप में फिर से खरीदें। | {name_mr} जी, आपण विक्रीच्या डेटाचा वापर बंद केला. आपले कवर रद्द झाले आहे आणि नवीन दावे तयार होणार नाहीत. पुन्हा कवर हवे असल्यास ॲपमध्ये पुन्हा खरेदी करा. | facts: `name`; After a sales withdrawal |
| `CONSENT_WITHDRAWN_SLIP` | {name_en} ji, you turned off slip reading. New slips will not be read. Slips already stored stay until you erase them in the app. | {name_hi} जी, आपने पर्ची पढ़ना बंद कर दिया। नई पर्चियाँ नहीं पढ़ी जाएँगी। जमा पर्चियाँ तब तक रहेंगी जब तक आप ऐप में उन्हें मिटा न दें। | {name_mr} जी, आपण पर्ची वाचणे बंद केले. नवीन पर्च्या वाचल्या जाणार नाहीत. साठवलेल्या पर्च्या आपण ॲपमध्ये मिटवेपर्यंत राहतील. | facts: `name`; After a slip withdrawal |
| `CONSENT_WITHDRAWN_SETTLEMENT` | {name_en} ji, you turned off premium deductions from your settlement. Your cover runs through {paid_to_en}. After that, pay again with a link to keep it. | {name_hi} जी, आपने सेटलमेंट से प्रीमियम कटना बंद कर दिया। आपका कवर {paid_to_hi} तक चलेगा। उसके बाद कवर रखने के लिए लिंक से फिर भुगतान करें। | {name_mr} जी, आपण सेटलमेंटमधून प्रीमियम कापणे बंद केले. आपले कवर {paid_to_mr} पर्यंत चालेल. त्यानंतर ते ठेवण्यासाठी लिंकने पुन्हा पैसे भरा. | facts: `name`, `paid_to`; After a settlement withdrawal |
| `SLIP_CONSENT_NEEDED` | We need your OK before we read a slip. Open the app and send your slip there. It will ask for your OK first. | पर्ची पढ़ने से पहले हमें आपकी हामी चाहिए। ऐप खोलकर पर्ची वहीं भेजें। वह पहले आपकी हामी पूछेगा। | पर्ची वाचण्यापूर्वी आम्हाला आपली संमती हवी आहे. ॲप उघडा आणि पर्ची तिथेच पाठवा. ते आधी आपली संमती विचारेल. | A photo arrives without an ACTIVE slip consent |

### 14.4 Consent centre screen

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `consent.title` | My data and consent | मेरा डेटा और सहमति | माझा डेटा आणि संमती | - |
| `consent.intro` | You decide how Chhatri uses your data. You can turn each item off. | आप तय करते हैं कि छतरी आपके डेटा का कैसे इस्तेमाल करे। आप हर एक को बंद कर सकते हैं। | छत्री आपला डेटा कसा वापरते हे आपण ठरवता. प्रत्येक गोष्ट आपण बंद करू शकता. | - |
| `consent.version` | Notice {version}. Prototype: nothing here is real data. | सूचना {version}। प्रोटोटाइप: यहाँ कुछ भी असली डेटा नहीं है। | सूचना {version}. प्रोटोटाइप: येथे काहीही खरा डेटा नाही. | facts: `version`; footer of the consent centre; version of the notice |
| `consent.state.on` | On | चालू | चालू | - |
| `consent.state.off` | Off | बंद | बंद | - |
| `consent.state.not_given` | Not given | दी नहीं गई | दिलेली नाही | - |
| `consent.source.seeded` | Set up by the simulator for this demo. | इस डेमो के लिए सिमुलेटर ने बनाया। | या डेमोसाठी सिम्युलेटरने तयार केले. | consent that the simulator set up for the demo |
| `consent.source.payment_app` | Agreed when you paid, in the app. | भुगतान के समय ऐप में सहमति दी। | पैसे भरताना ॲपमध्ये संमती दिली. | - |
| `consent.source.payment_chat` | Agreed when you paid, from the chat notice. | भुगतान के समय चैट की सूचना पर सहमति दी। | पैसे भरताना चॅटमधील सूचनेवर संमती दिली. | - |
| `consent.source.slip_upload` | Agreed when you sent a slip. | पर्ची भेजते समय सहमति दी। | पर्ची पाठवताना संमती दिली. | - |
| `consent.granted_on` | Agreed on {date} | {date} को सहमति दी | {date} रोजी संमती दिली | facts: `date` |
| `consent.used` | What we use | हम क्या इस्तेमाल करते हैं | आम्ही काय वापरतो | - |
| `consent.receipt` | Receipt | रसीद | पावती | - |
| `consent.empty` | You have not agreed to anything yet. You agree when you buy cover. | आपने अभी किसी बात पर सहमति नहीं दी है। कवर खरीदते समय आप सहमति देते हैं। | आपण अजून कशालाही संमती दिलेली नाही. कवर खरेदी करताना आपण संमती देता. | - |
| `consent.withdraw.title` | Turn this off? | इसे बंद करें? | हे बंद करायचे? | - |
| `consent.withdraw.confirm` | Turn off | बंद करें | बंद करा | - |
| `consent.withdraw.cancel` | Keep it on | चालू रखें | चालू ठेवा | - |
| `consent.withdraw.done` | Turned off. | बंद कर दिया। | बंद केले. | - |
| `consent.err.case_open` | Your claim is still being checked by our team. You can turn this off once it is answered. | आपका दावा अभी हमारी टीम देख रही है। जवाब आने के बाद आप इसे बंद कर सकते हैं। | आपला दावा अजून आमची टीम तपासत आहे. उत्तर आल्यानंतर आपण हे बंद करू शकता. | withdrawal refused while a claim review is open |
| `consent.activity_link` | See what was used | देखें क्या इस्तेमाल हुआ | काय वापरले ते पाहा | - |
| `consent.complain` | Complain about my data | मेरे डेटा के बारे में शिकायत करें | माझ्या डेटाबद्दल तक्रार करा | opens the grievance ladder with the topic data or consent |

### 14.5 Activity log

One fixed sentence for each audit action. A sentence never copies text from the audit entry, so it cannot print a patient name. Times are replay times.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `activity.title` | What was used | क्या इस्तेमाल हुआ | काय वापरले | - |
| `activity.empty` | Nothing has been used yet. | अभी तक कुछ इस्तेमाल नहीं हुआ। | अजून काहीही वापरलेले नाही. | - |
| `activity.filter.all` | All | सभी | सर्व | - |
| `activity.filter.sales` | Sales | बिक्री | विक्री | - |
| `activity.filter.slip` | Slip | पर्ची | पर्ची | - |
| `activity.filter.settlement` | Premium | प्रीमियम | प्रीमियम | - |
| `activity.more` | Show more | और दिखाएँ | आणखी दाखवा | - |
| `activity.times` | Times are simulated. | समय सिमुलेटेड हैं। | वेळा सिम्युलेटेड आहेत. | footer of the activity screen |
| `activity.silence.detected` | Your shop's sales were checked for {day}. No sales were found. | {day} के लिए आपकी दुकान की बिक्री देखी गई। कोई बिक्री नहीं मिली। | {day} साठी आपल्या दुकानाची विक्री तपासली गेली. कोणतीही विक्री आढळली नाही. | facts: `day`; audit action `silence.detected`; purpose sales; kind USED |
| `activity.decision.area` | Your sales for {day} were compared with your usual day. Decision {decision_id}. | {day} की आपकी बिक्री की तुलना आपके आम दिन से की गई। फ़ैसला {decision_id}। | {day} ची आपली विक्री आपल्या नेहमीच्या दिवसाशी तुलना केली गेली. निर्णय {decision_id}. | facts: `day`, `decision_id`; audit action `decision.area`; purpose sales; kind USED |
| `activity.slip.read` | Your slip photo was read. Details found: {found} of {total}. | आपकी पर्ची की फ़ोटो पढ़ी गई। मिली जानकारी: {total} में से {found}। | आपल्या पर्चीचा फोटो वाचला गेला. मिळालेली माहिती: {total} पैकी {found}. | facts: `found`, `total`; audit action `slip.read`; purpose slip; kind USED |
| `activity.decision.personal` | Your slip details were checked for a claim. Decision {decision_id}. | आपके दावे के लिए पर्ची की जानकारी जाँची गई। फ़ैसला {decision_id}। | दाव्यासाठी आपल्या पर्चीतील माहिती तपासली गेली. निर्णय {decision_id}. | facts: `decision_id`; audit action `decision.personal`; purpose slip; kind USED |
| `activity.decision.officer` | Your slip details were checked for a claim. Decision {decision_id}. | आपके दावे के लिए पर्ची की जानकारी जाँची गई। फ़ैसला {decision_id}। | दाव्यासाठी आपल्या पर्चीतील माहिती तपासली गेली. निर्णय {decision_id}. | facts: `decision_id`; audit action `decision.officer`; purpose slip; kind USED |
| `activity.premium.settled` | Tomorrow's premium of {amount} was taken from today's collections. | आज की कमाई से कल का {amount} का प्रीमियम लिया गया। | आजच्या जमा रकमेतून उद्याचे {amount} चे प्रीमियम घेतले गेले. | facts: `amount`; audit action `premium.settled`; purpose settlement; kind USED |
| `activity.premium.not_settled` | Today's collections were checked. Nothing was taken ({reason}). | आज की कमाई जाँची गई। कुछ नहीं काटा गया ({reason})। | आजची जमा रक्कम तपासली गेली. काहीही घेतले गेले नाही ({reason}). | facts: `reason`; audit action `premium.not_settled`; purpose settlement; kind USED |
| `activity.consent.granted` | You agreed: {label}. | आपने सहमति दी: {label}। | आपण संमती दिली: {label}. | facts: `label`; audit action `consent.granted`; purpose its purpose; kind GRANTED |
| `activity.consent.withdrawn` | You turned off: {label}. | आपने बंद किया: {label}। | आपण बंद केले: {label}. | facts: `label`; audit action `consent.withdrawn`; purpose its purpose; kind WITHDRAWN |
| `activity.cover.cancelled` | Your cover was cancelled because sales data was turned off. | बिक्री का डेटा बंद करने के कारण आपका कवर रद्द हुआ। | विक्रीचा डेटा बंद केल्यामुळे आपले कवर रद्द झाले. | audit action `cover.cancelled`; purpose sales; kind EFFECT |
| `activity.slip.erased` | Your slip data was erased. | आपकी पर्ची का डेटा मिटा दिया गया। | आपल्या पर्चीचा डेटा मिटवला गेला. | audit action `slip.erased`; purpose slip; kind ERASED |
| `activity.reason.below_premium` | collections below premium | कमाई प्रीमियम से कम थी | जमा रक्कम प्रीमियमपेक्षा कमी होती | one of three fixed phrases for the {reason} of an activity sentence |
| `activity.reason.lapsed` | cover lapsed before this day | इस दिन से पहले कवर ख़त्म हो चुका था | या दिवसाआधी कवर संपले होते | one of three fixed phrases for the {reason} of an activity sentence |
| `activity.reason.withdrawn` | consent withdrawn | आपने सहमति वापस ली थी | संमती मागे घेतली होती | one of three fixed phrases for the {reason} of an activity sentence |

### 14.6 Forget my slip

The photo, the details read from it and the same text in the claim record are erased. The decision, the amount and the check results stay. The activity log cannot be edited, and the app says so before the merchant confirms.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `slip.held` | Slip received {date} | {date} को मिली पर्ची | {date} रोजी मिळालेली पर्ची | facts: `date` |
| `slip.state.held` | Held | रखी है | ठेवलेली आहे | - |
| `slip.state.erased` | Erased | मिटाई गई | मिटवली | - |
| `slip.erase` | Erase this slip | यह पर्ची मिटाएँ | ही पर्ची मिटवा | - |
| `slip.erase.blocked` | Your claim is still being checked. You can erase the slip once it is answered. | आपका दावा अभी जाँचा जा रहा है। जवाब आने के बाद आप पर्ची मिटा सकते हैं। | आपला दावा अजून तपासला जात आहे. उत्तर आल्यानंतर आपण पर्ची मिटवू शकता. | erase refused while a claim review is open |
| `slip.erase.title` | Erase this slip? | यह पर्ची मिटाएँ? | ही पर्ची मिटवायची? | - |
| `slip.erase.removes` | We will erase: the photo, the details read from it (name, dates, hospital), and the same text in your claim record. | हम मिटाएँगे: फ़ोटो, उससे पढ़ी गई जानकारी (नाम, तारीख़ें, अस्पताल), और आपके दावे के रिकॉर्ड में वही लिखा हुआ। | आम्ही मिटवू: फोटो, त्यातून वाचलेली माहिती (नाव, तारखा, रुग्णालय) आणि आपल्या दाव्याच्या नोंदीतील तेच लिखाण. | - |
| `slip.erase.keeps` | We will keep: the decision, the amount, and which checks passed or failed. | हम रखेंगे: फ़ैसला, रकम, और कौन-सी जाँच पास या फ़ेल हुई। | आम्ही ठेवू: निर्णय, रक्कम आणि कोणत्या तपासण्या पास किंवा फेल झाल्या ते. | - |
| `slip.erase.audit_note` | The activity log cannot be edited, so it can still show the name and dates from this slip in entries written before today. | गतिविधि का लॉग बदला नहीं जा सकता, इसलिए आज से पहले लिखी गई प्रविष्टियों में इस पर्ची का नाम और तारीख़ें दिख सकती हैं। | गतिविधी नोंदवहीत (लॉग) बदल करता येत नाही, त्यामुळे आजपूर्वी लिहिलेल्या नोंदींमध्ये या पर्चीचे नाव आणि तारखा दिसू शकतात. | shown before the merchant confirms; the audit log is never edited |
| `slip.erase.confirm` | Erase | मिटाएँ | मिटवा | - |
| `slip.erase.cancel` | Keep it | रहने दें | राहू द्या | - |
| `slip.erase.done` | Slip erased. | पर्ची मिटा दी गई। | पर्ची मिटवली. | - |
| `receipt.erased` | Details erased on {date} at your request. The audit log still holds the original entry. | विवरण {date} को आपके कहने पर मिटाए गए। ऑडिट लॉग में मूल प्रविष्टि अब भी है। | आपल्या विनंतीवरून {date} रोजी तपशील मिटवले. ऑडिट लॉगमध्ये मूळ नोंद अजूनही आहे. | facts: `date`; shown on the decision view and the receipt after an erase |

## 15. States: empty, error, offline, SIMULATED, FALLBACK

### 15.1 Empty

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `empty.claims` | No claims yet. If your area's sales fall during a weather alert, Chhatri starts a claim for you. If your shop has no sales for a full day, Chhatri will ask if you are okay. | अभी कोई दावा नहीं है। मौसम अलर्ट के दौरान आपके इलाके की बिक्री गिरे, तो छतरी आपके लिए दावा शुरू करती है। आपकी दुकान में पूरे दिन बिक्री न हो, तो छतरी आपसे पूछेगी कि सब ठीक है या नहीं। | अजून कोणताही दावा नाही. हवामान अलर्ट दरम्यान आपल्या परिसरातील विक्री घटली, तर छत्री आपल्यासाठी दावा सुरू करते. आपल्या दुकानात दिवसभर विक्री झाली नाही, तर छत्री आपल्याला सर्व ठीक आहे का ते विचारेल. | claims list with no claim |
| `empty.cover` | You have no cover yet. | अभी आपका कोई कवर नहीं है। | आपले अजून कोणतेही कवर नाही. | Home with no cover record |
| `empty.receipt` | No receipt yet. A receipt appears after a payout is credited. | अभी कोई रसीद नहीं है। भुगतान जमा होने के बाद रसीद दिखती है। | अजून पावती नाही. रक्कम जमा झाल्यानंतर पावती दिसते. | receipt screen before a payout exists |
| `empty.consents` | Nothing to show yet. Your choices appear here after you buy cover. | अभी दिखाने को कुछ नहीं है। कवर खरीदने के बाद आपकी पसंद यहाँ दिखेगी। | अजून दाखवण्यासारखे काही नाही. कवर खरेदी केल्यानंतर आपले पर्याय येथे दिसतील. | - |
| `empty.grievances` | You have no open questions or complaints. | आपका कोई सवाल या शिकायत खुली नहीं है। | आपला कोणताही प्रश्न किंवा तक्रार खुली नाही. | - |

### 15.2 Error

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `error.title` | Could not load this | यह लोड नहीं हो सका | हे लोड होऊ शकले नाही | BUILT; English line is the BUILT error title |
| `error.generic` | Something went wrong. Try again. | कुछ गड़बड़ हो गई। फिर से कोशिश करें। | काहीतरी चुकले. पुन्हा प्रयत्न करा. | the mini-app error state; the English line is the wording of the mini-app spec |
| `error.retry` | Try again | फिर से कोशिश करें | पुन्हा प्रयत्न करा | BUILT; English line is the BUILT button label of the console error state |
| `error.code` | Error code: {code} | त्रुटि कोड: {code} | त्रुटी कोड: {code} | facts: `code`; small text under the error; code is the API error code such as not_found or contract_violation |
| `error.network` | We cannot connect right now. Check your internet and try again. | अभी कनेक्ट नहीं हो पा रहा। अपना इंटरनेट देखिए और फिर से कोशिश कीजिए। | सध्या कनेक्ट होत नाही. आपले इंटरनेट तपासा आणि पुन्हा प्रयत्न करा. | merchant wording for the BUILT NETWORK_ERROR state, whose console text says: Can’t reach the Chhatri server. Check that it is running, then try again. |
| `error.timeout` | This is taking too long. Please try again in a moment. | इसमें बहुत समय लग रहा है। कृपया थोड़ी देर बाद फिर से कोशिश करें। | यास खूप वेळ लागत आहे. कृपया थोड्या वेळाने पुन्हा प्रयत्न करा. | merchant wording for the BUILT TIMEOUT state, whose console text says: The Chhatri server is taking too long to answer. Try again in a moment. |
| `error.not_found` | We could not find this. It may have been removed, or the link is wrong. | यह नहीं मिला। हो सकता है यह हटा दिया गया हो, या लिंक ग़लत हो। | हे सापडले नाही. ते काढून टाकले असू शकते, किंवा लिंक चुकीची असू शकते. | X5: an unknown id gives a 404 and this screen, not a blank page |
| `error.no_zone` | We could not find your area, so your cover details cannot be shown. Please talk to our team. | आपका इलाका नहीं मिला, इसलिए कवर का ब्योरा नहीं दिखाया जा सकता। कृपया हमारी टीम से बात करें। | आपला परिसर सापडला नाही, म्हणून कवरचा तपशील दाखवता येत नाही. कृपया आमच्या टीमशी बोला. | X3: a merchant with no zone fails loudly instead of showing a made-up value |
| `error.pay_failed` | The payment did not go through. No money was taken. You can try again. | भुगतान नहीं हो पाया। कोई पैसा नहीं कटा। आप फिर से कोशिश कर सकते हैं। | पेमेंट होऊ शकले नाही. कोणतेही पैसे कापले गेले नाहीत. आपण पुन्हा प्रयत्न करू शकता. | premium payment FAILED; the BUILT COVER_LINK_UNAVAILABLE covers a link that could not be made |

### 15.3 Offline and the static demo (N7, wave 5)

The static demo runs in the browser against the in-browser mock backend. This deck does not claim that a public address exists; the repo owner deploys the static build.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `offline.banner` | Offline. Showing data from {time}. | ऑफ़लाइन। {time} का डेटा दिख रहा है। | ऑफलाइन. {time} चा डेटा दिसत आहे. | facts: `time`; the last good data stays on screen from memory; no copy is stored |
| `offline.blocked` | This needs the internet. Please try again when you are online. | इसके लिए इंटरनेट चाहिए। ऑनलाइन होने पर फिर से कोशिश करें। | यासाठी इंटरनेट लागते. ऑनलाइन झाल्यावर पुन्हा प्रयत्न करा. | - |
| `offline.static` | This is the static demo. It runs in your browser with made-up data. Nothing is sent anywhere. | यह स्टैटिक डेमो है। यह आपके ब्राउज़र में बनावटी डेटा के साथ चलता है। कुछ भी कहीं नहीं भेजा जाता। | हा स्टॅटिक डेमो आहे. तो आपल्या ब्राउझरमध्ये बनावट डेटासह चालतो. काहीही कुठेही पाठवले जात नाही. | N7; shown as a banner in the static build; nothing here claims that a public address exists |

### 15.4 SIMULATED

Always shown today, because sales, alerts, KYC, payouts, the lender, Soundbox, WhatsApp and the Paytm link are all simulated.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `sim.banner` | SIMULATED. This is demo data. No real money, message or payment moves. | SIMULATED। यह डेमो डेटा है। असली पैसा, संदेश या भुगतान नहीं जाता। | SIMULATED. हा डेमो डेटा आहे. खरे पैसे, संदेश किंवा पेमेंट जात नाही. | top of the mini-app and the receipt while any source is SIMULATED, which is always the case today |
| `sim.payment` | SIMULATED payment. No real money moves. | SIMULATED भुगतान। असली पैसा नहीं जाता। | SIMULATED पेमेंट. खरे पैसे जात नाहीत. | same text as buy.link.simulated, shown on the payout and premium rows |
| `sim.whatsapp` | SIMULATED WhatsApp. These messages stay in this demo phone. | SIMULATED WhatsApp। ये संदेश इसी डेमो फ़ोन में रहते हैं। | SIMULATED WhatsApp. हे संदेश याच डेमो फोनमध्ये राहतात. | chat header while the WhatsApp channel is not live |
| `sim.soundbox` | SIMULATED Soundbox. No speaker is used. | SIMULATED Soundbox। कोई स्पीकर इस्तेमाल नहीं होता। | SIMULATED Soundbox. कोणताही स्पीकर वापरला जात नाही. | Soundbox card |
| `sim.slip` | SIMULATED slip reading. A fixed result is used for the demo slips. | SIMULATED पर्ची पढ़ना। डेमो पर्चियों के लिए तय नतीजा इस्तेमाल होता है। | SIMULATED पर्ची वाचन. डेमो पर्च्यांसाठी ठरलेला निकाल वापरला जातो. | slip pre-check and receipt while the slip reader is simulated |
| `sim.lender` | SIMULATED lender. The answer comes from the demo rules. | SIMULATED लेंडर। जवाब डेमो नियमों से आता है। | SIMULATED लेंडर. उत्तर डेमो नियमांवरून येते. | instalment holiday rows |
| `sim.data` | SIMULATED data: sales, alerts and KYC are made up for the demo. | SIMULATED डेटा: बिक्री, अलर्ट और KYC डेमो के लिए बनाए गए हैं। | SIMULATED डेटा: विक्री, अलर्ट आणि KYC डेमोसाठी बनवलेले आहेत. | source chip details |

### 15.5 FALLBACK and the reasons (X6, H26, wave 2)

A FALLBACK badge says that a backup stepped in. It shows the provider and one reason line, and the console shows the code. The eleven reason codes are the ones of [fs-05](../02-product/feature-specs/fs-05-ask-chhatri.md) section 10: the first five give mode SIMULATED, the other six give mode FALLBACK.

| Key | English | Hindi | Marathi (draft, needs a native speaker's review) | Facts and when shown |
|---|---|---|---|---|
| `fb.banner` | FALLBACK. A backup is in use because the usual service was not available. | FALLBACK। आम सेवा उपलब्ध नहीं थी, इसलिए बैकअप इस्तेमाल हो रहा है। | FALLBACK. नेहमीची सेवा उपलब्ध नव्हती, म्हणून बॅकअप वापरले जात आहे. | shown with the reason line below it; hidden until X6 is switched on |
| `fb.reason.NO_KEY` | No key is set for this service, so the built-in demo is used. | इस सेवा के लिए कोई की सेट नहीं है, इसलिए बना-बनाया डेमो इस्तेमाल हो रहा है। | या सेवेसाठी कोणतीही की सेट केलेली नाही, म्हणून तयार डेमो वापरला जात आहे. | fallback_reason NO_KEY; mode SIMULATED |
| `fb.reason.MODEL_NOT_SET` | A key is set but no model is chosen, so the built-in demo is used. | की सेट है पर मॉडल चुना नहीं गया है, इसलिए बना-बनाया डेमो इस्तेमाल हो रहा है। | की सेट आहे पण मॉडेल निवडलेले नाही, म्हणून तयार डेमो वापरला जात आहे. | fallback_reason MODEL_NOT_SET; mode SIMULATED |
| `fb.reason.FORCED` | A presenter switched this on for the demo. | प्रस्तुतकर्ता ने डेमो के लिए इसे चालू किया है। | सादरकर्त्याने डेमोसाठी हे सुरू केले आहे. | fallback_reason FORCED: the demo fallback switch of X6; mode SIMULATED |
| `fb.reason.MOCK_BACKEND` | This is the static demo, so recorded samples are shown. | यह स्टैटिक डेमो है, इसलिए रिकॉर्ड किए हुए नमूने दिख रहे हैं। | हा स्टॅटिक डेमो आहे, म्हणून रेकॉर्ड केलेले नमुने दिसत आहेत. | fallback_reason MOCK_BACKEND: the in-browser mock backend; mode SIMULATED |
| `fb.reason.FREE_TIER_BLOCKED` | Real data is not sent to a free service, so the built-in demo is used. | असली डेटा मुफ़्त सेवा को नहीं भेजा जाता, इसलिए बना-बनाया डेमो इस्तेमाल हो रहा है। | खरा डेटा मोफत सेवेकडे पाठवला जात नाही, म्हणून तयार डेमो वापरला जात आहे. | fallback_reason FREE_TIER_BLOCKED: the data gate of ADR 0009; mode SIMULATED |
| `fb.reason.TIMEOUT` | The service took too long to answer. | सेवा ने जवाब देने में बहुत समय लिया। | सेवेने उत्तर देण्यास खूप वेळ घेतला. | fallback_reason TIMEOUT; mode FALLBACK |
| `fb.reason.RATE_LIMITED` | The service is busy or its free limit is used up. | सेवा व्यस्त है या उसकी मुफ़्त सीमा पूरी हो चुकी है। | सेवा व्यस्त आहे किंवा तिची मोफत मर्यादा संपली आहे. | fallback_reason RATE_LIMITED; mode FALLBACK |
| `fb.reason.PROVIDER_ERROR` | The service returned an error. | सेवा से त्रुटि मिली। | सेवेकडून त्रुटी मिळाली. | fallback_reason PROVIDER_ERROR; mode FALLBACK |
| `fb.reason.INVALID_REPLY` | The service's answer could not be used. | सेवा का जवाब इस्तेमाल करने लायक़ नहीं था। | सेवेचे उत्तर वापरण्यासारखे नव्हते. | fallback_reason INVALID_REPLY; mode FALLBACK |
| `fb.reason.GUARD_BLOCKED` | The answer could not be matched with your records, so a fixed answer is shown. | जवाब आपके रिकॉर्ड से मिलाया नहीं जा सका, इसलिए तय जवाब दिखाया जा रहा है। | उत्तर आपल्या नोंदींशी जुळवता आले नाही, म्हणून ठरलेले उत्तर दाखवले जात आहे. | fallback_reason GUARD_BLOCKED: the guard blocked a model reply; mode FALLBACK |
| `fb.reason.INJECTION_SUSPECTED` | A ready-made answer is shown. | तैयार जवाब दिखाया जा रहा है। | तयार उत्तर दाखवले जात आहे. | fallback_reason INJECTION_SUSPECTED; mode FALLBACK; the line does not say why, so the detection is not revealed; the console shows the code |
| `fb.ask` | Ask Chhatri is using ready-made answers right now. | अभी "छतरी से पूछें" में तैयार जवाब इस्तेमाल हो रहे हैं। | सध्या "छत्रीला विचारा" मध्ये तयार उत्तरे वापरली जात आहेत. | Ask Chhatri while its provider is in FALLBACK |
| `fb.slip` | Slip reading is not available, so a person will check your slip. | पर्ची पढ़ना अभी उपलब्ध नहीं है, इसलिए आपकी पर्ची कोई व्यक्ति देखेगा। | पर्ची वाचन सध्या उपलब्ध नाही, म्हणून आपली पर्ची एक व्यक्ती तपासेल. | slip pre-check while the reader is in FALLBACK; same meaning as the BUILT SLIP_TO_HUMAN_UNREADABLE |
| `ai.badge.reason` | Why: {reason} | क्यों: {reason} | का: {reason} | facts: `reason`; second line of an AI mode badge; reason is one of the fb.reason lines |

## 16. Officer console strings (English only)

The officer console is English only ([fs-08](../02-product/feature-specs/fs-08-claims-officer-console.md) section 14), so these rows have no Hindi or Marathi. Rows marked BUILT are quoted from the code. The others are proposed, and the wave says when each lands. A placeholder in braces is filled by the console from API fields.

| Key | English | Status | Where shown |
|---|---|---|---|
| `console.note.label` | Note for the audit log (optional) | BUILT | case panel, above Approve and Decline |
| `console.btn.approve` | Approve | BUILT | case panel |
| `console.btn.decline` | Decline | BUILT | case panel |
| `console.no_token` | Officer token unavailable: approvals need the demo session (GET /api/session). | BUILT | case panel, while the demo session is missing |
| `console.replay.slow` | Slow near payout | BUILT | control bar |
| `console.replay.loading` | Loading the replay… | BUILT | live page |
| `console.replay.seeking` | Moving the replay clock… | BUILT | live page |
| `console.audit.verify` | Verify chain | BUILT | audit page |
| `console.audit.valid` | Chain valid · {entries} entries · head {hash}… | BUILT | audit page; the head is the first characters of the hash |
| `console.audit.invalid` | Chain INVALID · first bad entry #{seq} of {entries} | BUILT | audit page |
| `console.dispute.confirm` | Confirm payout | PROPOSED, wave 4 | case panel of a DISPUTE case; the route stays /approve |
| `console.dispute.reject` | Reject dispute | PROPOSED, wave 4 | case panel of a DISPUTE case; the route stays /decline |
| `console.dispute.hint` | The amount cannot change. Confirming keeps the payout. Rejecting closes the dispute. The merchant is told the result either way. | PROPOSED, wave 4 | one line above the two DISPUTE buttons |
| `console.provider.force` | Force fallback | PROPOSED, wave 2 | provider panel, one switch for each switchable component |
| `console.provider.clear` | Clear all | PROPOSED, wave 2 | provider panel |
| `console.provider.forced` | forced for the demo | PROPOSED, wave 2 | chip next to a component that is forced; also the header chip while any component is forced |
| `console.provider.static` | static demo: nothing live to force | PROPOSED, wave 2 | provider panel in the static demo |
| `console.provider.model_not_set` | key set, model not set | PROPOSED, wave 2 | provider panel; the reason MODEL_NOT_SET in words |
| `console.cf.note` | checked by re-running the engine | PROPOSED, wave 4 | note under the one counterfactual line of a decision |
| `console.feed.holiday_refused` | {shop}: lender refused the holiday ({code}) | PROPOSED, wave 4 | feed line when the lender refuses or does not answer |
| `console.ops.open_cases` | Open cases | PROPOSED, wave 4 | ops strip, cell 1 |
| `console.ops.next_due` | Next due | PROPOSED, wave 4 | ops strip, cell 2 |
| `console.ops.engine_share` | Decided by the engine | PROPOSED, wave 4 | ops strip, cell 3 |
| `console.ops.paid_today` | Paid today | PROPOSED, wave 4 | ops strip, cell 4 |
| `console.ops.holiday` | Holiday requests | PROPOSED, wave 4 | ops strip, cell 5 |
| `console.ops.unavailable` | Ops numbers unavailable | PROPOSED, wave 4 | ops strip when the request fails, with a retry button |
| `console.whatif.open` | What if... | PROPOSED, wave 4 | button on the zone card |
| `console.whatif.readonly` | Read-only: nothing is saved | PROPOSED, wave 4 | top of the what-if drawer |
| `console.whatif.evaluated` | Evaluated at {time}, window {from} to {to} | PROPOSED, wave 4 | top of the what-if drawer; the hour is pinned when the drawer opens |
| `console.whatif.latest` | Latest hour | PROPOSED, wave 4 | link that pins the latest hour again |
| `console.whatif.back` | Back to what happened | PROPOSED, wave 4 | clears every override |
| `console.whatif.would_fire` | Would fire | PROPOSED, wave 4 | result line, with the drop when it fires |
| `console.whatif.would_not_fire` | Would not fire | PROPOSED, wave 4 | result line |
| `console.presenter.on` | Present | PROPOSED, wave 4 | header button for presenter mode |
| `console.presenter.keys` | Keys | PROPOSED, wave 4 | opens the list of presenter keys |
| `console.backtest.caveat` | The model's range is calibrated on simulated sales, so this backtest tests the rule, not accuracy on real shops. | PROPOSED, wave 4 | one line under the backtest hero |

## 17. Appendix A: the built catalogue with Marathi drafts

The 51 keys of `backend/chhatri/conversation/messages.py`, quoted exactly from `CATALOGUE`. English and Hindi are built. The Marathi column is a draft and needs a native speaker's review. A key with no Hindi line in the catalogue (CASE_CHIP and the three payout card badges) has no Marathi line either; the badge strings are in section 4.2. In a Marathi text, `{name_mr}`, `{date_mr}`, `{starts_on_mr}`, `{prepaid_mr}`, `{paid_to_mr}`, `{reason_mr}`, `{formula_mr}` and `{weekday_mr}` replace the `_hi` facts. `name_mr` can reuse `owner_name_hi`, which is already Devanagari.

| Key | English (built) | Hindi (built) | Marathi (draft, needs a native speaker's review) | Facts |
|---|---|---|---|---|
| `AREA_PAYOUT_INTRO` | {name_en} ji, heavy rain cut your area's sales by {drop}% today. | {name_hi} जी, आज भारी बारिश से आपके इलाके की बिक्री {drop}% गिरी। | {name_mr} जी, आज मुसळधार पावसामुळे आपल्या परिसरातील विक्री {drop}% घटली. | `drop`, `name_en`, `name_hi` |
| `PAYOUT_CARD` | Credited with today's settlement | आज के सेटलमेंट के साथ जमा | आजच्या सेटलमेंटसोबत जमा | - |
| `INSTALMENT_PAUSED` | Tomorrow's {instalment} instalment is paused. | कल की {instalment} की किस्त रोक दी गई है। | उद्या देय असलेला {instalment} चा हप्ता थांबवण्यात आला आहे. | `instalment` |
| `SOUNDBOX` | {amount} received on Paytm, from Chhatri | Paytm par {amount} prapt hue — Chhatri se | Paytm वर {amount} मिळाले — छत्रीकडून | `amount` |
| `CHECKIN_SILENT` | Your shop has been closed since yesterday. Is everything okay? | {name_hi} जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है? | {name_mr} जी, आपली दुकान कालपासून बंद दिसत आहे. सगळे ठीक आहे ना? | `name_hi` |
| `ASK_SLIP` | Get well soon. Please send one photo of the hospital slip. | जल्दी ठीक हो जाइए। अस्पताल की पर्ची की एक फ़ोटो भेज दीजिए। | लवकर बरे व्हा. रुग्णालयाच्या पर्चीचा एक फोटो पाठवा. | - |
| `PERSONAL_PAID` | {name_en} ji, your claim is approved. {amount} credited with today's settlement. | {name_hi} जी, आपका दावा मंज़ूर है। {amount} आज के सेटलमेंट के साथ जमा। | {name_mr} जी, आपला दावा मंजूर झाला आहे. {amount} आजच्या सेटलमेंटसोबत जमा. | `amount`, `name_en`, `name_hi` |
| `SLIP_TO_HUMAN` | Thank you. The name on the slip doesn't match your KYC, so our team will check it. You'll hear back within 24 hours. | धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा। | धन्यवाद. पर्चीवरील नाव आपल्या KYC शी जुळत नाही, म्हणून आमची टीम ती पाहील. 24 तासांत उत्तर मिळेल. | - |
| `EXPLAIN_AREA` | Your usual {weekday_en}: {expected}. Your area fell {drop}%. Chhatri pays half the lost sales. | आपका आम {weekday_hi}: {expected}। आज आपके इलाके की बिक्री {drop}% गिरी। छतरी खोई हुई बिक्री का आधा देती है। | आपला नेहमीचा {weekday_mr}: {expected}. आज आपल्या परिसरातील विक्री {drop}% घटली. छत्री गमावलेल्या विक्रीचे निम्मे देते. | `drop`, `expected`, `weekday_en`, `weekday_hi` |
| `DISPUTE_ACK` | Okay, I'm sending this to our team. You'll hear back within 24 hours. | ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा। | ठीक आहे, मी हे आमच्या टीमला पाठवत आहे. 24 तासांत उत्तर मिळेल. | - |
| `CASE_CHIP` | Sent to a claims officer · case {case_id} | (none in the catalogue) | (none) | `case_id` |
| `COVER_BLOCKED` | New cover starts after the waiting period — from {starts_on_en}. It won't apply to tomorrow's alert. | नया कवर वेटिंग पीरियड के बाद शुरू होता है — {starts_on_hi} से। कल के अलर्ट पर यह लागू नहीं होगा। | नवीन कवर वेटिंग पीरियडनंतर सुरू होते — {starts_on_mr} पासून. ते उद्याच्या अलर्टसाठी लागू होणार नाही. | `starts_on_en`, `starts_on_hi` |
| `COVER_LINK` | To buy cover for later, pay {first_payment} ({per_day}/day) here: {url} | आगे के लिए कवर लेना हो तो {first_payment} ({per_day}/दिन) यहाँ भरें: {url} | पुढील काळासाठी कवर घ्यायचे असेल तर {first_payment} ({per_day}/दिवस) येथे भरा: {url} | `first_payment`, `per_day`, `url` |
| `OFFICER_APPROVED` | {name_en} ji, our team approved your claim. {amount} credited. | {name_hi} जी, हमारी टीम ने आपका दावा मंज़ूर किया। {amount} जमा। | {name_mr} जी, आमच्या टीमने आपला दावा मंजूर केला. {amount} जमा. | `amount`, `name_en`, `name_hi` |
| `OFFICER_DECLINED` | {name_en} ji, our team reviewed your claim. {reason_en} | {name_hi} जी, हमारी टीम ने आपका दावा देखा। {reason_hi} | {name_mr} जी, आमच्या टीमने आपला दावा पाहिला. {reason_mr} | `name_en`, `name_hi`, `reason_en`, `reason_hi` |
| `FALLBACK_HELP` | I'm Chhatri. You can ask: "Why did I get this amount?" or "My loss was bigger". | मैं छतरी हूँ। आप पूछ सकते हैं: "मुझे इतने पैसे क्यों मिले?" या "मेरा नुकसान ज़्यादा हुआ"। | मी छत्री आहे. आपण विचारू शकता: "मला इतकी रक्कम का मिळाली?" किंवा "माझे नुकसान जास्त झाले". | - |
| `PAYOUT_CARD_BADGE` | No claim needed | (none in the catalogue) | (none) | - |
| `PAYOUT_CARD_BADGE_PERSONAL` | One photo, no forms | (none in the catalogue) | (none) | - |
| `PAYOUT_CARD_BADGE_OFFICER` | Approved by a claims officer | (none in the catalogue) | (none) | - |
| `SLIP_TO_HUMAN_DATES` | Thank you. The dates on the slip don't match the days your shop was closed, so our team will check it. You'll hear back within 24 hours. | धन्यवाद। पर्ची की तारीख़ें दुकान बंद रहने के दिनों से मेल नहीं खा रहीं, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा। | धन्यवाद. पर्चीवरील तारखा दुकान बंद असलेल्या दिवसांशी जुळत नाहीत, म्हणून आमची टीम ती पाहील. 24 तासांत उत्तर मिळेल. | - |
| `SLIP_TO_HUMAN_UNREADABLE` | Thank you. We couldn't read the slip clearly, so our team will check it. You'll hear back within 24 hours. | धन्यवाद। पर्ची साफ़ नहीं पढ़ी जा सकी, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा। | धन्यवाद. पर्ची स्पष्ट वाचता आली नाही, म्हणून आमची टीम ती पाहील. 24 तासांत उत्तर मिळेल. | - |
| `SLIP_TO_HUMAN_DAYS` | Thank you. This claim covers more days than we pay automatically, so our team will check it. You'll hear back within 24 hours. | धन्यवाद। यह दावा अपने-आप भुगतान की दिनों की सीमा से लंबा है, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा। | धन्यवाद. हा दावा आपोआप भरपाई देण्याच्या दिवसांच्या मर्यादेपेक्षा मोठा आहे, म्हणून आमची टीम ती पाहील. 24 तासांत उत्तर मिळेल. | - |
| `INSTALMENT_PAUSED_TODAY` | Today's {instalment} instalment is paused. | आज की {instalment} की किस्त रोक दी गई है। | आज देय असलेला {instalment} चा हप्ता थांबवण्यात आला आहे. | `instalment` |
| `INSTALMENT_PAUSED_ON` | The {instalment} instalment due on {date_en} is paused. | {date_hi} की {instalment} की किस्त रोक दी गई है। | {date_mr} रोजी देय असलेला {instalment} चा हप्ता थांबवण्यात आला आहे. | `date_en`, `date_hi`, `instalment` |
| `EXPLAIN_PERSONAL` | How your claim was worked out: {formula_en} | आपके दावे का हिसाब: {formula_hi} | आपल्या दाव्याचा हिशोब: {formula_mr} | `formula_en`, `formula_hi` |
| `EXPLAIN_AREA_FORMULA` | How your payout was worked out: {formula_en} | आपके भुगतान का हिसाब: {formula_hi} | आपल्या रकमेचा हिशोब: {formula_mr} | `formula_en`, `formula_hi` |
| `PERSONAL_DECLINED` | {name_en} ji, this claim can't be paid. {reason_en} | {name_hi} जी, यह दावा मंज़ूर नहीं हो सका। {reason_hi} | {name_mr} जी, हा दावा मंजूर होऊ शकला नाही. {reason_mr} | `name_en`, `name_hi`, `reason_en`, `reason_hi` |
| `REASON_COVER_IN_FORCE` | Your cover wasn't in force on that day. | उस दिन आपका कवर चालू नहीं था। | त्या दिवशी आपले कवर सुरू नव्हते. | - |
| `REASON_PREMIUM_PREPAID` | The premium for that day hadn't been paid in advance. | उस दिन का प्रीमियम पहले से जमा नहीं था। | त्या दिवसाचे प्रीमियम आधी भरलेले नव्हते. | - |
| `REASON_SILENCE_VERIFIED` | Our records don't show your shop closed for that whole day. | हमारे रिकॉर्ड में उस दिन दुकान पूरे दिन बंद नहीं दिखी। | आमच्या नोंदींमध्ये त्या दिवशी दुकान दिवसभर बंद दिसली नाही. | - |
| `REASON_NOT_ALREADY_PAID` | That day has already been paid. | उस दिन का भुगतान पहले ही हो चुका है। | त्या दिवसाची रक्कम आधीच दिली गेली आहे. | - |
| `REASON_WITHIN_ANNUAL_LIMIT` | It would go over the yearly limit. | इससे साल की सीमा पार हो जाती। | यामुळे वार्षिक मर्यादा ओलांडली गेली असती. | - |
| `REASON_COVER_BEFORE_ALERT` | The cover was bought after the alert was issued. | कवर अलर्ट जारी होने के बाद लिया गया था। | कवर अलर्ट जाहीर झाल्यानंतर घेतले होते. | - |
| `REASON_ALERT_ACTIVE` | There was no weather alert for your area at that time. | उस समय आपके इलाके में कोई मौसम अलर्ट नहीं था। | त्या वेळी आपल्या परिसरात कोणताही हवामान अलर्ट नव्हता. | - |
| `REASON_INDEX_QUORUM` | Too few shops in your area to measure the drop. | आपके इलाके में हिसाब के लिए काफ़ी दुकानें नहीं थीं। | हिशोबासाठी आपल्या परिसरात पुरेशी दुकाने नव्हती. | - |
| `REASON_BELOW_FLOOR` | Your area's sales didn't fall below the payout level. | आपके इलाके की बिक्री भुगतान की सीमा से नीचे नहीं गिरी। | आपल्या परिसरातील विक्री भरपाईच्या पातळीखाली गेली नाही. | - |
| `REASON_BELOW_MODEL_RANGE` | Your area's sales stayed within their usual range. | आपके इलाके की बिक्री आम दायरे के अंदर रही। | आपल्या परिसरातील विक्री नेहमीच्या श्रेणीच्या आत राहिली. | - |
| `REASON_OFFICER_PERSONAL` | After checking the slip, this claim can't be paid. | पर्ची की जाँच के बाद यह दावा मंज़ूर नहीं हो सका। | पर्चीची तपासणी केल्यानंतर हा दावा मंजूर होऊ शकला नाही. | - |
| `REASON_OFFICER_DISPUTE` | Your area's numbers support the amount paid. | आपके इलाके के आँकड़ों के हिसाब से भुगतान सही था। | आपल्या परिसरातील आकड्यांनुसार रक्कम बरोबर होती. | - |
| `REASON_OFFICER_DISPUTE_PERSONAL` | The amount paid follows your policy's daily limit. | आपकी पॉलिसी की रोज़ की सीमा के हिसाब से भुगतान सही था। | आपल्या पॉलिसीच्या रोजच्या मर्यादेनुसार रक्कम बरोबर होती. | - |
| `COVER_STATUS_ACTIVE` | Your cover is active. Premium is paid through {prepaid_en}. | आपका कवर चालू है। प्रीमियम {prepaid_hi} तक जमा है। | आपले कवर सुरू आहे. प्रीमियम {prepaid_mr} पर्यंत भरलेले आहे. | `prepaid_en`, `prepaid_hi` |
| `COVER_STATUS_STARTS` | Your cover starts on {starts_on_en}. | आपका कवर {starts_on_hi} से शुरू होगा। | आपले कवर {starts_on_mr} पासून सुरू होईल. | `starts_on_en`, `starts_on_hi` |
| `COVER_STATUS_UNPAID` | Your cover is active, but the premium for the coming days hasn't been paid yet. | आपका कवर चालू है, पर आगे के दिनों का प्रीमियम अभी जमा नहीं है। | आपले कवर सुरू आहे, पण पुढील दिवसांचे प्रीमियम अजून भरलेले नाही. | - |
| `PREMIUM_PAID_STARTS` | {name_en} ji, we received your {amount} premium. Your cover starts on {starts_on_en} and is paid through {paid_to_en}. | {name_hi} जी, आपका {amount} का प्रीमियम मिल गया। आपका कवर {starts_on_hi} से शुरू होगा और {paid_to_hi} तक का प्रीमियम जमा है। | {name_mr} जी, आपले {amount} चे प्रीमियम मिळाले. आपले कवर {starts_on_mr} पासून सुरू होईल आणि {paid_to_mr} पर्यंतचे प्रीमियम भरलेले आहे. | `amount`, `name_en`, `name_hi`, `paid_to_en`, `paid_to_hi`, `starts_on_en`, `starts_on_hi` |
| `PREMIUM_PAID_ACTIVE` | {name_en} ji, we received your {amount} premium. Your cover is active and paid through {paid_to_en}. | {name_hi} जी, आपका {amount} का प्रीमियम मिल गया। आपका कवर चालू है और {paid_to_hi} तक का प्रीमियम जमा है। | {name_mr} जी, आपले {amount} चे प्रीमियम मिळाले. आपले कवर सुरू आहे आणि {paid_to_mr} पर्यंतचे प्रीमियम भरलेले आहे. | `amount`, `name_en`, `name_hi`, `paid_to_en`, `paid_to_hi` |
| `COVER_LINK_UNAVAILABLE` | The payment link couldn't be created right now. Please ask again in a little while. | भुगतान लिंक अभी नहीं बन सका। थोड़ी देर बाद फिर से पूछिए। | पेमेंट लिंक आत्ता तयार होऊ शकली नाही. थोड्या वेळाने पुन्हा विचारा. | - |
| `CHECKIN_OK` | Good to hear. If you need help, just write to me. | यह सुनकर अच्छा लगा। कोई मदद चाहिए तो बस लिखिए। | हे ऐकून बरे वाटले. काही मदत हवी असेल तर फक्त लिहा. | - |
| `CHECKIN_WHAT_HAPPENED` | What happened? If you're ill or in hospital, please tell me. | क्या हुआ? अगर आप बीमार हैं या अस्पताल में हैं, तो बताइए। | काय झाले? आपण आजारी असाल किंवा रुग्णालयात असाल, तर सांगा. | - |
| `ILLNESS_NO_SILENCE` | Get well soon. If your shop stays closed for a full business day, Chhatri will reach out to you. | जल्दी ठीक हो जाइए। अगर दुकान पूरे दिन बंद रही, तो छतरी ख़ुद आपसे संपर्क करेगी। | लवकर बरे व्हा. दुकान दिवसभर बंद राहिली, तर छत्री स्वतः आपल्याशी संपर्क करेल. | - |
| `PHOTO_NOT_NEEDED` | Thanks for the photo. There's no open claim right now. If your shop stays closed for a full business day, Chhatri will reach out. | फ़ोटो के लिए धन्यवाद। अभी कोई दावा खुला नहीं है। दुकान पूरे दिन बंद रहने पर छतरी ख़ुद संपर्क करेगी। | फोटोसाठी धन्यवाद. सध्या कोणताही दावा खुला नाही. दुकान दिवसभर बंद राहिली, तर छत्री स्वतः संपर्क करेल. | - |
| `VOICE_UNCLEAR` | Sorry, I couldn't hear that clearly. Please say it again or type it. | माफ़ कीजिए, आवाज़ साफ़ नहीं सुनाई दी। कृपया फिर से बोलिए या लिखकर भेजिए। | क्षमा करा, आवाज स्पष्ट ऐकू आला नाही. कृपया पुन्हा बोला किंवा लिहून पाठवा. | - |

### 17.1 Marathi calendar names and formula patterns

The code builds month, weekday and formula text in Hindi and English only (`MONTHS_HI`, `WEEKDAYS_HI`, `policy/explain.py`). N8 adds the Marathi counterparts below.

**Months**

| Month | Hindi (built) | Marathi (draft) |
|---|---|---|
| January | जनवरी | जानेवारी |
| February | फ़रवरी | फेब्रुवारी |
| March | मार्च | मार्च |
| April | अप्रैल | एप्रिल |
| May | मई | मे |
| June | जून | जून |
| July | जुलाई | जुलै |
| August | अगस्त | ऑगस्ट |
| September | सितंबर | सप्टेंबर |
| October | अक्टूबर | ऑक्टोबर |
| November | नवंबर | नोव्हेंबर |
| December | दिसंबर | डिसेंबर |

**Weekdays**

| Weekday | Hindi (built) | Marathi (draft) |
|---|---|---|
| Monday | सोमवार | सोमवार |
| Tuesday | मंगलवार | मंगळवार |
| Wednesday | बुधवार | बुधवार |
| Thursday | गुरुवार | गुरुवार |
| Friday | शुक्रवार | शुक्रवार |
| Saturday | शनिवार | शनिवार |
| Sunday | रविवार | रविवार |

**Formula patterns**

| Case | Hindi (built) | Marathi (draft) |
|---|---|---|
| area, not capped | `{expected} का {drop}% = {lost}; उसका आधा = {share}` | `{expected} चे {drop}% = {lost}; त्याचे निम्मे = {share}` |
| area, capped | `{expected} का {drop}% = {lost}; उसका आधा = {share}; सीमा {cap}` | `{expected} चे {drop}% = {lost}; त्याचे निम्मे = {share}; मर्यादा {cap}` |
| personal, capped | `{expected} का आधा = {per_day} प्रतिदिन; सीमा {cap} × {days} दिन = {amount}` | `{expected} चे निम्मे = {per_day} प्रतिदिन; मर्यादा {cap} × {days} दिवस = {amount}` |
| personal, not capped | `{expected} का आधा = {per_day} प्रतिदिन × {days} दिन = {amount}` | `{expected} चे निम्मे = {per_day} प्रतिदिन × {days} दिवस = {amount}` |

A date is day, space, month name: `27 अगस्त` today and `27 ऑगस्ट` in the Marathi draft. English formulas keep the `½ ×` form; the Marathi formula uses `निम्मे` for one half and `{share_pct}%` for any other share, as the Hindi formula uses `आधा`.

## 18. Appendix B: built strings and limits that the new copy relies on

Quoted exactly. A change to any of these changes the rows that point at them.

| What | Exact text or value | Where |
|---|---|---|
| Payout card detail, credited | with today’s settlement | `frontend/src/components/phone/whatHappened.ts` |
| Payout card detail, in transit | with the next settlement | `frontend/src/components/phone/whatHappened.ts` |
| Payout card detail, failed | payout failed | `frontend/src/components/phone/whatHappened.ts` |
| Instalment step detail | lender notified | `frontend/src/components/phone/whatHappened.ts` |
| Slow-day sentence | Why Zone 9 got nothing: its sales fell to 61% on a day with no weather alert. That's a slow day, not a loss event, so Chhatri doesn't pay. | `backend/chhatri/replay/board.py` |
| Recorder error, no permission | Microphone permission denied or unavailable | `frontend/src/components/phone/useRecorder.ts` |
| Recorder error, no support | This browser cannot record audio | `frontend/src/components/phone/useRecorder.ts` |
| Recording limit | MAX_RECORD_SECONDS = 30 | `frontend/src/components/phone/useRecorder.ts` |
| Recording line | Recording 0:12 / 0:30 | `frontend/src/components/phone/Composer.tsx` |
| Error title | Could not load this | `frontend/src/components/common/Status.tsx` |
| Error button | Try again | `frontend/src/components/common/Status.tsx` |
| Network error | Can’t reach the Chhatri server. Check that it is running, then try again. | `frontend/src/components/common/Status.tsx` |
| Timeout error | The Chhatri server is taking too long to answer. Try again in a moment. | `frontend/src/components/common/Status.tsx` |
| Sound toggle, off | Enable sound | `frontend/src/components/layout/SoundToggle.tsx` |
| Sound toggle, on | Sound on | `frontend/src/components/layout/SoundToggle.tsx` |
| Voice chip, why | मुझे इतने ही पैसे क्यों मिले? / Why did I get only this much? | `backend/chhatri/integrations/demo_voice.py` |
| Voice chip, dispute | मेरा नुकसान ज़्यादा हुआ। / My loss was bigger. | `backend/chhatri/integrations/demo_voice.py` |
| Voice chip, ill | मैं अस्पताल में हूँ, बुखार है। / I'm in hospital with a fever. | `backend/chhatri/integrations/demo_voice.py` |
| Voice chip, cover | Red alert tomorrow. Cover me today. | `backend/chhatri/integrations/demo_voice.py` |
| Sample slip labels | Anil's admission slip · Slip with a different name · Blurry slip | `frontend/src/components/phone/Composer.tsx` |
| Slip check, wrong document | The document is not an admission slip, discharge summary, prescription or bill. | `backend/chhatri/policy/checks.py` |
| Slip check, unclear | The slip could not be read clearly. | `backend/chhatri/policy/checks.py` |
| Slip check, clear | The slip was read clearly. | `backend/chhatri/policy/checks.py` |
| Medical document types | admission_slip, discharge_summary, prescription, bill | `backend/chhatri/policy/catalogue.py` |
| WhatsApp reply buttons | at most 3 buttons, titles at most 20 characters | `backend/chhatri/integrations/whatsapp_payloads.py` |
| Voice upload limit | audio at most 30 seconds | `backend/chhatri/api/uploads.py` |
| Image upload limit | image at most 5 MB | `backend/chhatri/api/uploads.py` |
| Rules header | Illustrative, to be set with Paytm's insurance partner and compliance teams. | `backend/chhatri/policy/rules.yaml` |
| Dispute clock | dispute_sla_hours: 24 | `backend/chhatri/policy/rules.yaml` |
| First case id after a load | C-2291 | `docs/DEMO.md` |

## 19. Review checklist for the native speaker

Marathi is a draft. Please check, in this order:

1. The term table in section 1.5, which every string depends on.
2. The honorific जी after a name (`{name_mr} जी`). Is it natural in Mumbai Marathi, or should it be another form?
3. The spelling छत्री, and the choice of रक्कम, भरपाई, हप्ता and परिसर.
4. Whether लेंडर is understood, or whether कर्ज देणारी संस्था reads better in the first mention.
5. The SOUNDBOX line. The built Hindi line is romanised (`Paytm par ... prapt hue`). The Marathi draft is in Devanagari, which a speaker reads better; confirm what the Soundbox display and the voice need.
6. The month, weekday and formula names in section 17.1.
7. Gendered verbs. The drafts use forms that are the same for every speaker (`पाठवत आहे`, `समजावून सांगता येते`).
8. Every counterfactual (section 6): the conditional mood (`असते`, `असती`) must read as a plain "if", never as a promise.

## Open questions

1. Who reviews Marathi, and when? Needed before wave 4 ships N8. Owner: Omkar Kadam.
2. Who reads the new Hindi lines outside the team? Owner: Omkar Kadam.
3. The helpline number and portal address for `scam.report` are configuration, not text. They must be checked against the official source before the first use. Owner: Omkar Kadam.
4. `grv.clock.portal` shows the figure that the Bima Bharosa portal states. Check it again at release. Owner: Omkar Kadam.
5. The respondent split in section 13.2 (insurer, Paytm, lender, Chhatri) needs the partners' confirmation. Owner: Omkar Kadam.
6. Which fields survive "forget my slip"? `slip.erase.removes` and `slip.erase.keeps` state the proposal of the cover and consent spec: the photo and the read fields go, the decision and the audit entry stay. Owner: Ujjwal Pardeshi with compliance.
7. The built DISPUTE_ACK says `भेज रहा हूँ`, a masculine form. New lines avoid it. Changing the built line means changing the catalogue, `DEMO.md`, the tests and this deck together. Owner: Omkar Kadam.
8. Where does TALK_TO_TEAM lead? The Ask Chhatri spec opens the dispute button for a merchant who has a decision and falls back to ASK_AGAIN for everyone else until N5 (wave 3). No case kind carries a general question (PERSONAL_CLAIM_REVIEW, DISPUTE and AREA_REVIEW do not fit). Owner: Ujjwal Pardeshi.
9. The tracker can show the lender's reason in plain words (`TRACK_EDI_REFUSED_WHY`) or leave it out. The EDI holiday spec shows it and the mini-app spec leaves it out (section 1.8). Pick one. Owner: Omkar Kadam with Ujjwal Pardeshi.
10. Real WhatsApp needs approved templates for most business-initiated messages. Only `chhatri_area_payout` and `chhatri_checkin` exist in the code, so the reply buttons of section 8.3 apply inside the 24 hour session only. Owner: Ujjwal Pardeshi.
11. The mini-app spec and the policy engine spec list different source kinds (section 1.8). Make them one list. Owner: Ujjwal Pardeshi with Omkar Kadam.
12. The slip notice and the voice notice both name outside services. With no key set nothing leaves the app, so the lines say may. A pilot needs the providers' retention terms before any real slip or voice is sent. Owner: Omkar Kadam.

## Changelog

- 2026-10-02 · v1 · first version: all new P0 strings in three languages, Marathi drafts for the 51 built keys, built text quoted exactly
