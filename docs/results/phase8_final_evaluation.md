# Phase 8 Final Evaluation: Held-Out Streams (EVAL_SEEDS 90000-90049)

_Split: **eval** (seeds 90000-90049), 30-day streams, 7 days drain, generated 2026-10-31T02:48:59. Mean ± std across streams; lower is better for waits. All policies were evaluated on identical streams._

## normal (50 streams)

| Policy | Weighted wait (min) | Avg wait (min) | Critical wait (min) | Low-acuity isolation wait (min) | P90 wait (min) | ICU util | Still waiting | Peak queue | Invalid actions | Violations |
|---|---|---|---|---|---|---|---|---|---|---|
| b1 | 419.4 ± 206.1 | 351.0 ± 176.9 | 421.8 ± 233.6 | 3954.6 ± 2195.9 | 1028.1 ± 659.9 | 0.89 ± 0.03 | 0.6 ± 1.7 | 11.5 ± 4.4 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h1 | 180.8 ± 107.5 | 282.2 ± 158.7 | 89.3 ± 110.4 | 4536.2 ± 2128.2 | 147.4 ± 425.1 | 0.58 ± 0.08 | 0.6 ± 1.6 | 8.2 ± 3.1 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h2 | 433.6 ± 200.7 | 359.6 ± 163.2 | 433.9 ± 228.9 | 3817.2 ± 1935.7 | 1071.9 ± 643.9 | 0.89 ± 0.03 | 0.4 ± 1.2 | 11.7 ± 4.1 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h3 | 184.1 ± 108.7 | 275.4 ± 149.8 | 93.7 ± 117.7 | 4166.7 ± 1989.4 | 145.7 ± 425.8 | 0.58 ± 0.08 | 0.4 ± 1.4 | 8.3 ± 3.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| x6_obs_v2 | 256.2 ± 178.6 | 316.2 ± 171.5 | 185.1 ± 202.9 | 4535.9 ± 2072.7 | 417.3 ± 664.1 | 0.68 ± 0.08 | 0.5 ± 1.3 | 9.5 ± 4.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| x6_obs_v2_safe | 253.3 ± 170.7 | 313.6 ± 166.3 | 182.2 ± 195.8 | 4508.8 ± 2031.2 | 416.0 ± 656.1 | 0.68 ± 0.08 | 0.4 ± 1.2 | 9.5 ± 3.8 | 0.0 ± 0.0 | 0.0 ± 0.0 |

**Paired differences** (policy minus reference; negative = policy is better; 95% bootstrap CI; win = share of streams where the policy is better)

| Policy | Metric | vs | Mean diff | 95% CI | Win rate |
|---|---|---|---|---|---|
| b1 | acuity_weighted_avg_wait_min | h1 | 238.6 | [201.1, 277.7] | 0% |
| b1 | avg_wait_incl_unadmitted_min | h3 | 75.6 | [50.6, 99.8] | 16% |
| b1 | critical_avg_wait_min | h1 | 332.6 | [288.1, 378.9] | 0% |
| h1 | acuity_weighted_avg_wait_min | b1 | -238.6 | [-277.7, -201.1] | 100% |
| h1 | avg_wait_incl_unadmitted_min | b1 | -68.7 | [-92.8, -44.4] | 84% |
| h1 | avg_wait_incl_unadmitted_min | h3 | 6.8 | [-3.1, 17.0] | 36% |
| h1 | critical_avg_wait_min | b1 | -332.6 | [-378.9, -288.1] | 100% |
| h2 | acuity_weighted_avg_wait_min | b1 | 14.2 | [1.0, 26.5] | 24% |
| h2 | acuity_weighted_avg_wait_min | h1 | 252.8 | [216.4, 291.3] | 0% |
| h2 | avg_wait_incl_unadmitted_min | b1 | 8.7 | [-5.0, 22.2] | 32% |
| h2 | avg_wait_incl_unadmitted_min | h3 | 84.3 | [57.8, 110.3] | 20% |
| h2 | critical_avg_wait_min | b1 | 12.1 | [-3.4, 26.0] | 24% |
| h2 | critical_avg_wait_min | h1 | 344.7 | [301.9, 388.5] | 0% |
| h3 | acuity_weighted_avg_wait_min | b1 | -235.3 | [-273.8, -198.1] | 98% |
| h3 | acuity_weighted_avg_wait_min | h1 | 3.2 | [-3.1, 9.8] | 36% |
| h3 | avg_wait_incl_unadmitted_min | b1 | -75.6 | [-99.8, -50.6] | 84% |
| h3 | critical_avg_wait_min | b1 | -328.1 | [-373.0, -284.8] | 100% |
| h3 | critical_avg_wait_min | h1 | 4.5 | [-1.7, 10.9] | 18% |
| x6_obs_v2 | acuity_weighted_avg_wait_min | b1 | -163.2 | [-192.1, -135.0] | 96% |
| x6_obs_v2 | acuity_weighted_avg_wait_min | h1 | 75.4 | [50.6, 103.5] | 12% |
| x6_obs_v2 | avg_wait_incl_unadmitted_min | b1 | -34.8 | [-59.7, -10.0] | 80% |
| x6_obs_v2 | avg_wait_incl_unadmitted_min | h3 | 40.8 | [23.3, 59.7] | 16% |
| x6_obs_v2 | critical_avg_wait_min | b1 | -236.8 | [-269.4, -204.5] | 96% |
| x6_obs_v2 | critical_avg_wait_min | h1 | 95.8 | [65.0, 130.4] | 10% |
| x6_obs_v2_safe | acuity_weighted_avg_wait_min | b1 | -166.2 | [-195.6, -137.5] | 96% |
| x6_obs_v2_safe | acuity_weighted_avg_wait_min | h1 | 72.4 | [49.1, 98.9] | 12% |
| x6_obs_v2_safe | avg_wait_incl_unadmitted_min | b1 | -37.4 | [-61.7, -13.4] | 80% |
| x6_obs_v2_safe | avg_wait_incl_unadmitted_min | h3 | 38.2 | [22.1, 55.0] | 16% |
| x6_obs_v2_safe | critical_avg_wait_min | b1 | -239.7 | [-273.0, -206.5] | 96% |
| x6_obs_v2_safe | critical_avg_wait_min | h1 | 92.9 | [63.4, 125.8] | 10% |

