# Stage 3 baseline - 2026-09-22

Captured before any change in this branch. Every later claim about what moved is
measured against this file.

## case-jacksonville-2024

- ais_source `noaa_dense` - funnel 32 -> 22 -> 3 -> 3 (dropped_short 0)
- abstained **False** - None
- origin centroid [-79.69132, 30.1539] r50 14.67 r90 33.94
- window 2024-07-30T09:51:29Z .. 2024-07-30T22:51:29Z (`age`)
- age_method `combined` gate `chronic_track` hours [0.5, 13.5]
- age_estimators {'shear': None, 'fay': None, 'elongation': None, 'track': [0.2, 9.5]}
- posterior median 2.8 hpd80 [0.5, 13.5] grid 1.0..72.0 mode 1.0 mass_in_lowest_cell 0.30986
- particles 97 steps x 45 min = 72.0 h

| rank | mmsi | name | score | weight_live | prox | gap | slow | traj | temp | type |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 210145000 | STENA PROSPEROUS | 0.734 | 0.85 | 0.859 | 1.000 | 0.000 | 1.000 | 0.109 | 1.000 |
| 2 | 563082600 | MENUETT | 0.593 | 0.85 | 0.926 | 0.000 | 0.000 | 1.000 | 0.173 | 1.000 |
| 3 | 338305838 | PATRIOT | 0.569 | 0.85 | 0.051 | 1.000 | 0.000 | 1.000 | 0.956 | 0.500 |

dark_vessels: [(0.991, -79.6346, 30.35297), (0.892, -79.59244, 30.3918)]

excluded: [('368053000', 'MAERSK KANSAS'), ('352476000', 'MANIZALES'), ('352980797', 'AMETHYST ACE')]

## case-farallones-2023

- ais_source `noaa_dense` - funnel 11 -> 8 -> 3 -> 0 (dropped_short 0)
- abstained **True** - the top two vessels score within a few percent of each other and cannot be separated on this evidence
- origin centroid [-123.89651, 37.85042] r50 5.46 r90 12.35
- window 2023-03-16T19:54:42Z .. 2023-03-17T13:54:42Z (`age`)
- age_method `combined` gate `chronic_track` hours [0.5, 18.5]
- age_estimators {'shear': None, 'fay': None, 'elongation': None, 'track': [1.0, 19.6]}
- posterior median 3.9 hpd80 [0.5, 18.5] grid 1.0..72.0 mode 1.0 mass_in_lowest_cell 0.24336
- particles 97 steps x 45 min = 72.0 h

**no suspects named**

excluded: [('248264000', 'TUGELA'), ('212656000', 'PANAGIA THALASSINI'), ('636016487', 'HORIZON')]

## case-gulf-alaska-2023

- ais_source `gfw_hourly` - funnel 14 -> 12 -> 2 -> 2 (dropped_short 1)
- abstained **False** - None
- origin centroid [-142.75863, 59.55186] r50 1.27 r90 2.89
- window 2023-05-16T04:27:08Z .. 2023-05-16T15:27:08Z (`age`)
- age_method `combined` gate `chronic_track` hours [0.5, 11.5]
- age_estimators {'shear': None, 'fay': None, 'elongation': None, 'track': [0.0, 5.2]}
- posterior median 2.0 hpd80 [0.5, 11.5] grid 1.0..72.0 mode 1.0 mass_in_lowest_cell 0.37574
- particles 97 steps x 45 min = 72.0 h

| rank | mmsi | name | score | weight_live | prox | gap | slow | traj | temp | type |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 941201607 | 941201607      11.7V | 0.273 | 0.45 | 0.269 | null | null | null | 0.281 | null |
| 2 | 941214805 | 941214805 | 0.225 | 0.45 | 0.287 | null | null | null | 0.100 | null |

excluded: [('941205333', '941205333      11.5V'), ('367415050', 'INTANGIBLE'), ('941216622', 'MAJOR BUOY 4')]

## case-huntington-2021

- ais_source `noaa_dense` - funnel 596 -> 514 -> 7 -> 3 (dropped_short 12)
- abstained **False** - None
- origin centroid [-118.14432, 33.53277] r50 3.8 r90 7.1
- window 2021-10-01T17:41:51Z .. 2021-10-01T19:58:21Z (`convergence`)
- age_method `none` gate `unknown_both` hours None
- age_estimators {'shear': [12.5, 64.4], 'fay': None, 'elongation': [9.4, 32.2], 'track': [1.5, 28.6]}
- age_refusal None
- particles 97 steps x 45 min = 72.0 h

| rank | mmsi | name | score | weight_live | prox | gap | slow | traj | temp | type |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 368117160 | GOOD JU JU | 0.58 | 0.85 | 0.795 | 0.000 | 0.000 | 1.000 | 0.527 | 0.500 |
| 2 | 372914000 | MORNING CONDUCTOR | 0.497 | 0.7 | 0.276 | null | 0.000 | 1.000 | 0.432 | 1.000 |
| 3 | 367492920 | KENNETH CARL | 0.415 | 0.7 | 0.219 | null | 1.000 | 1.000 | 0.002 | 0.500 |

excluded: [('338120738', 'PER AMORE'), ('368014440', 'MONTE CARLO'), ('367393270', 'NICHOLAS L')]

## case-mumbai-2023

- ais_source `gfw_hourly` - funnel 74 -> 66 -> 28 -> 3 (dropped_short 3)
- abstained **False** - None
- origin centroid [71.90433, 18.90696] r50 7.25 r90 11.07
- window 2023-08-31T01:03:33Z .. 2023-09-02T01:03:33Z (`bounded`)
- age_method `none` gate `unknown_both` hours None
- age_estimators {'shear': [18.3, 58.0], 'fay': None, 'elongation': None, 'track': [1.0, 19.7]}
- age_refusal None
- particles 97 steps x 45 min = 72.0 h

| rank | mmsi | name | score | weight_live | prox | gap | slow | traj | temp | type |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 419001555 | OLYMPUS | 0.888 | 0.35 | 0.953 | null | null | null | null | 0.500 |
| 2 | 636019523 | LISA | 0.781 | 0.35 | 0.745 | null | null | null | null | 1.000 |
| 3 | 353728000 | MSC MADELEINE | 0.781 | 0.35 | 0.745 | null | null | null | null | 1.000 |

excluded: [('419001628', 'SAGAR ENERGY'), ('419001116', 'OCEAN TURQUOISE'), ('419663000', 'KAMET')]

## case-jamnagar-2024

- ais_source `gfw_hourly` - funnel 111 -> 102 -> 21 -> 0 (dropped_short 3)
- abstained **True** - the top two vessels score within a few percent of each other and cannot be separated on this evidence
- origin centroid [71.2627, 20.49169] r50 14.1 r90 21.31
- window 2024-02-20T01:11:14Z .. 2024-02-22T01:11:14Z (`bounded`)
- age_method `none` gate `unknown_both` hours None
- age_estimators {'shear': [25.4, 67.0], 'fay': None, 'elongation': [70.6, 72.0], 'track': [0.8, 15.8]}
- age_refusal None
- particles 97 steps x 45 min = 72.0 h

**no suspects named**

excluded: [('419012000', 'AMBUJA SHIKHAR'), ('219216000', 'MAERSK BOSTON'), ('419476000', 'AMBUJA SHAKTI')]
