# PYFP Scoring Tables

Swappable JSON scoring standards (D10). Each file corresponds to a row in `pyfp_scoring_table_version`.

| File | Rubric | Notes |
|---|---|---|
| `hfz_standards_2024.json` | fitnessgram_hfz | Cooper Institute FitnessGram HFZ 2024 (default) |
| `pft_85th_percentile_2010.json` | pft_2026 | Presidential Fitness Test 85th-percentile standards (2010 baseline) |
| `pft_2026_official.json` | pft_2026 | Placeholder — replace when PCSFN publishes official 2026 standards |

## JSON shape

```json
{
  "name": "...",
  "rubric": "fitnessgram_hfz | pft_2026",
  "events": {
    "pyfp_<event>": {
      "unit": "laps | seconds | count | inches | cm | kg | percent",
      "by_age_gender": {
        "male":   { "<age>": { "hfz_min": N, "hfz_max": N } },
        "female": { "<age>": { "hfz_min": N, "hfz_max": N } }
      }
    }
  }
}
```

Full tables populated in Phase 7.