## moderate_surge (50 streams)

| Policy | Weighted wait (min) | Avg wait (min) | Critical wait (min) | Low-acuity isolation wait (min) | P90 wait (min) | ICU util | Still waiting | Peak queue | Invalid actions | Violations |
|---|---|---|---|---|---|---|---|---|---|---|
| b1 | 3488.4 ± 1008.1 | 2796.4 ± 822.2 | 4018.5 ± 1169.1 | 12233.9 ± 2986.1 | 7312.5 ± 2173.6 | 0.96 ± 0.01 | 14.4 ± 8.4 | 106.7 ± 29.4 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h1 | 3144.0 ± 970.5 | 2652.3 ± 834.5 | 3534.0 ± 1108.3 | 12455.4 ± 2885.7 | 6836.2 ± 2067.9 | 0.89 ± 0.02 | 13.6 ± 8.2 | 103.0 ± 29.6 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h2 | 3559.1 ± 1015.9 | 2815.9 ± 823.2 | 4134.9 ± 1185.2 | 12137.7 ± 2934.7 | 7592.7 ± 2237.4 | 0.96 ± 0.01 | 14.9 ± 8.5 | 106.7 ± 29.1 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h3 | 3190.2 ± 972.8 | 2664.9 ± 828.9 | 3611.0 ± 1126.8 | 12494.8 ± 2885.2 | 7080.6 ± 2100.2 | 0.89 ± 0.02 | 14.0 ± 8.2 | 103.1 ± 29.4 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| x6_obs_v2 | 3472.5 ± 970.4 | 2836.4 ± 788.3 | 3913.3 ± 1132.4 | 14806.7 ± 3712.9 | 8373.0 ± 2487.2 | 0.91 ± 0.02 | 20.8 ± 9.3 | 105.8 ± 28.3 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| x6_obs_v2_safe | 3287.0 ± 978.2 | 2690.8 ± 816.0 | 3748.3 ± 1134.1 | 12555.0 ± 2966.9 | 7183.9 ± 2082.5 | 0.92 ± 0.02 | 14.1 ± 8.1 | 104.1 ± 29.1 | 0.0 ± 0.0 | 0.0 ± 0.0 |

**Paired differences** (policy minus reference; negative = policy is better; 95% bootstrap CI; win = share of streams where the policy is better)

