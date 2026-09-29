# Chhatri Demo Script (SPEC §0, §13, §17)

**Duration**: 4–5 minutes live (no internet needed; all data offline)

**Setup**: `make dev` (backend + frontend running), or `make up` (Docker)

---

## Pre-Demo Checklist

- [ ] Wifi **off** or presenter note warning judges (demo is 100% offline; only simulators run)
- [ ] Browser zoomed to **100%** (demo is designed for 1280×720 projector)
- [ ] Enable sound: click **"Enable sound"** toggle in header (browser autoplay is blocked; one click grants permission)
- [ ] Load scenario: pick **"monsoon"** from scenario picker (top left)
- [ ] **Play** button: ensure replay is paused at start (click play to begin)

---

## Demo Flow (4 minutes)

### 1. The Problem (30 seconds, no interaction)

> *[Scroll frontend to show initial state: map with green zones, no alerts]*
>
> "Anil runs a tea stall in Mumbai. When it rains, sales collapse. Today, he's not online to file a claim. By the time he reaches an office, the insurance company has asked for bills and photos. That's 30–60 days to get paid.
>
> Chhatri fixes this: **the claim starts itself.**"

### 2. The Storm Hits (2 minutes, live replay)

> *[Click play button; replay starts at 08:00]*
>
> "It's Tuesday morning in Mumbai. Weather forecast says rain could hit the city at 14:00.
>
> At 13:30, the red alert appears." 

*[Wait until ~14:00 sim-time; zones Z7, Z3, Z12 turn orange/red on the map]*

> "Three zones are flagged. Watch the sales data: they're falling in real-time."

*[Let replay run; watch hexes on the map change color as sales drop below expected]*

> "At 17:00—the trigger fires."

*[Watch the KPI tiles update: "3 zones triggered", "312 shops paid"]*

> "Three zones triggered. 312 shops just got paid—**automatically, in 4 minutes**. No claim forms. No bills. No waiting.

> Here's Anil's shop."

*[Click Z7 on map or zone card; inspect panel showing "₹1,380 paid · 17:04"]*

> "His usual Tuesday is ₹4,380. Sales fell 63%. We pay him half the loss: ₹1,380. **Credited with today's settlement.**
>
> His next instalment—₹600—is paused. He can't miss a payment when sales collapsed."

*[Point to "Tomorrow's ₹600 instalment is paused" in the zone panel]*

### 3. Personal Claim (1.5 minutes, live conversation)

