# Conversation design

| | |
|---|---|
| Status | Draft v1 · 2 Oct 2026 |
| Owner | Omkar Kadam |
| Audience | Merchants, support staff, UX designers, product teams evaluating bilingual fintech |
| Related | [Product requirements](../02-product/prd.md) · [Feature specs](../02-product/feature-specs/fs-05-ask-chhatri.md) · [Features fs-04 and fs-05](../02-product/feature-specs/) · [Current audit](../01-strategy/current-state-audit.md) · [Facts and sources](../01-strategy/facts-and-sources.md) |

## TL;DR

- Chhatri speaks respectful, simple Hindi first (आप), with English always beside it. Numbers as digits; amounts in ₹ with Indian grouping.
- Nine intents: WHY_AMOUNT, DISPUTE_AMOUNT, REPORT_ILLNESS, BUY_COVER, COVER_STATUS, GREETING, AFFIRM, DENY, UNKNOWN. Rules first; Sarvam chat (free credits) for UNKNOWN.
- Guard stops any claim to pay money or approve unless those numbers appear in the decision facts.
- Five channels: WhatsApp simulator, Soundbox payout announcement, mini-app, Ask Chhatri, console.
- Proactive messages capped at 1 per day (X8) except replies. Escalation to a person is always offered for disputes.
- Proposed new copy: EDI-holiday wording, mini-app screens, slip pre-check retake flow, Ask Chhatri hand-off.
- Marathi (N8) roadmap: 5 sample strings from the catalogue, to be checked by a native speaker.

## 1. Voice and tone

**Respectful आप.** Every merchant message uses the formal second person आप ("you"), never तु, with the honourific जी after their name. Every shop owner is addressed by their given name (`merchant.owner_name_hi` / `merchant.owner_name`), e.g. "अनिल जी" / "Anil ji".

**Simple, everyday Hindi and English.** Sentences are short (one idea per message). Vocabulary is concrete — say पर्ची ("slip", "document") not दस्तावेज़ ("document" but technical); बंद ("closed") not बन्द. Devanagari script throughout the Hindi text (no Hinglish in merchant-facing messages). English is plain: "Get well soon", never "expedite your recovery".

**Numbers as digits.** Always write ₹1,380, not "one thousand three hundred eighty rupees". Grouping follows Indian convention: ₹1,58,900. Dates in Hindi: "27 अगस्त" (day, space, month name in `MONTHS_HI` from `messages.py`). Percentage as integer: 63%, never 63.2 %.

**No jargon for low literacy.** No "premium", say "रोज़ की रक़म" ("daily amount") or show the number. No "claim", say "दावा" (the noun a merchant uses). No "policy", say the rule directly: "रोज़ की ₹600 की सीमा" ("₹600 daily limit").

## 2. Channels and routing

| Channel | Used for | Merchant sees | Notes |
|---|---|---|---|
| **WhatsApp Cloud API (Simulated today)** | Payout notifications (template), check-in (template), Q&A, disputes, voice | Hindi text + English, voice notes (TTS), card (payout amount + badge) | SIMULATED in demo (no Cloud API keys). Plan: outside 24-hour window, approved templates (SPEC §14.2). Send voice notes as OGG/Opus. See INTEGRATIONS.md for template registration. |
| **WhatsApp phone simulator (Simulated)** | Same as live | Same | In-console phone at `/merchant/{id}`. All non-demo merchants routed here. Text or voice chips (canned: why, dispute, ill, cover). |
| **Soundbox (Simulated)** | Payout announcement (broadcast) | Spoken Paytm announcement: "₹1,380 प्राप्त हुए — Chhatri से" | Hindi number name read by TTS or fallback Paytm audio. Audited as `soundbox` event. |
| **Merchant mini-app (N1, planned) | Cover status, claim tracker, ask, dispute, grievance, consent | Home card · Coverage explainer · Buy screen · Tracker (Detected → Checked → Decided → Paid → EDI holiday) · Help escalation ladder | Hindi-first with English toggle. Screens wireframed in `/design/screens-and-flows.md` (to be designed). |
| **Ask Chhatri (N2, planned)** | Coverage questions, claim questions | Chat UI; merchant asks "क्या गर्मी में भी कवर होता है?" ("Is cover active during heat?") → grounded answer citing C3 (coverage clause) + merchant's own facts | Text + voice (Sarvam STT). Fallback: "हमारी टीम से बात करिए" ("Talk to our team"). |
| **Claims officer console** | Operator uses `/claims` queue to review, approve or decline REFERRED cases | Only officer sees; case C-2291 with slip image, extracted fields, KYC match score, silent days | Audit trail preserved. |