| Policy | Metric | vs | Mean diff | 95% CI | Win rate |
|---|---|---|---|---|---|
| b1 | acuity_weighted_avg_wait_min | h1 | 344.4 | [287.1, 402.5] | 4% |
| b1 | avg_wait_incl_unadmitted_min | h1 | 144.0 | [106.6, 181.6] | 14% |
| b1 | critical_avg_wait_min | h1 | 484.5 | [406.3, 563.1] | 0% |
| h1 | acuity_weighted_avg_wait_min | b1 | -344.4 | [-402.5, -287.1] | 96% |
| h1 | avg_wait_incl_unadmitted_min | b1 | -144.0 | [-181.6, -106.6] | 86% |
| h1 | critical_avg_wait_min | b1 | -484.5 | [-563.1, -406.3] | 100% |
| h2 | acuity_weighted_avg_wait_min | b1 | 70.7 | [50.0, 92.5] | 4% |
| h2 | acuity_weighted_avg_wait_min | h1 | 415.1 | [351.9, 479.3] | 0% |
| h2 | avg_wait_incl_unadmitted_min | b1 | 19.5 | [6.8, 33.2] | 30% |
| h2 | avg_wait_incl_unadmitted_min | h1 | 163.6 | [124.0, 202.9] | 14% |
| h2 | critical_avg_wait_min | b1 | 116.5 | [83.4, 151.2] | 4% |
| h2 | critical_avg_wait_min | h1 | 601.0 | [516.2, 687.4] | 0% |
| h3 | acuity_weighted_avg_wait_min | b1 | -298.3 | [-357.0, -242.1] | 94% |
| h3 | acuity_weighted_avg_wait_min | h1 | 46.2 | [27.0, 68.6] | 8% |
| h3 | avg_wait_incl_unadmitted_min | b1 | -131.5 | [-169.6, -94.3] | 82% |
| h3 | avg_wait_incl_unadmitted_min | h1 | 12.6 | [1.8, 24.1] | 24% |
| h3 | critical_avg_wait_min | b1 | -407.5 | [-489.3, -328.0] | 92% |
| h3 | critical_avg_wait_min | h1 | 77.0 | [45.5, 111.1] | 8% |
| x6_obs_v2 | acuity_weighted_avg_wait_min | b1 | -15.9 | [-78.0, 45.5] | 48% |
| x6_obs_v2 | acuity_weighted_avg_wait_min | h1 | 328.5 | [276.0, 381.8] | 2% |
| x6_obs_v2 | avg_wait_incl_unadmitted_min | b1 | 40.0 | [-9.0, 88.5] | 38% |
| x6_obs_v2 | avg_wait_incl_unadmitted_min | h1 | 184.0 | [142.4, 227.2] | 10% |
| x6_obs_v2 | critical_avg_wait_min | b1 | -105.2 | [-182.0, -28.4] | 66% |
| x6_obs_v2 | critical_avg_wait_min | h1 | 379.3 | [319.1, 439.1] | 2% |
| x6_obs_v2_safe | acuity_weighted_avg_wait_min | b1 | -201.4 | [-253.5, -150.7] | 86% |
| x6_obs_v2_safe | acuity_weighted_avg_wait_min | h1 | 143.1 | [109.0, 177.5] | 14% |
| x6_obs_v2_safe | avg_wait_incl_unadmitted_min | b1 | -105.6 | [-139.1, -72.9] | 82% |
| x6_obs_v2_safe | avg_wait_incl_unadmitted_min | h1 | 38.5 | [16.1, 61.1] | 30% |
| x6_obs_v2_safe | critical_avg_wait_min | b1 | -270.2 | [-341.5, -201.9] | 86% |
| x6_obs_v2_safe | critical_avg_wait_min | h1 | 214.3 | [166.6, 262.3] | 12% |

## severe_surge (50 streams)

| Policy | Weighted wait (min) | Avg wait (min) | Critical wait (min) | Low-acuity isolation wait (min) | P90 wait (min) | ICU util | Still waiting | Peak queue | Invalid actions | Violations |
|---|---|---|---|---|---|---|---|---|---|---|
| b1 | 14532.2 ± 644.3 | 13925.9 ± 652.9 | 15098.2 ± 689.7 | 20639.8 ± 1845.8 | 23348.4 ± 1050.7 | 0.98 ± 0.01 | 546.0 ± 45.5 | 726.2 ± 45.5 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h1 | 14473.7 ± 634.1 | 14048.2 ± 654.8 | 14886.8 ± 676.6 | 20815.6 ± 1823.1 | 23396.9 ± 1026.8 | 0.94 ± 0.01 | 547.1 ± 45.9 | 727.0 ± 45.5 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h2 | 14560.7 ± 649.1 | 13904.7 ± 654.0 | 15173.0 ± 702.4 | 20586.7 ± 1802.3 | 23369.1 ± 1090.0 | 0.98 ± 0.01 | 547.0 ± 44.8 | 724.6 ± 45.8 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h3 | 14492.6 ± 638.4 | 14041.5 ± 662.4 | 14932.9 ± 681.6 | 20830.3 ± 1747.5 | 23467.2 ± 1113.6 | 0.94 ± 0.01 | 549.6 ± 47.0 | 726.3 ± 45.6 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| x6_obs_v2 | 14753.2 ± 669.8 | 14005.6 ± 608.6 | 15592.8 ± 859.6 | 21938.8 ± 2147.1 | 25996.3 ± 1507.6 | 0.95 ± 0.01 | 582.4 ± 43.1 | 718.0 ± 44.4 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| x6_obs_v2_safe | 14468.5 ± 646.0 | 13964.0 ± 656.4 | 14940.5 ± 690.5 | 20848.9 ± 1849.9 | 23357.8 ± 1057.3 | 0.96 ± 0.01 | 546.7 ± 46.3 | 725.6 ± 45.6 | 0.0 ± 0.0 | 0.0 ± 0.0 |

