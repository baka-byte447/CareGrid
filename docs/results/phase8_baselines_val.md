# Phase 8 baselines on validation streams

_Split: **val** (seeds 80000-80019), 30-day streams, 7 days drain, generated 2026-10-27T03:32:27. Mean ± std across streams; lower is better for waits. All policies were evaluated on identical streams._

## normal (20 streams)

| Policy | Weighted wait (min) | Avg wait (min) | Critical wait (min) | Low-acuity isolation wait (min) | P90 wait (min) | ICU util | Still waiting | Peak queue | Invalid actions | Violations |
|---|---|---|---|---|---|---|---|---|---|---|
| b1 | 440.6 ± 197.6 | 404.8 ± 148.1 | 422.8 ± 228.3 | 4783.8 ± 1533.2 | 1108.6 ± 691.2 | 0.88 ± 0.03 | 0.2 ± 1.1 | 12.4 ± 3.3 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h1 | 193.1 ± 101.6 | 323.3 ± 170.6 | 78.7 ± 76.4 | 4990.1 ± 1995.9 | 201.8 ± 448.8 | 0.58 ± 0.07 | 0.5 ± 1.4 | 9.2 ± 3.3 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h2 | 468.4 ± 215.5 | 423.0 ± 177.5 | 456.3 ± 241.7 | 4713.4 ± 2068.8 | 1224.7 ± 723.9 | 0.88 ± 0.03 | 0.2 ± 1.1 | 12.7 ± 3.9 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h3 | 209.0 ± 121.3 | 338.4 ± 187.8 | 92.7 ± 90.1 | 5020.7 ± 2097.9 | 234.5 ± 523.6 | 0.58 ± 0.08 | 0.6 ± 1.5 | 9.3 ± 3.4 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| random | 16708.4 ± 1084.5 | 17100.7 ± 914.6 | 15992.2 ± 1450.9 | 26863.0 ± 2271.3 | 37944.9 ± 1547.5 | 0.44 ± 0.09 | 247.6 ± 24.8 | 258.9 ± 24.6 | 302.2 ± 28.5 | 0.0 ± 0.0 |
| always_wait | 31809.5 ± 1038.3 | 31751.0 ± 870.6 | 31861.6 ± 1384.1 | 32105.2 ± 2182.6 | 48963.4 ± 673.3 | 0.00 ± 0.00 | 490.9 ± 36.2 | 490.9 ± 36.2 | 0.0 ± 0.0 | 0.0 ± 0.0 |

**Paired differences** (policy minus reference; negative = policy is better; 95% bootstrap CI; win = share of streams where the policy is better)

| Policy | Metric | vs | Mean diff | 95% CI | Win rate |
|---|---|---|---|---|---|
| b1 | acuity_weighted_avg_wait_min | h1 | 247.5 | [186.6, 312.5] | 0% |
| b1 | avg_wait_incl_unadmitted_min | h1 | 81.5 | [33.1, 128.3] | 25% |
| b1 | critical_avg_wait_min | h1 | 344.1 | [266.6, 423.5] | 0% |
| h1 | acuity_weighted_avg_wait_min | b1 | -247.5 | [-312.5, -186.6] | 100% |
| h1 | avg_wait_incl_unadmitted_min | b1 | -81.5 | [-128.3, -33.1] | 75% |
| h1 | critical_avg_wait_min | b1 | -344.1 | [-423.5, -266.6] | 100% |
| h2 | acuity_weighted_avg_wait_min | b1 | 27.8 | [10.0, 48.2] | 15% |
| h2 | acuity_weighted_avg_wait_min | h1 | 275.3 | [207.1, 346.4] | 0% |
| h2 | avg_wait_incl_unadmitted_min | b1 | 18.1 | [-6.6, 46.2] | 35% |
| h2 | avg_wait_incl_unadmitted_min | h1 | 99.6 | [46.0, 155.9] | 25% |
| h2 | critical_avg_wait_min | b1 | 33.5 | [14.1, 58.6] | 0% |
| h2 | critical_avg_wait_min | h1 | 377.6 | [292.7, 467.0] | 0% |
| h3 | acuity_weighted_avg_wait_min | b1 | -231.6 | [-294.5, -174.6] | 100% |
| h3 | acuity_weighted_avg_wait_min | h1 | 15.9 | [0.3, 34.3] | 25% |
| h3 | avg_wait_incl_unadmitted_min | b1 | -66.4 | [-116.6, -14.9] | 75% |
| h3 | avg_wait_incl_unadmitted_min | h1 | 15.1 | [-4.4, 37.1] | 25% |
| h3 | critical_avg_wait_min | b1 | -330.1 | [-404.7, -260.9] | 100% |
| h3 | critical_avg_wait_min | h1 | 14.0 | [-0.4, 30.8] | 15% |
| random | acuity_weighted_avg_wait_min | b1 | 16267.8 | [15782.6, 16747.0] | 0% |
| random | acuity_weighted_avg_wait_min | h1 | 16515.3 | [16029.4, 16985.9] | 0% |
| random | avg_wait_incl_unadmitted_min | b1 | 16695.9 | [16280.7, 17089.1] | 0% |
| random | avg_wait_incl_unadmitted_min | h1 | 16777.4 | [16379.2, 17152.6] | 0% |
| random | critical_avg_wait_min | b1 | 15569.3 | [14930.0, 16217.6] | 0% |
| random | critical_avg_wait_min | h1 | 15913.5 | [15273.3, 16554.7] | 0% |
| always_wait | acuity_weighted_avg_wait_min | b1 | 31368.9 | [30891.4, 31848.0] | 0% |
| always_wait | acuity_weighted_avg_wait_min | h1 | 31616.4 | [31160.3, 32084.9] | 0% |
| always_wait | avg_wait_incl_unadmitted_min | b1 | 31346.1 | [30965.2, 31757.7] | 0% |
| always_wait | avg_wait_incl_unadmitted_min | h1 | 31427.7 | [31047.3, 31838.3] | 0% |
| always_wait | critical_avg_wait_min | b1 | 31438.8 | [30817.6, 32052.8] | 0% |
| always_wait | critical_avg_wait_min | h1 | 31782.9 | [31176.0, 32399.6] | 0% |

