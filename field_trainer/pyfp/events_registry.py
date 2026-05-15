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

# Coach-facing descriptions shown on setup and recording pages.
EVENT_DESCRIPTIONS = {
    "pyfp_pacer": (
        "20-meter Progressive Aerobic Cardiovascular Endurance Run (PACER). "
        "Athlete shuttles between two lines 20 m apart, keeping pace with audio beeps "
        "that increase in speed each level. Test ends when the athlete fails to reach "
        "the line before the beep twice."
    ),
    "pyfp_mile_run": (
        "Timer starts at GO and stops when the athlete crosses the finish line."
    ),
    "pyfp_mile_walk": (
        "One-Mile Walk. Athlete walks one mile without running. Timer starts at GO and "
        "stops when the athlete crosses the finish line. Scored on elapsed time — "
        "lower is better."
    ),
    "pyfp_curl_up": (
        "Curl-Up. Athlete performs as many curl-ups as possible to a cadence beep "
        "(3 seconds per rep). Hands slide along a measuring strip; elbows must touch "
        "knees on the way up. Test ends when the athlete cannot keep pace."
    ),
    "pyfp_push_up": (
        "Right-Angle Push-Up. Athlete performs as many push-ups as possible to a "
        "cadence beep (3 seconds per rep), lowering until the upper arm is parallel "
        "to the floor (90° elbow angle). Test ends when the athlete cannot keep pace."
    ),
    "pyfp_pull_up": (
        "Pull-Up. Athlete hangs from a bar with an overhand grip and performs as many "
        "full pull-ups as possible without a time limit. Chin must clear the bar on "
        "each rep; no kipping or swinging."
    ),
    "pyfp_modified_pull_up": (
        "Modified Pull-Up. Athlete lies beneath a bar set at shoulder height, grips "
        "the bar overhand, and pulls until the chin reaches the bar. Body stays "
        "straight; heels remain on the floor. Count as many reps as possible."
    ),
    "pyfp_flexed_arm_hang": (
        "Flexed-Arm Hang. Athlete grips a bar with an overhand grip and holds the "
        "chin above the bar as long as possible. Timer starts when the athlete is in "
        "position and stops when the chin drops to or below bar level."
    ),
    "pyfp_plank": (
        "Plank. Athlete holds a prone plank position (forearms on floor, body straight) "
        "as long as possible. Timer starts when position is assumed and stops when "
        "form breaks (hips drop or raise significantly)."
    ),
    "pyfp_trunk_lift": (
        "Trunk Lift. Athlete lies face-down with hands under thighs. Lifts the upper "
        "body as high as possible using back muscles only and holds for a measurement. "
        "Scored in inches; maximum recorded score is 12 inches."
    ),
    "pyfp_sit_and_reach": (
        "Back-Saver Sit-and-Reach. Athlete sits with one leg extended against a "
        "sit-and-reach box, the other knee bent, and reaches as far forward as possible "
        "along the ruler. Each leg is measured separately."
    ),
    "pyfp_shoulder_stretch": (
        "Shoulder Stretch. Athlete reaches one hand over the shoulder and the other "
        "behind the back and attempts to touch fingertips. Scored pass/fail for each "
        "side independently. Both sides passing = full HFZ credit."
    ),
    "pyfp_v_sit_reach": (
        "V-Sit Reach. Athlete sits with legs straight and feet shoulder-width apart "
        "on a marked line, then reaches forward as far as possible along a ruler "
        "placed between the legs. Up to 3 attempts; best score recorded."
    ),
    "pyfp_shuttle_run": (
        "4×30 ft Shuttle Run. Athlete starts at Endpoint A, sprints to Endpoint B "
        "(touch/tag), returns to A (touch), sprints to B (touch), and finishes back "
        "at A. Touch sequence: B → A → B → A. Scored on total elapsed time — "
        "lower is better."
    ),
    "pyfp_bmi": (
        "Body Mass Index. BMI is calculated from height and weight "
        "(weight in lbs × 703 ÷ height in inches²). Healthy range is age- and "
        "gender-specific based on CDC growth charts."
    ),
    "pyfp_skinfold": (
        "Skinfold Body Composition. Triceps and calf skinfold thicknesses are measured "
        "in millimetres with calipers. Percent body fat is estimated using the "
        "Slaughter equation (varies by gender)."
    ),
}


def events_for_rubric(rubric: str) -> list[str]:
    if rubric == "both":
        return list(EVENTS.keys())
    return [k for k, v in EVENTS.items() if rubric in v["rubrics"]]