## 3. Message catalogue

### 3.1 How it works

Every merchant-facing message is rendered from the catalogue in `backend/chhatri/conversation/messages.py` using two functions:

**`render(key, lang, **facts)`:** fills a template with facts and returns a string in the given language (hi or en). Example:

```python
render("AREA_PAYOUT_INTRO", "hi", name_hi="अनिल", drop=63)
# → "अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री 63% गिरी।"
```

**`bilingual(key, **facts)`:** returns a tuple `(hindi, english)` — the deck's bilingual line. Example:

```python
bilingual("AREA_PAYOUT_INTRO", name_hi="अनिल", name_en="Anil", drop=63)
# → ("अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री 63% गिरी।", 
#    "Anil ji, heavy rain cut your area's sales by 63% today.")
```

Money figures are formatted once (with `format_inr`) and passed as pre-formatted strings (e.g., `instalment="₹600"`), never as paise or floats.

### 3.2 Catalogue (SPEC §13.4 contract table)

The 16 deck-specified keys and their Hindi / English lines, verbatim:

| Key | Hindi | English | Facts required |
|---|---|---|---|
| AREA_PAYOUT_INTRO | {name_hi} जी, आज भारी बारिश से आपके इलाके की बिक्री {drop}% गिरी। | {name_en} ji, heavy rain cut your area's sales by {drop}% today. | name_hi, name_en, drop |
| PAYOUT_CARD | आज के सेटलमेंट के साथ जमा | Credited with today's settlement | — |
| INSTALMENT_PAUSED | कल की {instalment} की किस्त रोक दी गई है। | Tomorrow's {instalment} instalment is paused. | instalment |
| SOUNDBOX | Paytm par {amount} prapt hue — Chhatri se | {amount} received on Paytm, from Chhatri | amount |
| CHECKIN_SILENT | {name_hi} जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है? | Your shop has been closed since yesterday. Is everything okay? | name_hi, name_en |
| ASK_SLIP | जल्दी ठीक हो जाइए। अस्पताल की पर्ची की एक फ़ोटो भेज दीजिए। | Get well soon. Please send one photo of the hospital slip. | — |
| PERSONAL_PAID | {name_hi} जी, आपका दावा मंज़ूर है। {amount} आज के सेटलमेंट के साथ जमा। | {name_en} ji, your claim is approved. {amount} credited with today's settlement. | name_hi, name_en, amount |
| SLIP_TO_HUMAN | धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा। | Thank you. The name on the slip doesn't match your KYC, so our team will check it. You'll hear back within 24 hours. | — |
| EXPLAIN_AREA | आपका आम {weekday_hi}: {expected}। आज आपके इलाके की बिक्री {drop}% गिरी। छतरी खोई हुई बिक्री का आधा देती है। | Your usual {weekday_en}: {expected}. Your area fell {drop}%. Chhatri pays half the lost sales. | weekday_hi, weekday_en, expected, drop |
| DISPUTE_ACK | ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा। | Okay, I'm sending this to our team. You'll hear back within 24 hours. | — |
| CASE_CHIP | — (no Hindi) | Sent to a claims officer · case {case_id} | case_id |
| COVER_BLOCKED | नया कवर वेटिंग पीरियड के बाद शुरू होता है — {starts_on_hi} से। कल के अलर्ट पर यह लागू नहीं होगा। | New cover starts after the waiting period — from {starts_on_en}. It won't apply to tomorrow's alert. | starts_on_hi, starts_on_en |
| COVER_LINK | आगे के लिए कवर लेना हो तो {first_payment} ({per_day}/दिन) यहाँ भरें: {url} | To buy cover for later, pay {first_payment} ({per_day}/day) here: {url} | first_payment, per_day, url |
| OFFICER_APPROVED | {name_hi} जी, हमारी टीम ने आपका दावा मंज़ूर किया। {amount} जमा। | {name_en} ji, our team approved your claim. {amount} credited. | name_hi, name_en, amount |
| OFFICER_DECLINED | {name_hi} जी, हमारी टीम ने आपका दावा देखा। {reason_hi} | {name_en} ji, our team reviewed your claim. {reason_en} | name_hi, name_en, reason_hi, reason_en |
| FALLBACK_HELP | मैं छतरी हूँ। आप पूछ सकते हैं: "मुझे इतने पैसे क्यों मिले?" या "मेरा नुकसान ज़्यादा हुआ"। | I'm Chhatri. You can ask: "Why did I get this amount?" or "My loss was bigger". | — |