## moderate_surge (20 streams)

| Policy | Weighted wait (min) | Avg wait (min) | Critical wait (min) | Low-acuity isolation wait (min) | P90 wait (min) | ICU util | Still waiting | Peak queue | Invalid actions | Violations |
|---|---|---|---|---|---|---|---|---|---|---|
| b1 | 3392.9 ± 987.7 | 2746.7 ± 770.9 | 3933.5 ± 1184.7 | 12811.0 ± 2333.5 | 7331.9 ± 2215.6 | 0.95 ± 0.01 | 16.1 ± 9.4 | 105.0 ± 31.2 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h1 | 3096.2 ± 981.3 | 2623.6 ± 763.7 | 3483.9 ± 1170.8 | 13354.2 ± 3166.7 | 6858.5 ± 2153.8 | 0.88 ± 0.02 | 15.4 ± 9.1 | 101.2 ± 30.8 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h2 | 3428.0 ± 1003.3 | 2757.6 ± 777.4 | 3983.3 ± 1202.9 | 12678.9 ± 2630.5 | 7423.0 ± 2264.3 | 0.95 ± 0.01 | 16.9 ± 9.6 | 105.0 ± 31.4 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h3 | 3121.9 ± 987.1 | 2630.6 ± 753.8 | 3527.0 ± 1188.2 | 13386.7 ± 3077.7 | 7024.7 ± 2156.1 | 0.88 ± 0.02 | 16.1 ± 9.1 | 101.5 ± 31.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| random | 17012.7 ± 730.1 | 17223.0 ± 655.3 | 16387.7 ± 971.5 | 26632.4 ± 1765.0 | 37783.7 ± 1509.3 | 0.67 ± 0.06 | 434.3 ± 32.9 | 454.2 ± 32.3 | 526.1 ± 36.1 | 0.0 ± 0.0 |
| always_wait | 31714.1 ± 858.8 | 31665.9 ± 612.2 | 31677.5 ± 1326.3 | 32081.6 ± 1541.9 | 49072.7 ± 518.2 | 0.00 ± 0.00 | 844.4 ± 46.4 | 844.4 ± 46.4 | 0.0 ± 0.0 | 0.0 ± 0.0 |

**Paired differences** (policy minus reference; negative = policy is better; 95% bootstrap CI; win = share of streams where the policy is better)

