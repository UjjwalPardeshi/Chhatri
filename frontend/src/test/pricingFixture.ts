/**
 * The `data` of a real GET /api/pricing answer at the published rules (pilot-0.1: floor 50%, share 50%, cap ₹2,500,
 * loading 35%), trimmed to three of the 24 zones: Anil's Z7, the dearest Z8 and the cheapest Z21, so the city's lowest
 * and highest premium are still the zones' own. The median is the 24 zones' (tests only).
 */
export const PRICING_DATA = {
  label: 'simulated sales · real Open-Meteo rainfall',
  seasons: ['Jun–Sep 2024', 'Jun–Sep 2025'],
  floors: [40, 45, 50, 55, 60],
  zones: [
    { zone_id: 'Z7', shops: 46, triggers: 6, expected_payout_per_year_paise: 441_791, premium_per_day_paise: 1862, premium_per_month_paise: 55_860, premium_per_year_paise: 679_630, payout_days_per_year: 3, current_premium_per_day_paise: 1862, loss_ratio_at_current_price: 0.65, name: 'Parel · Lalbaug' },
    { zone_id: 'Z8', shops: 99, triggers: 12, expected_payout_per_year_paise: 921_086, premium_per_day_paise: 3882, premium_per_month_paise: 116_460, premium_per_year_paise: 1_416_930, payout_days_per_year: 6, current_premium_per_day_paise: 3882, loss_ratio_at_current_price: 0.6501, name: 'Dadar · Mahim' },
    { zone_id: 'Z21', shops: 104, triggers: 2, expected_payout_per_year_paise: 164_530, premium_per_day_paise: 693, premium_per_month_paise: 20_790, premium_per_year_paise: 252_945, payout_days_per_year: 1, current_premium_per_day_paise: 693, loss_ratio_at_current_price: 0.6505, name: 'Borivali' },
  ],
  city: { premium_min_paise: 693, premium_median_paise: 1643, premium_max_paise: 3882, real_drops: 148, real_drops_paid: 89, recall: 0.6014, payouts: 125, payouts_no_real_drop: 36, false_payout_share: 0.288 },
  levers: { floor_pct: 50, share_pct: 50, cap_rupees: 2500, loading_pct: 35 },
  rules: { version: 'pilot-0.1', floor_pct: 50, share_pct: 50, cap_rupees: 2500, loading_pct: 35, min_per_day_rupees: 2 },
}