Extensions (flows, pre-checks, decline reasons) are in `messages.py` with the same voice: `SLIP_TO_HUMAN_DATES`, `SLIP_TO_HUMAN_UNREADABLE`, `SLIP_TO_HUMAN_DAYS`, `EXPLAIN_PERSONAL`, `EXPLAIN_AREA_FORMULA`, `PREMIUM_PAID_STARTS`, `PREMIUM_PAID_ACTIVE`, `COVER_STATUS_ACTIVE`, `COVER_STATUS_STARTS`, `COVER_STATUS_UNPAID`, `INSTALMENT_PAUSED_TODAY` / `_ON`, `REASON_COVER_IN_FORCE`, `REASON_PREMIUM_PREPAID`, `REASON_SILENCE_VERIFIED`, `REASON_NOT_ALREADY_PAID`, `REASON_WITHIN_ANNUAL_LIMIT`, `REASON_COVER_BEFORE_ALERT`, `REASON_ALERT_ACTIVE`, `REASON_INDEX_QUORUM`, `REASON_BELOW_FLOOR`, `REASON_BELOW_MODEL_RANGE`, `CHECKIN_OK`, `CHECKIN_WHAT_HAPPENED`, `ILLNESS_NO_SILENCE`, `PHOTO_NOT_NEEDED`, `VOICE_UNCLEAR`.

## 4. Intent detection (9 intents)

**Priority order** (`PRIORITY` tuple in `intents.py`): the list controls which intent wins when text matches multiple rules.

| Intent | Rule | Example |
|---|---|---|
| DISPUTE_AMOUNT | Loss + "more", disagreement ("गलत", "wrong", "review"), "not enough" (not a why-question), or "should get more money" | "मेरा नुकसान ज़्यादा हुआ" ("My loss was bigger") |
| WHY_AMOUNT | Why-word + amount word, or "explain" / "हिसाब" | "मुझे इतने ही पैसे क्यों मिले?" ("Why did I get this much?") |
| REPORT_ILLNESS | Hospital, fever, ill, accident (ILLNESS concept in lexicon) | "मैं अस्पताल में हूँ, बुखार है" ("I'm in hospital with a fever") |
| COVER_STATUS | Cover word + status word (active, कब, "do I have") | "मेरा कवर चालू है क्या?" ("Is my cover active?") |
| BUY_COVER | Cover word + buy word ("दे दो", "buy") | "Red alert tomorrow. Cover me today." |
| DENY | Whole message is only deny words (नहीं, नहीं है, not OK) + fillers | "नहीं" ("No") |
| AFFIRM | Whole message is only affirm words (हाँ, जी, OK, ठीक है) + fillers | "ठीक है" ("Okay") |
| GREETING | Whole message is only greeting words (नमस्ते, hello) + fillers | "नमस्ते" ("Hello") |
| UNKNOWN | None of the above | "फ़ोटो भेज दिया" (sent a photo, no intent) |

**LLM fallback.** When a merchant's text is classified UNKNOWN and a `ChatModel` is available (Sarvam `sarvam-105b` with free credits), the message is sent to the model with the intent schema (SPEC §13.2). The model's reply is accepted only if it is exactly one of the intent values; on any error the rules' UNKNOWN stands and a warning is logged (the merchant's text is never logged).

## 5. Guard (grounding, promises, references)

The `guard.py` module enforces SPEC §0.2 "Every money number shown to a merchant is reproducible from the numbers shown next to it".

**Digit check.** Any free-text LLM reply (Ask Chhatri, intent LLM, future extensions) must not contain a digit sequence that is not in the decision facts. Devanagari digits are folded to ASCII; ₹1,380 and "1380" match. An extra half ("₹1,380.50") brings in "50" which must be in the facts.

**Promise check.** The reply must not promise money or approval (Hindi, English, Hinglish phrasings like "approved", "will pay", "गारंटी", "पक्का", "मिल जाएंगे", "pass ho jayega"). Match list in `PROMISE` concept in `guard.py`. If a violation is found, the caller falls back to a template.

**Examples that fail the guard:**
- "आपको ₹1,500 की जगह ₹2,000 देंगे" (₹2,000 not in decision) → fallback to DISPUTE_ACK template.
- "आपका दावा ज़रूर मंज़ूर होगा" (promise "जरूर मंजूर", "will definitely be approved") → fallback.

