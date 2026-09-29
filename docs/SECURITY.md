# Chhatri Security (SPEC §21)

## Controls

### Secrets

- **No secrets in source code**: all credentials from environment (`.env`)
- **Demo mode**: officer token printed at startup when unset (secure; token is not persisted)
- **Internal secret**: `CHHATRI_INTERNAL_SECRET` used for n8n webhook verification and officer routes

### Input Validation

- **Pydantic models**: all HTTP inputs validated against schema
- **File uploads**: type/size checked by magic bytes (not just MIME headers)
  - Images: ≤ 5 MB, jpeg/png/webp
  - Audio: ≤ 5 MB, ≤ 30 s, ogg/opus/webm/mp3/wav/m4a
- **Merchant phone numbers**: masked in logs (`+91•••••12345`)
- **Audit log**: PII never logged

### API Security

- **Authentication**: `Bearer <CHHATRI_OFFICER_TOKEN>` on sensitive routes
  - `POST /api/cases/{id}/approve`
  - `POST /api/cases/{id}/decline`
  - `POST /api/premium/link`
- **Authorization**: demo mode routes return 404 when `CHHATRI_DEMO_MODE=false`
- **Webhook signature verification**: WhatsApp webhooks verify `X-Hub-Signature-256 = hmac_sha256(app_secret, raw_body)`
- **CORS**: restricted to `CHHATRI_CONSOLE_ORIGIN` (default `http://localhost:5173`)
- **Rate limiting**: simple in-memory limits on webhook and upload routes

### Audit

- **Immutable ledger**: `AuditLog` is append-only SQLite; every decision stored with all checks
- **Tamper detection**: SHA256 hash chain; `AuditLog.verify()` recomputes chain and reports first bad entry
- **Determinism**: same seed + same scenario ⇒ identical audit hashes (except `recorded_at` wall time)

### Workflow Security

- **Signature verification**: n8n workflows verify `X-Chhatri-Secret` header before executing steps
- **Idempotency**: payout execution is idempotent on `decision_id` (prevents double-spending)
- **No free-text approval**: policy engine is deterministic code; LLM never approves

---

## Threat Model

### 1. Forged Webhooks

**Threat**: Attacker sends fake webhook (WhatsApp, Paytm callback, n8n step callback).

**Controls**:
- WhatsApp: signature verification (`X-Hub-Signature-256`)
- n8n: secret header verification (`X-Chhatri-Secret`)
- Paytm: (depends on Paytm's API security; we don't verify signatures beyond HTTPS + API key)

**Residual risk**: Low. Attacker must forge HMAC or steal shared secret.

### 2. Replayed Callbacks

**Threat**: Attacker replays a legitimate webhook (e.g., payout callback) to trigger double-payout.

**Controls**:
- Idempotency: payout execution is idempotent on `decision_id`
- Audit log: every execution logged with timestamp and actor
- Backend enforcement: `payout_for_decision(decision_id)` returns existing payout if already executed

**Residual risk**: Very low. Replay attack results in 200 (no-op), not double-payout.

### 3. Gaming the Area Index

**Threat**: Merchants coordinate to boost sales during a claimed low-index window (e.g., all shops in Z7 run promotions) to invalidate a payout trigger.

**Controls**:
- Area-level trigger: requires 20+ shops below the model range (coordination difficult)
- Model training: trained on normal days only (anomalies detectable)
- Historical data: backtest validates trigger accuracy over 2 past monsoons

**Residual risk**: Medium. Requires coordination of 20+ merchants. Economically irrational (merchants gain ₹0, lose effort).

### 4. Fake Slips

**Threat**: Merchant presents fake hospital slip (photoshopped, from internet, printed template) to claim personal payout.

**Controls**:
- Vision model: Sarvam extracts patient name, dates, hospital from image
- Name matching: rapidfuzz token_set_ratio ≥ 85 vs KYC name
- Date matching: admission ≤ silent day ≤ discharge (or ∞)
- Confidence threshold: 0.80 minimum
- Manual review: if any SOFT check fails (name mismatch, date mismatch, unreadable), case goes to human

**Residual risk**: Medium. Vision model can be fooled by high-quality fakes. Mitigated by: (a) confidence threshold, (b) always-review-on-doubt, (c) audit log (catches patterns).

### 5. Buying Cover Before a Storm

**Threat**: Merchant buys cover after an alert is issued, triggering immediately.

**Controls**:
- Waiting period: new cover starts 7 days after purchase (SPEC §9.5)
- Alert lookahead: if an alert is current or forecasted within 72 hours, cover is blocked from immediate start
- Check `COVER_BEFORE_ALERT`: if trigger alert issued after purchase, claim is declined

**Residual risk**: Low. Waiting period enforced in policy engine.

### 6. Premium Evasion

**Threat**: Merchant stops paying premium, then claims a loss.

**Controls**:
- Check `PREMIUM_PREPAID`: requires `prepaid_through ≥ event_date` (Insurance Act s.64VB)
- Settlement deduction: Paytm deducts premium from merchant's daily collections automatically
- If gross settlement < premium, no advance; claim fails

**Residual risk**: Very low. Premium check is a HARD fail.

### 7. Officer Collusion

**Threat**: Officer approves ineligible claims (e.g., slip with different name).