| Policy | Metric | vs | Mean diff | 95% CI | Win rate |
|---|---|---|---|---|---|
| b1 | acuity_weighted_avg_wait_min | h1 | 296.7 | [203.5, 392.5] | 10% |
| b1 | avg_wait_incl_unadmitted_min | h1 | 123.1 | [72.8, 179.1] | 20% |
| b1 | critical_avg_wait_min | h1 | 449.6 | [310.9, 593.0] | 0% |
| h1 | acuity_weighted_avg_wait_min | b1 | -296.7 | [-392.5, -203.5] | 90% |
| h1 | avg_wait_incl_unadmitted_min | b1 | -123.1 | [-179.1, -72.8] | 80% |
| h1 | critical_avg_wait_min | b1 | -449.6 | [-593.0, -310.9] | 100% |
| h2 | acuity_weighted_avg_wait_min | b1 | 35.1 | [12.3, 59.1] | 5% |
| h2 | acuity_weighted_avg_wait_min | h1 | 331.8 | [236.0, 431.6] | 5% |
| h2 | avg_wait_incl_unadmitted_min | b1 | 10.9 | [-9.5, 34.5] | 40% |
| h2 | avg_wait_incl_unadmitted_min | h1 | 134.0 | [75.4, 197.1] | 20% |
| h2 | critical_avg_wait_min | b1 | 49.7 | [23.4, 77.3] | 5% |
| h2 | critical_avg_wait_min | h1 | 499.3 | [357.3, 644.3] | 0% |
| h3 | acuity_weighted_avg_wait_min | b1 | -271.0 | [-362.0, -180.3] | 90% |
| h3 | acuity_weighted_avg_wait_min | h1 | 25.7 | [4.2, 52.8] | 20% |
| h3 | avg_wait_incl_unadmitted_min | b1 | -116.2 | [-175.4, -62.5] | 75% |
| h3 | avg_wait_incl_unadmitted_min | h1 | 6.9 | [-5.8, 20.8] | 35% |
| h3 | critical_avg_wait_min | b1 | -406.5 | [-536.5, -278.9] | 95% |
| h3 | critical_avg_wait_min | h1 | 43.1 | [5.1, 88.2] | 20% |
| random | acuity_weighted_avg_wait_min | b1 | 13619.8 | [13164.0, 14119.2] | 0% |
| random | acuity_weighted_avg_wait_min | h1 | 13916.6 | [13437.8, 14434.1] | 0% |
| random | avg_wait_incl_unadmitted_min | b1 | 14476.2 | [14094.2, 14927.4] | 0% |
| random | avg_wait_incl_unadmitted_min | h1 | 14599.3 | [14222.3, 15050.3] | 0% |
| random | critical_avg_wait_min | b1 | 12454.1 | [11845.0, 13074.5] | 0% |
| random | critical_avg_wait_min | h1 | 12903.7 | [12264.6, 13557.4] | 0% |
| always_wait | acuity_weighted_avg_wait_min | b1 | 28321.2 | [27767.3, 28894.7] | 0% |
| always_wait | acuity_weighted_avg_wait_min | h1 | 28617.9 | [28036.2, 29220.5] | 0% |
| always_wait | avg_wait_incl_unadmitted_min | b1 | 28919.2 | [28523.2, 29346.0] | 0% |
| always_wait | avg_wait_incl_unadmitted_min | h1 | 29042.3 | [28644.7, 29472.6] | 0% |
| always_wait | critical_avg_wait_min | b1 | 27743.9 | [27012.3, 28482.1] | 0% |
| always_wait | critical_avg_wait_min | h1 | 28193.6 | [27398.2, 28996.0] | 0% |

## severe_surge (10 streams)

| Policy | Weighted wait (min) | Avg wait (min) | Critical wait (min) | Low-acuity isolation wait (min) | P90 wait (min) | ICU util | Still waiting | Peak queue | Invalid actions | Violations |
|---|---|---|---|---|---|---|---|---|---|---|
| b1 | 14095.5 ± 588.6 | 13724.0 ± 616.7 | 14463.2 ± 561.4 | 21124.4 ± 1794.6 | 23059.1 ± 1041.1 | 0.97 ± 0.01 | 528.4 ± 55.7 | 707.8 ± 57.1 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h1 | 13969.5 ± 580.4 | 13851.3 ± 615.3 | 14124.2 ± 555.8 | 21765.3 ± 2156.9 | 23083.4 ± 1032.4 | 0.94 ± 0.01 | 529.3 ± 56.4 | 709.8 ± 57.0 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h2 | 14109.9 ± 590.2 | 13728.5 ± 607.9 | 14488.5 ± 572.5 | 21191.7 ± 1909.4 | 23150.5 ± 982.2 | 0.97 ± 0.01 | 532.1 ± 53.0 | 707.8 ± 57.1 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| h3 | 13975.0 ± 576.7 | 13844.9 ± 619.6 | 14140.4 ± 540.3 | 21551.2 ± 2222.6 | 23089.7 ± 1039.7 | 0.94 ± 0.01 | 529.0 ± 56.8 | 710.0 ± 56.9 | 0.0 ± 0.0 | 0.0 ± 0.0 |
| random | 19426.5 ± 538.2 | 19063.7 ± 489.2 | 19927.5 ± 581.9 | 28211.7 ± 1774.7 | 40070.1 ± 724.3 | 0.86 ± 0.02 | 878.1 ± 47.6 | 905.6 ± 45.9 | 961.3 ± 47.4 | 0.0 ± 0.0 |
| always_wait | 31838.0 ± 364.4 | 31750.7 ± 365.7 | 31861.1 ± 530.1 | 32174.9 ± 1539.3 | 49098.2 ± 523.1 | 0.00 ± 0.00 | 1504.1 ± 52.7 | 1504.1 ± 52.7 | 0.0 ± 0.0 | 0.0 ± 0.0 |