## 6. Proactive messaging and X8 cap

**Rule X8:** Proactive messages (business-initiated outreach) are capped at 1 per day per merchant, except payment confirmations and replies to inbound messages. No loan, top-up or cross-sell message or card appears while an alert covers the merchant's zone, while a claim is open, or while a dispute is open (SPEC §24.4 §X8).

**Proactive flows:**
- **Silent check-in** (11:20 next day): CHECKIN_SILENT template only (WhatsApp, approved for 24-hour window).
- **Payout announcement** (17:04): AREA_PAYOUT_INTRO + PAYOUT_CARD (free-form within 24 h; outside it use `chhatri_area_payout` template). Soundbox event.
- **Personal payout and officer approval**: PERSONAL_PAID or OFFICER_APPROVED (free-form). Soundbox event.
- **Instalment pause** (17:05 or +5 min): INSTALMENT_PAUSED / INSTALMENT_PAUSED_TODAY / INSTALMENT_PAUSED_ON (free-form).
- **Premium payment confirmation** (on Paytm callback): PREMIUM_PAID_STARTS or PREMIUM_PAID_ACTIVE (free-form, filled with payout decision facts).
- **EDI holiday request outcome** (future N3 feature): "The lender decided to / did not pause your instalment. Here's why: ...".

**Justification for 1 message/day:** Merchant fatigue and reducing message spam in a low-bandwidth market. Payout announcements (Soundbox + WhatsApp) and urgent escalations (officer approval) are necessary; silencing them risks trust loss. The daily cap excludes replies (the merchant initiated) and confirmations (passive acknowledgments).

## 7. Voice UX (N4 speech, simulated or Sarvam)

### 7.1 Input: speech-to-text (STT)

- **Live (Sarvam Saaras v3 or v4):** merchant records voice up to 30 s; sent to `client.speech_to_text.transcribe` with `language_code="hi-IN"` (or "unknown" for mixed language) and `input_audio_codec="opus"` (WhatsApp) or `"webm"` (browser). Returns `.transcript`, `.language_code`, `.language_probability`.
- **Simulated:** four canned transcripts (demo voice keys) — `why`, `dispute`, `ill`, `cover`. Merchant taps a chip; the transcript is injected.
- **Fallback to text:** if STT fails (quota exhausted, timeout), the merchant is offered tap-to-send chips (AFFIRM, DENY, UNKNOWN reply, or a re-ask chip).

### 7.2 Interaction model: chips and confirmation

- **Chips:** merchant sees up to 3 reply buttons, e.g. "Why did I get this?" (blue) · "My loss was bigger" (red) · "OK, thanks" (grey).
- **Tap:** merchant taps a chip → voice recording starts (browser `MediaRecorder` or WhatsApp voice record UI).
- **Confirmation loop:**
  - "I heard: 'मेरा नुकसान ज़्यादा हुआ' (My loss was bigger). Is that right?"
  - Chips: "Yes" (green) · "No, I'll type it" (red).
  - If no: text input fallback.
- **Slow speech:** TTS playback can be slowed on the merchant's device (browser `playbackRate` control or WhatsApp audio player speed).
- **Silence or noise:** if the transcript is empty or confidence is very low, offer re-record or text.

### 7.3 Output: text-to-speech (TTS)

- **Live (Sarvam Bulbul v3):** the merchant's local language reply (Hindi or English) is sent to `client.text_to_speech.convert(text=…, language_code="hi-IN", model="bulbul:v3", speaker="ritu", output_audio_codec="mp3")` (browser) or `"opus"` (WhatsApp OGG). Returns base64 audio.
- **Simulated:** browser `speechSynthesis` API (Hindi voice selection when available; English fallback).
- **Playback:** auto-play in WhatsApp voice note; in the console/mini-app, show a play button. Caption text always displayed.

## 8. Repair strategies