**Controls**:
- `apply_officer_decision()` re-runs all HARD checks (cover, premium, not-already-paid)
- SOFT checks are recorded as `WAIVED_BY_OFFICER` (not deleted; auditable)
- Officer approval is logged with officer ID in audit chain
- Audit log is tamper-evident (SHA256 chain)

**Residual risk**: Medium. Officer can waive SOFT checks. Mitigated by: (a) audit trail (all waivers logged), (b) backtest review (catches patterns of bias).

---

## Security Testing

### Unit Tests

- `backend/tests/api/test_security.py`: webhook signature verification
- `backend/tests/policy/test_engine.py`: check logic (cover, premium, dates, etc.)
- `backend/tests/audit/test_log.py`: chain tamper detection

### Integration Tests

- Replay scenarios with bad data (slip mismatch, expired cover, lapsed premium)
- Verify every scenario produces the expected decision (APPROVED / REFERRED / DECLINED)

### Audit Verification

- `GET /api/audit/verify` returns `{valid, entries, head_hash, first_bad_seq}`
- Test tampers audit entry, verify detection

### E2E (Playwright)

- Test officer approve flow with partial slip (name mismatch) → REFERRED → APPROVED with waiver
- Verify audit log records the waiver

---

## Deployment Security

### Environment

- `.env` is `.gitignore`d (never committed)
- `CHHATRI_INTERNAL_SECRET` is auto-generated if unset (printed to stdout at startup)
- `CHHATRI_OFFICER_TOKEN` is auto-generated if unset (printed to stdout in demo mode only)

### Docker

- Backend image: `python:3.12-slim` + minimal dependencies
- Frontend image: multi-stage (node builder + nginx serving)
- No secrets in Dockerfile (all from environment)

### HTTPS

- Demo runs on `http://` (localhost, no HTTPS needed)
- Production deployment: add HTTPS reverse proxy (nginx, CloudFront)
- API should enforce HTTPS only (see deployment guide)

---

## Privacy

### Data Minimization

- Phone numbers masked in logs: `+91•••••12345`
- Audit log stores facts (decision_id, amount, checks), not merchant name or address
- Slip extractions are stored (necessary for fraud detection) but marked sensitive

### Data Retention

- Audit log: permanent (immutable ledger)
- Decisions, payouts, cases: retained for dispute period (24 hours in demo, longer in production)
- Messages (WhatsApp, voice): retained per WhatsApp T&C (not our choice)

### GDPR / India Privacy Act

- Demo doesn't handle real PII (merchants are simulated, names are fake, phone numbers are fake)
- Production: data controller agreements with Paytm, Sarvam, WhatsApp required
- Right to erasure: handled at Paytm level (Chhatri is integration, not primary data holder)

---

## Incident Response

### If a Secret Leaks

1. Rotate `CHHATRI_INTERNAL_SECRET` and `CHHATRI_OFFICER_TOKEN` immediately
2. Redeploy backend + n8n
3. Review audit log for forged requests (actor = webhook source IP / token value)
4. Revert any unauthorized decisions (officer can decline and issue counter-payout)

### If a Decision is Disputed

1. Officer reviews decision + checks + evidence
2. If error, issue counter-payout or revised decision
3. Both decisions logged in audit chain with audit timestamps (wall time) and `decided_by`

### If Model is Suspected of Bias

1. Run backtest on historical data
2. Compute false positive / false negative rates per zone
3. Retrain if calibration drifts (recompute lower bound)
4. All model versions logged with training date, metrics, data window

---

## Compliance

### Insurance Act, s.64VB (India)

> "Insurer shall not forfeit the policy for non-payment of premium if premium is paid within 2 months of the due date."

**Chhatri's approach**:
- Premium prepaid via settlement deduction (automatic)
- Check `PREMIUM_PREPAID` is HARD fail (no claim without prepayment)
- Waiting period (7 days post-purchase) complies with s.64VB spirit (insurability requirement)

### Prevention of Fraud

- Vision model for slip verification (difficult to forge)
- Name matching (rapidfuzz, not substring match)
- Audit log tamper-evidence
- Human review of doubtful claims

### Accountability

- Every decision recorded with `decided_by` (`policy-engine` or `officer:<id>`)
- Audit log chain-verified
- Officer actions logged and wayward patterns detectable

---

## Security Checklist for Deployment

- [ ] `.env` file created (never `.env.example`)
- [ ] `CHHATRI_INTERNAL_SECRET` set (or auto-generated and rotated after startup)
- [ ] `CHHATRI_OFFICER_TOKEN` set (or auto-generated; if auto, printed to stdout only)
- [ ] `SARVAM_API_KEY` not in logs (check `chhatri_log_level=ERROR` or `WARNING` in production)
- [ ] WhatsApp webhook verified (Meta dashboard)
- [ ] CORS origin configured (`CHHATRI_CONSOLE_ORIGIN`)
- [ ] Rate limits enabled (built-in; limits not currently tuned for production, adjust as needed)
- [ ] Audit log backed up (SQLite file in volume)
- [ ] HTTPS enforced on frontend (reverse proxy, not Chhatri's concern)
- [ ] Demo mode disabled in production (`CHHATRI_DEMO_MODE=false`)
