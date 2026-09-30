# Chhatri backtest · two past monsoons

*simulated sales · real Open-Meteo rainfall* · Jun–Sep 2024 · Jun–Sep 2025 · data to 2025-10-01T00:00:00+05:30

## Chhatri vs a weather-only trigger

| Measure | Chhatri | Weather-only |
|---|---|---|
| Real sales drops that get paid | 89 of 148 (60%) | 49 of 148 (33%) |
| Payouts with no real drop | 36 of 125 (29%) | 287 of 336 (85%) |
| Trigger to money | same day · 4 min | next day · after the daily rain total |
| Documents per area claim | 0 | 0 |
| Total paid | ₹1,49,40,252 | ₹3,36,08,953 |

## Doubtful personal claims seen by a human

359 of 844 personal claims referred to a claims officer (43%); 485 paid automatically.

## Premiums vs payouts, per zone

| Zone | Premium / day | Premiums | Payouts | Loss ratio | False + | Missed |
|---|---|---|---|---|---|---|
| Z1 | ₹13.55 | ₹10,78,173.50 | ₹7,00,981 | 65% | 2 | 5 |
| Z2 | ₹13.71 | ₹11,70,971.10 | ₹7,61,211 | 65% | 2 | 2 |
| Z3 | ₹14.16 | ₹14,57,488.80 | ₹9,47,263 | 65% | 0 | 0 |
| Z4 | ₹16.84 | ₹11,06,388 | ₹7,19,179 | 65% | 0 | 1 |
| Z5 | ₹9.87 | ₹5,69,202.90 | ₹3,69,818 | 65% | 0 | 5 |
| Z6 | ₹29.84 | ₹24,61,501.60 | ₹16,00,026 | 65% | 5 | 1 |
| Z7 | ₹18.62 | ₹6,25,259.60 | ₹4,06,448 | 65% | 1 | 4 |
| Z8 | ₹38.82 | ₹28,05,521.40 | ₹18,23,751 | 65% | 5 | 5 |
| Z9 | ₹25.38 | ₹11,85,753.60 | ₹7,70,745 | 65% | 4 | 0 |
| Z10 | ₹16.60 | ₹4,24,130 | ₹2,75,648 | 65% | 0 | 5 |
| Z11 | ₹10.89 | ₹5,16,730.50 | ₹3,35,790 | 65% | 1 | 2 |
| Z12 | ₹10.48 | ₹9,56,300 | ₹6,21,724 | 65% | 0 | 4 |
| Z13 | ₹16.25 | ₹14,23,500 | ₹9,25,012 | 65% | 1 | 1 |
| Z14 | ₹21.36 | ₹18,24,357.60 | ₹11,85,785 | 65% | 2 | 2 |
| Z15 | ₹17.04 | ₹5,22,446.40 | ₹3,39,639 | 65% | 1 | 3 |
| Z16 | ₹9.34 | ₹2,25,000.60 | ₹1,46,254 | 65% | 0 | 1 |
| Z17 | ₹15.98 | ₹4,78,281.40 | ₹3,10,921 | 65% | 2 | 2 |
| Z18 | ₹21.14 | ₹5,40,127 | ₹3,51,135 | 65% | 4 | 1 |
| Z19 | ₹13.66 | ₹6,38,195.20 | ₹4,14,884 | 65% | 1 | 1 |
| Z20 | ₹28.79 | ₹6,93,551.10 | ₹4,50,849 | 65% | 1 | 3 |
| Z21 | ₹6.93 | ₹5,26,125.60 | ₹3,42,223 | 65% | 0 | 3 |
| Z22 | ₹19.06 | ₹9,46,138.40 | ₹6,14,968 | 65% | 1 | 1 |
| Z23 | ₹7.19 | ₹1,94,201.90 | ₹1,26,232 | 65% | 0 | 5 |
| Z24 | ₹19.59 | ₹6,14,930.10 | ₹3,99,766 | 65% | 3 | 2 |

## Notes

- 1821 simulated shops in 24 Mumbai zones, 1820 with cover; hourly rain from the real Open-Meteo records for Santacruz and Colaba.
- Rolling-origin LightGBM quantile models per area and shop type — Jun–Sep 2024: fitted 6 Jan 2024–3 May 2024, range calibrated 4 May 2024–31 May 2024; Jun–Sep 2025: fitted 7 Jan 2024–3 May 2025, range calibrated 4 May 2025–31 May 2025.
- Chhatri pays when an alert is in force and the area index stays below 50% for 3 hours and below the model's range: 50% of the lost sales, decided by the policy engine, credited with the settlement.
- Weather-only pays when the reference grid point's daily rain reaches 64.5 mm (IMD “heavy”): 50% × expected day × 50% to every covered shop of the zones on that grid point, once the day's total is known.
- Real drop = zone-day whose true shock-caused loss is at least 40% of the expected day sales of its covered shops: 50 rain (Chhatri paid 41, weather-only 47); 48 bandh (Chhatri paid 48, weather-only 0); 50 slow-day (Chhatri paid 0, weather-only 2). Slow days come with no alert: Chhatri does not pay them by design (a slow day is not a loss event), so they count as misses.
- Personal claims come from silent-shop detection; slips are read by the simulated reader and 18% are modelled as doubtful (unreadable, another name or a later admission). Doubtful claims (such a slip, or more than 3 days) seen by a human: 359 of 359, 0 paid automatically. All personal claims: 844, 485 paid automatically (₹17,25,040), 359 referred, 0 declined.
- Premium per zone = max(₹2, area loss per shop per year / 365 / (1 − 0.35)); each monsoon is one policy year. Loss ratios are in-sample. Personal claims are not priced per zone: the closure hazard is the same everywhere.
- Every pilot shop is assumed to hold prepaid cover through every season replayed.