| Scenario | Merchant sees | Next step |
|---|---|---|
| Intent not recognised ("फ़ोटो भेज दिया", a statement) | FALLBACK_HELP: "I'm Chhatri. You can ask: 'Why did I get this amount?' or 'My loss was bigger'." Chips for those two intents. | Merchant re-asks or says something new. |
| Wrong intent (merchant says "हाँ" to REPORT_ILLNESS but means "yes, I'm OK") | CHECKIN_OK: "Good to hear. If you need help, just write." Chips: "Ask Chhatri", "Open a dispute". | Merchant can course-correct. |
| Angry merchant ("गलत है! जालसाज़ी है!" — "This is wrong! Fraud!") | Classified as DISPUTE_AMOUNT → DISPUTE_ACK (escalation to human). Case opened. | Officer reviews; tone is never defensive. |
| Merchant insists on a person ("बिना बात किए पैसे नहीं मिले, टीम को कहो") | DISPUTE_AMOUNT → escalation. Or if asking for help: Ask Chhatri first, then "हमारी टीम से बात करिए" (escalate to officer/grievance). | Case CL-2291 opened with evidence. |
| Voice unclear or clipped | VOICE_UNCLEAR: "Sorry, I couldn't hear that clearly. Please say it again or type it." Text box + retry chip. | Merchant retypes or re-records. |
| Photo sent when not asked | PHOTO_NOT_NEEDED: "Thanks for the photo. There's no open claim right now. If your shop stays closed for a full business day, Chhatri will reach out." | No action; no claim opened. |

## 9. Escalation phrases

When a merchant's concern cannot be resolved by the system (dispute, name mismatch, appeal):

- **WhatsApp / mini-app:** "मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा।" / "I'm sending this to our team. You'll hear back within 24 hours." A case is opened with `due_by = now + 24 hours`.
- **Ask Chhatri limits:** if a question is outside the scope (coverage, claim decision facts) or the model cannot ground the answer, offer "हमारी टीम से बात करिए" / "Talk to our support team." Route to the officer console or a grievance opener.
- **Grievance ladder (N5, future):** GRO → Bima Bharosa → Insurance Ombudsman, each with an SLA clock shown in the mini-app tracker.

## 10. Proposed new copy and change requests

### 10.1 EDI-holiday wording (K3 reframing)

**Current (problematic):** "कल की ₹600 की किस्त रोक दी गई है" suggests Chhatri paused the loan unilaterally.

**Proposed new key:** `INSTALMENT_HOLIDAY_LENDER_DECIDES`

```
Hindi: {name_hi} जी, आपके लेंडर ने आपकी अगली किस्त को रोकने की अनुमति दी है।
       कल की {instalment} की किस्त {expected_date} तक के लिए रोक दी गई है।
English: {name_en} ji, your lender has approved a pause on your next instalment.
         The instalment due tomorrow ({date_label}) is paused until {extended_date}.
Facts: name_hi, name_en, instalment (amount), expected_date (formatted), date_label (en), extended_date (formatted)
```

This makes the lender's role explicit: the lender decides whether to pause the instalment based on the merchant's loan status and its pre-agreed policy.

[Status: PROPOSED (post-hackathon — conditional on lender integration; not yet implemented in messages.py or DEMO.md.)]

### 10.2 Mini-app screens (N1) copy

Five screens, bilingual, short actions:

**1. Home / Cover card**
- Title: "आपका कवर / Your cover"
- Status: COVER_STATUS_ACTIVE / COVER_STATUS_STARTS / COVER_STATUS_UNPAID (from catalogue)
- Buttons: "कवरेज देखें / See coverage" · "सहायता / Help"

**2. Coverage explainer ("क्या कवर है / What's covered")**
- Headline: "आय की सुरक्षा / Income protection"
- Two types (bilingual headers):
  - "बारिश में बिक्री का नुकसान / Loss during heavy rain" — threshold, area index, payout formula (50% of drop), ₹2,500 cap.
  - "अस्पताल में आय का नुकसान / Income loss while hospitalized" — one photo required, ₹1,500 cap, up to 3 days.
- "क्या कवर नहीं है / Not covered": fire/theft (separate product); cancel cover ≥7 days old.
- Close button: "समझ गया / Got it"

**3. Claim tracker (emerging, one item per state)**
- Each claim shows: date, type, step (Detected / Checked / Decided / Paid / EDI holiday), icon + label, plain reason in 1 line, next step + ETA.
- Example item: "19 अगस्त · बारिश का नुकसान / Aug 19 · Rain loss" | "Checked · Your shop's sales fell 63%" | "Decision: should arrive by 17:05" | (accepted decision shows amount).

**4. Ask a question (text + voice)**
- Input: "कवर लिए हुए कितने दिन हुए?" / "How long have I had cover?"
- Output: grounded answer from Ask Chhatri (N2), or "हमारी टीम से पूछिए" / "Ask our support team" (escalation).

