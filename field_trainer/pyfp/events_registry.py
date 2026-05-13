EVENTS = {
    "pyfp_pacer":            {"rubrics": {"fitnessgram_hfz", "pft_2026"}, "category": "aerobic",     "engine": "beep_test_bridge"},
    "pyfp_mile_run":         {"rubrics": {"fitnessgram_hfz", "pft_2026"}, "category": "aerobic",     "engine": "mile_service"},
    "pyfp_mile_walk":        {"rubrics": {"fitnessgram_hfz"},             "category": "aerobic",     "engine": "mile_service"},
    "pyfp_curl_up":          {"rubrics": {"fitnessgram_hfz", "pft_2026"}, "category": "core",        "engine": "cadence"},
    "pyfp_push_up":          {"rubrics": {"fitnessgram_hfz", "pft_2026"}, "category": "upper",       "engine": "cadence"},
    "pyfp_pull_up":          {"rubrics": {"fitnessgram_hfz", "pft_2026"}, "category": "upper",       "engine": "manual_count"},
    "pyfp_modified_pull_up": {"rubrics": {"fitnessgram_hfz"},             "category": "upper",       "engine": "manual_count"},
    "pyfp_flexed_arm_hang":  {"rubrics": {"fitnessgram_hfz"},             "category": "upper",       "engine": "timer"},
    "pyfp_plank":            {"rubrics": {"pft_2026"},                    "category": "core",        "engine": "timer"},
    "pyfp_trunk_lift":       {"rubrics": {"fitnessgram_hfz"},             "category": "trunk",       "engine": "manual_measure"},
    "pyfp_sit_and_reach":    {"rubrics": {"fitnessgram_hfz"},             "category": "flexibility", "engine": "manual_measure"},
    "pyfp_shoulder_stretch": {"rubrics": {"fitnessgram_hfz"},             "category": "flexibility", "engine": "manual_passfail"},
    "pyfp_v_sit_reach":      {"rubrics": {"fitnessgram_hfz"},             "category": "flexibility", "engine": "manual_measure"},
    "pyfp_shuttle_run":      {"rubrics": {"fitnessgram_hfz"},             "category": "agility",     "engine": "shuttle_service"},
    "pyfp_bmi":              {"rubrics": {"fitnessgram_hfz"},             "category": "body_comp",   "engine": "manual_measure"},
    "pyfp_skinfold":         {"rubrics": {"fitnessgram_hfz"},             "category": "body_comp",   "engine": "manual_measure"},
}


def events_for_rubric(rubric: str) -> list[str]:
    if rubric == "both":
        return list(EVENTS.keys())
    return [k for k, v in EVENTS.items() if rubric in v["rubrics"]]