**Paired differences** (policy minus reference; negative = policy is better; 95% bootstrap CI; win = share of streams where the policy is better)

| Policy | Metric | vs | Mean diff | 95% CI | Win rate |
|---|---|---|---|---|---|
| b1 | acuity_weighted_avg_wait_min | h1 | 126.0 | [88.2, 170.1] | 0% |
| b1 | avg_wait_incl_unadmitted_min | h2 | -4.5 | [-29.2, 15.0] | 20% |
| b1 | critical_avg_wait_min | h1 | 339.0 | [255.5, 442.7] | 0% |
| h1 | acuity_weighted_avg_wait_min | b1 | -126.0 | [-170.1, -88.2] | 100% |
| h1 | avg_wait_incl_unadmitted_min | b1 | 127.3 | [88.3, 165.7] | 0% |
| h1 | avg_wait_incl_unadmitted_min | h2 | 122.8 | [75.8, 165.8] | 10% |
| h1 | critical_avg_wait_min | b1 | -339.0 | [-442.7, -255.5] | 100% |
| h2 | acuity_weighted_avg_wait_min | b1 | 14.4 | [1.0, 33.3] | 0% |
| h2 | acuity_weighted_avg_wait_min | h1 | 140.4 | [93.7, 191.6] | 0% |
| h2 | avg_wait_incl_unadmitted_min | b1 | 4.5 | [-15.0, 29.2] | 20% |
| h2 | critical_avg_wait_min | b1 | 25.3 | [4.3, 50.5] | 0% |
| h2 | critical_avg_wait_min | h1 | 364.3 | [274.6, 468.6] | 0% |
| h3 | acuity_weighted_avg_wait_min | b1 | -120.6 | [-158.1, -86.3] | 100% |
| h3 | acuity_weighted_avg_wait_min | h1 | 5.4 | [-1.3, 14.5] | 20% |
| h3 | avg_wait_incl_unadmitted_min | b1 | 120.9 | [79.1, 161.6] | 0% |
| h3 | avg_wait_incl_unadmitted_min | h2 | 116.4 | [68.0, 161.3] | 10% |
| h3 | critical_avg_wait_min | b1 | -322.8 | [-412.2, -245.6] | 100% |
| h3 | critical_avg_wait_min | h1 | 16.2 | [-1.2, 38.4] | 10% |
| random | acuity_weighted_avg_wait_min | b1 | 5331.0 | [5068.3, 5621.4] | 0% |
| random | acuity_weighted_avg_wait_min | h1 | 5457.0 | [5190.3, 5744.3] | 0% |
| random | avg_wait_incl_unadmitted_min | b1 | 5339.7 | [4985.7, 5706.4] | 0% |
| random | avg_wait_incl_unadmitted_min | h2 | 5335.3 | [4978.7, 5709.6] | 0% |
| random | critical_avg_wait_min | b1 | 5464.3 | [5145.8, 5764.3] | 0% |
| random | critical_avg_wait_min | h1 | 5803.3 | [5512.4, 6076.4] | 0% |
| always_wait | acuity_weighted_avg_wait_min | b1 | 17742.4 | [17387.2, 18111.4] | 0% |
| always_wait | acuity_weighted_avg_wait_min | h1 | 17868.5 | [17510.5, 18228.7] | 0% |
| always_wait | avg_wait_incl_unadmitted_min | b1 | 18026.7 | [17570.8, 18498.9] | 0% |
| always_wait | avg_wait_incl_unadmitted_min | h2 | 18022.2 | [17567.9, 18489.8] | 0% |
| always_wait | critical_avg_wait_min | b1 | 17397.9 | [17085.9, 17721.8] | 0% |
| always_wait | critical_avg_wait_min | h1 | 17736.9 | [17401.7, 18084.1] | 0% |