**5. Help and grievance**
- "मेरा सवाल है / I have a question" → Ask Chhatri
- "मेरे दावे पर असहमत हूँ / I disagree with my claim decision" → Open case, show SLA clocks
- "अपनी कहानी सुनाऊँ / Tell my story" → free-text to GRO (future).

### 10.3 Ask Chhatri hand-off (N2 prompt)

When a merchant's question is outside the scope of the `GROUNDED` policy (A19), the AI must hand off:

**Proposed handoff template:**
```
Hindi: धन्यवाद आपके सवाल के लिए। यह सवाल हमारी टीम के साथ ज़्यादा अच्छा होगा।
       उन्हें भेज देते हैं?
English: Thanks for your question. Our team can help with this better.
         Should I send this to them?
Chips: "हाँ, भेज दो / Yes, send" · "नहीं, थीक है / No, I'm OK"
```

On "Yes": case opened as HANDOFF kind; officer queue shows it. On "No": end the conversation.

### 10.4 Hospital slip pre-check (N3, slip extraction retake flow)

When a merchant sends a slip photo, the vision model extracts four fields: patient name, admission/discharge dates, hospital, document type. A pre-check runs before the policy engine:

**Proposed new key:** `SLIP_PRECHECK_SHOW_FIELDS`
```
Hindi: खुशी है! पर्ची पढ़ गई। कृपया देख लीजिए:
       रोगी: {patient_name} ({confidence}%)
       अस्पताल: {hospital}
       दिन: {admission_date} - {discharge_date}
       सब ठीक है? (Confidence shown as % for transparency)
English: Great! We read the slip. Please check:
         Patient: {patient_name} ({confidence}%)
         Hospital: {hospital}
         Dates: {admission_date} - {discharge_date}
         Is that right?
Chips: "हाँ / Yes, correct" · "नहीं, फिर से भेज दूँ / No, I'll resend"
```

If "No": merchant re-takes photo. If confidence < 80%, suggest retake without asking: "फ़ोटो साफ़ नहीं दिख रही। फिर से भेज दीजिए।" / "The photo is unclear. Please retake it."

## 11. Marathi (N8 roadmap)

Support for Mumbai merchants (35% of the city, unverified estimate). Use the same catalogue structure; keys map to Marathi templates checked by a native speaker (future). Sample 5 strings:

| Hindi | Marathi (to be checked by native speaker) |
|---|---|
| {name_hi} जी, आज भारी बारिश से आपके इलाके की बिक्री {drop}% गिरी। | {name_mr} जी, आज जोरदार पाऊस आपल्या इलाक्यातील विक्रय {drop}% घालून गेली। |
| जल्दी ठीक हो जाइए। अस्पताल की पर्ची की एक फ़ोटो भेज दीजिए। | लवकर बरं व्हा जा। रुग्णालयाची पर्ची एक फोटो पाठवा. |
| धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा। | धन्यवाद। पर्चीवरील नाव आपल्या KYC बरोबर जुळत नाही। |
| ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा। | ठीक आहे, मी हे आमच्या टीमला पाठवित आहे। 24 तासांत उत्तर मिळेल। |
| आपका कवर {starts_on_hi} से शुरू होगा। | आपला कवर {starts_on_mr} पासून सुरु होईल। |

**Approach:** Hire a Marathi speaker to review; test with 2–3 native Mumbai merchants; deploy incrementally on a feature flag. Dates, numbers and merchant names are inserted by the same code, so no new logic is needed.

## 12. Sample dialogues by journey

**Journey J3: Silent shop check-in → personal claim (illness, happy path)**

Scenario: `illness` (Wed 20 Aug silent, Thu 21 Aug outreach).