**Paired differences** (policy minus reference; negative = policy is better; 95% bootstrap CI; win = share of streams where the policy is better)

| Policy | Metric | vs | Mean diff | 95% CI | Win rate |
|---|---|---|---|---|---|
| b1 | acuity_weighted_avg_wait_min | h1 | 58.4 | [37.8, 79.3] | 22% |
| b1 | avg_wait_incl_unadmitted_min | h2 | 21.2 | [10.3, 32.4] | 16% |
| b1 | critical_avg_wait_min | h1 | 211.4 | [176.9, 246.5] | 2% |
| h1 | acuity_weighted_avg_wait_min | b1 | -58.4 | [-79.3, -37.8] | 78% |
| h1 | avg_wait_incl_unadmitted_min | b1 | 122.3 | [105.6, 138.6] | 2% |
| h1 | avg_wait_incl_unadmitted_min | h2 | 143.5 | [123.9, 162.8] | 0% |
| h1 | critical_avg_wait_min | b1 | -211.4 | [-246.5, -176.9] | 98% |
| h2 | acuity_weighted_avg_wait_min | b1 | 28.6 | [19.9, 37.9] | 6% |
| h2 | acuity_weighted_avg_wait_min | h1 | 87.0 | [63.7, 111.1] | 14% |
| h2 | avg_wait_incl_unadmitted_min | b1 | -21.2 | [-32.4, -10.3] | 60% |
| h2 | critical_avg_wait_min | b1 | 74.8 | [53.0, 97.9] | 6% |
| h2 | critical_avg_wait_min | h1 | 286.1 | [245.5, 328.4] | 0% |
| h3 | acuity_weighted_avg_wait_min | b1 | -39.5 | [-61.2, -18.5] | 74% |
| h3 | acuity_weighted_avg_wait_min | h1 | 18.9 | [10.2, 30.1] | 6% |
| h3 | avg_wait_incl_unadmitted_min | b1 | 115.5 | [96.8, 135.0] | 2% |
| h3 | avg_wait_incl_unadmitted_min | h2 | 136.8 | [115.0, 161.8] | 2% |
| h3 | critical_avg_wait_min | b1 | -165.3 | [-203.5, -129.8] | 92% |
| h3 | critical_avg_wait_min | h1 | 46.1 | [30.4, 62.8] | 2% |
| x6_obs_v2 | acuity_weighted_avg_wait_min | b1 | 221.1 | [186.4, 257.7] | 4% |
| x6_obs_v2 | acuity_weighted_avg_wait_min | h1 | 279.5 | [244.5, 315.0] | 0% |
| x6_obs_v2 | avg_wait_incl_unadmitted_min | b1 | 79.7 | [41.0, 116.2] | 22% |
| x6_obs_v2 | avg_wait_incl_unadmitted_min | h2 | 100.9 | [63.0, 137.6] | 20% |
| x6_obs_v2 | critical_avg_wait_min | b1 | 494.6 | [394.4, 595.8] | 10% |
| x6_obs_v2 | critical_avg_wait_min | h1 | 706.0 | [601.2, 806.9] | 2% |
| x6_obs_v2_safe | acuity_weighted_avg_wait_min | b1 | -63.7 | [-79.6, -48.2] | 88% |
| x6_obs_v2_safe | acuity_weighted_avg_wait_min | h1 | -5.3 | [-17.1, 7.2] | 56% |
| x6_obs_v2_safe | avg_wait_incl_unadmitted_min | b1 | 38.1 | [25.1, 52.1] | 20% |
| x6_obs_v2_safe | avg_wait_incl_unadmitted_min | h2 | 59.3 | [42.7, 76.3] | 12% |
| x6_obs_v2_safe | critical_avg_wait_min | b1 | -157.7 | [-189.2, -126.5] | 90% |
| x6_obs_v2_safe | critical_avg_wait_min | h1 | 53.6 | [32.3, 75.3] | 24% |