> *[Switch to merchant phone view; navigate to Anil's chat]*
>
> "But Anil is in the hospital with a fever. His shop is closed.
>
> At 11:20 tomorrow, Chhatri checks in."

*[Scroll to see the check-in message: "Your shop has been closed since yesterday. Is everything okay?"]*

> "Anil replies."

*[Use the voice demo chip: click "I'm in hospital with a fever" (canned voice); watch message appear in chat]*

> "Chhatri asks for proof."

*[Point to the follow-up: "Please send one photo of the hospital slip."]*

> "One photo."

*[Click upload sample slip; show the admission slip ("Anil R. Jadhav, admitted Aug 20, KEM Hospital, Viral fever")]*

> "Our vision model reads the name, dates, hospital. Policy checks:
> - **Name matches KYC?** Yes, ✓
> - **Dates cover the silent days?** Yes, ✓
> - **Within the 3-day auto-limit?** Yes, ✓
>
> All checks pass. Decision: **APPROVED, ₹1,500**. Paid the same day."

*[Show the payout card in the chat; watch the audit log for the decision]*

### 4. Three Live Tests (1 minute, automated checks)

> *[Reset to monsoon scenario at 17:12; or load fresh]*
>
> "Our demo includes three live tests from the pitch deck."

#### Test 1: EXPLAINED
> *[In chat, send or use chip: "Why did I get only this much?" or "मुझे इतने पैसे क्यों मिले?"]*
>
> "**Merchant asks why the payout is small.**"

*[Watch response appear: "Your usual Tuesday: ₹4,380. Your area fell 63%. Chhatri pays half the lost sales."]*

> "We show the breakdown—every number is reproducible. Then:"

*[Watch follow-up: "मेरा नुकसान ज़्यादा हुआ" / "My loss was bigger."]*

> "**The merchant disputes.** A case is opened instantly. A human on our team will review."

*[Point to "Sent to a claims officer · case C-2291" in chat; switch to claims officer queue if time]*

#### Test 2: HUMAN
> *[Show slip mismatch scenario briefly, or explain]*
>
> "If the slip has a different name, or dates don't match, the AI can't auto-approve. **A human always reviews doubtful claims.**"

#### Test 3: BLOCKED
> *[Or explain without live replay]*
>
> "If a merchant tries to buy cover **during a forecast alert**, they're blocked. New cover starts after the 7-day waiting period."

---

## Fallback Plan (No Internet, No Paytm)

**Fallback already built in.** The demo is 100% offline:

- ✓ All merchants, sales, weather fixtures committed to `backend/data/`
- ✓ Model trained on past data; committed to `backend/artifacts/model/`
- ✓ Sarvam voice/chat/vision → simulator (deterministic, Hindi/English)
- ✓ WhatsApp → console phone simulator
- ✓ Paytm → simulated links (marked "SIMULATED", cannot actually charge)
- ✓ n8n → in-process workflow runner
- ✓ Fonts self-hosted (Ubuntu, Noto Sans Devanagari)

If the Paytm payment link button fails (PAYTM_MCP_URL not set), it shows a simulated link and says "SIMULATED".

---

## Likely Judge Questions

### "Is the payout real? How do you actually send money?"
> "In the demo, payouts are simulated. The settlement rail is simulated: 4 minutes after the policy engine approves, we record a `Payout(status=CREDITED)`.
>
> In production, this would hit Paytm's settlement rail. We already integrate with Paytm's payment MCP server—we use the same API that powers the premium link button. The demo just records the event instead of actually charging."

### "What if someone lies about being sick?"
> "The hospital slip is verified by our vision model (Sarvam). The patient name must match the KYC name (95–100% confidence via fuzzy matching). The dates must cover the silent period.
>
> If **any** of these fail, the case goes to a human. We never auto-pay without confidence.
>
> We also have basis risk: if a merchant claims illness but was actually on holiday, the area-level trigger didn't fire (no rain alert), so **the area check fails first**. Basis risk is baked into the trigger logic."

### "How do you prevent gaming? Can a merchant pay people to buy at their shop to bump sales?"
> "Good catch. Our trigger is area-level, not shop-level. One shop can't fake an area index. If Anil's shop has high sales but the rest of the zone is low, that's actually healthy—the zone's index is still below the model's range.
>
> **Gaming the index would require coordinating 20+ shops.** Easier to just work.
>
> Also: the expected sales model is trained on normal days only (no alerts, no shocks). If half the shops in a zone suddenly have high sales during a RED alert, that's a statistical anomaly—the backtest would flag it."

### "Why focus on merchants, not crop insurance?"
> "Merchants are 1.57 crore on Paytm—we can reach them instantly. Crop insurance requires physical inspection and acreage proof. Merchants have digital footprints (transaction history, location, loan data). We measure the loss in real-time from their sales data; no assessment needed.
>
> The model is smaller (LightGBM, ≤ 500 MB), faster (triggers in 4 minutes), and cheaper (settlement costs are lower than crop insurance).
>
> The monsoon pilot tests this. Future: heatwave cover, bandh cover, other weather events."

### "What's the business model?"
> "Chhatri sits on top of Paytm's merchant plan (₹2/day fixed price). We charge an additional rider:
>
> - Premium = expected loss cost / (1 - loading factor)
> - Loading (profit margin) = 35%
> - Merchants prepay via settlement: Paytm deducts the daily premium from the merchant's own collections that day
>
> If a merchant collects ₹10,000 and the premium is ₹10, Paytm settles ₹9,990 and ₹10 goes to insurance. The payout comes from the insurance fund (our partner), not Paytm's pocket.
>
> See deck slide 12: ₹561 crore merchant plan revenue → ₹814 crore with Chhatri rider (+45% YoY)."

### "How is this different from Paytm's earlier plans?"
> "Paytm's earlier merchant protection plans (30–60 days, required bills/photos) never gained trust because merchants had to file and wait. Chhatri:
>
> - **Automatic**: triggers on data Paytm already sees
> - **Same-day**: payout within hours, not weeks
> - **No docs for area claims**: we measure the loss, not ask the merchant to prove it
> - **Minimal docs for personal claims**: one photo, not a binder of bills
>
> This is a product innovation, not a tech innovation. The innovation is **policy + data**, not just AI."

---

## Demo Technical Notes

- **Replay speed**: 6 sim-minutes per real second (configurable via slider; default for demo is 6x)
- **Monsoon replay**: 08:00–20:00 IST (12 hours) → ≈ 2 min wall-clock at 6x
- **Scenario load**: ≤ 1s (cold start: ≤ 3s)
- **Trigger → money**: 17:00 trigger → 17:04 credited (sim-time); displayed in real-time
- **Fonts**: Self-hosted Ubuntu + Noto Sans Devanagari (no external CDN)
- **Audio**: Sarvam Bulbul v3 TTS (live) or browser `speechSynthesis` (simulated, en-US for English)

---

## After the Demo

- **Backtest tab**: Show 2024 & 2025 monsoon backtests (real rainfall, simulated sales, 2 trigger strategies)
- **Audit tab**: "Verify chain" button proves tamper-evidence (every step cryptographically linked)
- **Policy tab**: Show the payout authority table (what Chhatri alone pays, what goes to humans)

---

## Keywords for Judges

- **Claims that start themselves**: automation via real-time data
- **Measured loss, not guessed**: LightGBM model + area index
- **Same-day payout**: 4-minute trigger-to-money in replay
- **Instalment pause**: loan protection, not just insurance claim
- **No claim form**: merchant does nothing
- **No basis risk**: area-level trigger, not individual shop
- **Doubt → human**: REFERRED cases go to officers, not paid without review
- **Code decides, not AI**: policy engine is logic, not LLM
- **Offline-first**: works without internet; Sarvam/WhatsApp/n8n optional
- **Deterministic**: same scenario seed → identical payouts, audit hashes