```
11:20 System: CHECKIN_SILENT
  Hindi: "अनिल जी, आपकी दुकान कल से बंद दिख रही है। सब ठीक है?"
  English: "Your shop has been closed since yesterday. Is everything okay?"
  Chips: [Why did you ask? (AFFIRM)] [Something's wrong (REPORT_ILLNESS)]
  
Merchant taps chip: REPORT_ILLNESS voice recording → "मैं अस्पताल में हूँ, बुखार है"
Intent: REPORT_ILLNESS (rules)

System: ASK_SLIP
  "जल्दी ठीक हो जाइए। अस्पताल की पर्ची की एक फ़ोटो भेज दीजिए।"
  "Get well soon. Please send one photo of the hospital slip."
  
Merchant: [upload slip anil_admission_slip.png]

System: SLIP_PRECHECK_SHOW_FIELDS (proposed)
  "खुशी है! पर्ची पढ़ गई। कृपया देख लीजिए:
   रोगी: Anil R. Jadhav (92%)
   अस्पताल: KEM Hospital, Parel
   दिन: 2025-08-20 - 2025-08-20
   सब ठीक है?"
  Chips: [हाँ / Yes] [नहीं, फिर से भेज दूँ / No, resend]

Merchant: [हाँ / Yes]

Policy engine: APPROVED ₹1,500 (formula ½ × ₹4,300 capped at ₹1,500 × 1 day)

System (at +4 min): PERSONAL_PAID + PAYOUT_CARD + Soundbox
  "अनिल जी, आपका दावा मंज़ूर है। ₹1,500 आज के सेटलमेंट के साथ जमा।"
  "Anil ji, your claim is approved. ₹1,500 credited with today's settlement."
  Soundbox: "Paytm par ₹1,500 prapt hue — Chhatri se"
  
System (at +5 min): INSTALMENT_PAUSED_TODAY
  "आज की ₹600 की किस्त रोक दी गई है।"
  "Today's ₹600 instalment is paused."

[Status: lines marked EXISTING in the catalogue; SLIP_PRECHECK_SHOW_FIELDS and INSTALMENT_PAUSED_TODAY are new.]
```

**Journey J4: Area payout + why-amount question (area claim)**

Scenario: `monsoon` (17:00 trigger).

```
17:04 System: AREA_PAYOUT_INTRO + PAYOUT_CARD + Soundbox
  "अनिल जी, आज भारी बारिश से आपके इलाके की बिक्री 63% गिरी।"
  Payout card: "₹1,380 · आज के सेटलमेंट के साथ जमा · No claim needed"

Merchant (at 17:12): Taps chip WHY_AMOUNT voice → "मुझे इतने ही पैसे क्यों मिले?"
Intent: WHY_AMOUNT (rules)

System: EXPLAIN_AREA
  "आपका आम मंगलवार: ₹4,380। आज आपके इलाके की बिक्री 63% गिरी। छतरी खोई हुई बिक्री का आधा देती है।"
  "Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales."
  [Console shows formula: ½ × ₹4,380 × 63% = ₹1,380]
  Chips: [Thank you (AFFIRM)] [I still disagree (DISPUTE_AMOUNT)]

Merchant: [I still disagree]
Intent: DISPUTE_AMOUNT (rules)

System: DISPUTE_ACK
  "ठीक है, मैं इसे हमारी टीम को भेज रहा हूँ। 24 घंटे में जवाब मिलेगा।"
  Case C-2291 opened.

[Status: all lines EXISTING.]
```

**Journey J5: Cover purchase blocked (alert active)**

Scenario: `buy_cover` (Mon 18 Aug 18:00, alert issued 17:30).

```
Ramesh (S-0907, not covered, Z3): "Red alert tomorrow. Cover me today."
Intent: BUY_COVER (rules: "cover" + "buy")

System: policy engine evaluate_cover_purchase(merchant, now, alerts, forecasts)
  Alert A-20250818-01 is in the feed: issued 17:30 (< now), valid 14:00–20:00 (alert.valid_from < now + 72h lookahead).
  Result: BLOCKED

System: COVER_BLOCKED + COVER_LINK
  "नया कवर वेटिंग पीरियड के बाद शुरू होता है — 25 अगस्त से। कल के अलर्ट पर यह लागू नहीं होगा।"
  "New cover starts after the waiting period — from 25 August. It won't apply to tomorrow's alert."
  
  "आगे के लिए कवर लेना हो तो ₹424.80 (₹14.16/दिन) यहाँ भरें: https://paytm.me/sim-XXXXX"
  "To buy cover for later, pay ₹424.80 (₹14.16/day) here: …"

[Status: COVER_BLOCKED EXISTING; COVER_LINK existing; regulatory position (B3) reframes what "pause" means in context.]
```

**Journey J6: Slip with name mismatch (operator approval)**

Scenario: `illness_mismatch` (Thu 21 Aug, slip patient "Sunil Pawar").

