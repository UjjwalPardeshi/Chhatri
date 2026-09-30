# Chhatri backtest · two past monsoons

*simulated sales · real Open-Meteo rainfall* · Jun–Sep 2024 · Jun–Sep 2025 · data to 2025-10-01T00:00:00+05:30

## Chhatri vs a weather-only trigger

| Measure | Chhatri | Weather-only |
|---|---|---|
| Real sales drops that get paid | 89 of 147 (61%) | 49 of 147 (33%) |
| Payouts with no real drop | 36 of 125 (29%) | 287 of 336 (85%) |
| Trigger to money | same day · 4 min | next day · after the daily rain total |
| Documents per area claim | 0 | 0 |
| Total paid | ₹1,50,01,175 | ₹3,37,18,436 |

## Doubtful personal claims seen by a human

359 of 844 personal claims referred to a claims officer (43%); 485 paid automatically.

## Premiums vs payouts, per zone

| Zone | Premium / day | Premiums | Payouts | Loss ratio | False + | Missed |
|---|---|---|---|---|---|---|
| Z1 | ₹13.56 | ₹10,78,969.20 | ₹7,01,336 | 65% | 2 | 5 |
| Z2 | ₹13.71 | ₹11,70,971.10 | ₹7,61,080 | 65% | 2 | 2 |
| Z3 | ₹14.20 | ₹14,61,606 | ₹9,50,071 | 65% | 0 | 0 |
| Z4 | ₹16.82 | ₹11,05,074 | ₹7,18,470 | 65% | 0 | 1 |
| Z5 | ₹9.87 | ₹5,69,202.90 | ₹3,70,034 | 65% | 0 | 5 |
| Z6 | ₹29.91 | ₹24,67,275.90 | ₹16,03,526 | 65% | 5 | 1 |
| Z7 | ₹20.68 | ₹6,94,434.40 | ₹4,51,280 | 65% | 1 | 3 |
| Z8 | ₹38.85 | ₹28,07,689.50 | ₹18,25,046 | 65% | 5 | 5 |
| Z9 | ₹25.43 | ₹11,88,089.60 | ₹7,72,347 | 65% | 4 | 0 |
| Z10 | ₹16.58 | ₹4,23,619 | ₹2,75,427 | 65% | 0 | 5 |
| Z11 | ₹10.88 | ₹5,16,256 | ₹3,35,700 | 65% | 1 | 2 |
| Z12 | ₹10.51 | ₹9,59,037.50 | ₹6,23,555 | 65% | 0 | 4 |
| Z13 | ₹16.26 | ₹14,24,376 | ₹9,25,715 | 65% | 1 | 1 |
| Z14 | ₹21.34 | ₹18,22,649.40 | ₹11,84,598 | 65% | 2 | 2 |
| Z15 | ₹17.03 | ₹5,22,139.80 | ₹3,39,430 | 65% | 1 | 3 |
| Z16 | ₹9.34 | ₹2,25,000.60 | ₹1,46,222 | 65% | 0 | 1 |
| Z17 | ₹15.98 | ₹4,78,281.40 | ₹3,10,827 | 65% | 2 | 2 |
| Z18 | ₹21.18 | ₹5,41,149 | ₹3,51,730 | 65% | 4 | 1 |
| Z19 | ₹13.68 | ₹6,39,129.60 | ₹4,15,359 | 65% | 1 | 1 |
| Z20 | ₹28.83 | ₹6,94,514.70 | ₹4,51,432 | 65% | 1 | 3 |
| Z21 | ₹6.93 | ₹5,26,125.60 | ₹3,41,861 | 65% | 0 | 3 |
| Z22 | ₹19.05 | ₹9,45,642 | ₹6,14,723 | 65% | 1 | 1 |
| Z23 | ₹7.19 | ₹1,94,201.90 | ₹1,26,236 | 65% | 0 | 5 |
| Z24 | ₹19.86 | ₹6,23,405.40 | ₹4,05,170 | 65% | 3 | 2 |

## Notes

- 1821 simulated shops in 24 Mumbai zones, 1820 with cover; hourly rain from the real Open-Meteo records for Santacruz and Colaba.
- Rolling-origin LightGBM quantile models per area and shop type — Jun–Sep 2024: fitted 6 Jan 2024–3 May 2024, range calibrated 4 May 2024–31 May 2024; Jun–Sep 2025: fitted 7 Jan 2024–3 May 2025, range calibrated 4 May 2025–31 May 2025.
- Chhatri pays when an alert is in force and the area index stays below 50% for 3 hours and below the model's range: 50% of the lost sales, decided by the policy engine, credited with the settlement.
- Weather-only pays when the reference grid point's daily rain reaches 64.5 mm (IMD “heavy”): 50% × expected day × 50% to every covered shop of the zones on that grid point, once the day's total is known.
- Real drop = zone-day whose true shock-caused loss is at least 40% of the expected day sales of its covered shops: 49 rain (Chhatri paid 41, weather-only 47); 48 bandh (Chhatri paid 48, weather-only 0); 50 slow-day (Chhatri paid 0, weather-only 2). Slow days come with no alert: Chhatri does not pay them by design (a slow day is not a loss event), so they count as misses.
- Personal claims come from silent-shop detection; slips are read by the simulated reader and 18% are modelled as doubtful (unreadable, another name or a later admission). Doubtful claims (such a slip, or more than 3 days) seen by a human: 359 of 359, 0 paid automatically. All personal claims: 844, 485 paid automatically (₹17,28,585), 359 referred, 0 declined.
- Premium per zone = max(₹2, area loss per shop per year / 365 / (1 − 0.35)); each monsoon is one policy year. Loss ratios are in-sample. Personal claims are not priced per zone: the closure hazard is the same everywhere.
- Every pilot shop is assumed to hold prepaid cover through every season replayed.