```
Anil: [upload slip mismatch_admission_slip.png]
Vision: Extracted name "Sunil Pawar" (confidence 88%)

Policy engine: NAME_MATCHES_KYC check fails (token_set_ratio("SUNIL PAWAR", "ANIL RAMESH JADHAV") = 42 < 85)

Decision: REFERRED (soft fail) + case C-2291 opened

System: SLIP_TO_HUMAN (different reason text variant)
  "धन्यवाद। पर्ची पर नाम आपके KYC से मेल नहीं खा रहा, इसलिए हमारी टीम इसे देखेगी। 24 घंटे में जवाब मिलेगा।"
  Case chip: "Sent to a claims officer · case C-2291"

Officer (in /claims console): Opens C-2291, sees slip image, extracted fields, KYC name, match score (42%), silent dates.
Evidence bundle includes a counterfactual: "Approved automatically when the name on the slip matches your KYC."

Officer: Taps [Approve]. Re-runs HARD checks (COVER_IN_FORCE, PREMIUM_PREPAID, SILENCE_VERIFIED all pass).

New decision: APPROVED ₹1,500 (decided_by="officer:...") at 11:24.

System (at 11:28, +4 min): OFFICER_APPROVED
  "अनिल जी, हमारी टीम ने आपका दावा मंज़ूर किया। ₹1,500 जमा।"
  Payout card + Soundbox.

[Status: all lines EXISTING; shows human loop.]
```

**Journey J8: EDI holiday request outcome (future N3 scenario)**

Scenario: payout decision made; lender decides on EDI pause.

```
Decision: APPROVED ₹1,380 (area claim, 17:00)
Workflows: payout → pause_instalment (lender agrees) → notify

System (at 17:05): INSTALMENT_HOLIDAY_LENDER_DECIDES (proposed)
  "अनिल जी, आपके लेंडर ने आपकी अगली किस्त को रोकने की अनुमति दी है।
   कल की ₹600 की किस्त 29 अगस्त तक के लिए रोक दी गई है।"
  "Anil ji, your lender has approved a pause on your next instalment.
   The instalment due tomorrow (₹600) is paused until 29 August."

Alternative (lender declines): "आपके लेंडर ने किस्त रोकने से इंकार कर दिया है।
   अगर आप कर्ज़ में परेशानी में हैं, तो हमारी टीम से बात करिए।"

[Status: proposed new copy; contingent on lender integration; tested in pilot.]
```

## 13. Content rules for low literacy

When writing or updating the catalogue:

1. **One idea per message.** Never combine two facts: "आपका दावा मंज़ूर है और ₹1,500 जमा है" is two messages: "आपका दावा मंज़ूर है।" then "₹1,500 आज के सेटलमेंट के साथ जमा।"

2. **Numbers first, then explanation.** "₹1,380 मिल गया क्योंकि..." ("₹1,380 because...") not "हमने आपकी हिसाब देखा और ₹1,380 देने का फैसला लिया" (past tense, passive, explanation buried).

3. **No jargon; use merchant words.** नियम (rule) → सीमा (limit) or "रोज़ के पैसे"; प्रीमियम (premium) → "रोज़ की रक़म"; दस्तावेज़ (document) → पर्ची (slip); पॉलिसी (policy) → कवर (cover).

4. **Short sentences.** Max 12 words per line. Good: "आपका दावा मंज़ूर है।" vs Bad: "आपका जो दावा आपने अस्पताल की पर्ची के साथ किया है उसे हमारी टीम ने देखा और मंज़ूर कर दिया है।"

5. **Active voice.** "₹1,380 जमा किया गया" (passive, bureaucratic) → "₹1,380 जमा" or "आपको ₹1,380 मिल गया" (active, conversational).

6. **No abbreviations or acronyms** in merchant text. Write KYC spelled (rarely shown to merchants); always spell EDI as "किस्त की रुकावट" / "instalment pause".

## Open questions

1. Should Ask Chhatri (N2) be voice-first or text-first in the mini-app? Voice needs a "listening" UI. Owner: Omkar Kadam.
2. What is the right number of proactive messages per day? N8 (Marathi) translations — how to source and validate? Owner: Omkar Kadam.
3. Should the pre-check (N3) show confidence % to the merchant, or just indicate "clear" / "blurry"? (Transparency vs simplicity.) Owner: Ujjwal Pardeshi.

## Changelog

- 2026-10-02 · v1.3 · second fact-check pass: clarified WhatsApp is SIMULATED today (no Cloud API keys)
- 2026-10-02 · v1.2 · logic and truth audit fixes
- 2026-10-02 · v1.1 · fact-check pass: removed an internal reference, expanded lender role explanation
- 2026-10-02 · v1 · first draft, from SPEC §13, intents, guard, messages.py and INTEGRATIONS.md
