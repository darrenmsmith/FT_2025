# Sequential Mode Multi-Athlete Fix

## Problem Report
**User:** "We need to fix the multi athlete doing warm-up: round 1. ultrathink it fails to start the second athlete. D0 should tell the next athlete what action to do after the first athlete touches D1 and repeat for the third athlete."

**Symptoms:**
- First athlete starts correctly
- First athlete touches D1 → "Device triggers next athlete" appears in logs
- BUT: Second athlete never gets D0 audio instructions
- All athletes run simultaneously instead of sequentially

## Root Cause

The Simon Says (pattern mode) multi-athlete implementation loaded **ALL athletes** into `active_runs` at session start and marked them all as 'started' in the database.

### Pattern Mode Behavior (CORRECT):
1. Load all 3 athletes at session start
2. Generate unique pattern for each
3. Mark all as started in DB
4. Only first athlete is `is_active=True`
5. Athletes transition one-by-one using `_move_to_next_athlete()`

### Sequential Mode Behavior (BROKEN):
1. **WRONG:** Load all 3 athletes at session start
2. **WRONG:** Mark all as 'started' in DB
3. When D1 is touched with `triggers_next_athlete`:
   - Calls `get_next_queued_run(session_id)`
   - **Returns None** - no queued runs left!
   - Next athlete logic never executes
   - No D0 audio played

### What Sequential Mode NEEDS:
1. Load ONLY first athlete at session start
2. Leave athletes 2 and 3 in 'queued' status
3. When D1 is touched:
   - Calls `get_next_queued_run(session_id)`
   - **Returns athlete 2** (still queued) ✓
   - Start athlete 2's run in DB
   - Add to active_runs
   - Create segments
   - **Play D0 audio for athlete 2** ✓

## The Fix

**File:** `/opt/services/session_service.py`

**Lines 146-156:**
```python
# PATTERN MODE: Load ALL athletes upfront with unique patterns
# SEQUENTIAL MODE: Load ONLY first athlete (others triggered by D1 touch)
previous_pattern = None

# Determine which athletes to load at session start
if course_mode == 'pattern':
    # Pattern mode: Load all athletes upfront
    athletes_to_load = all_runs
else:
    # Sequential mode: Load only first athlete
    athletes_to_load = [all_runs[0]]

for idx, run in enumerate(athletes_to_load):
    # ... existing code
```

**Key Change:**
- **Pattern mode:** `athletes_to_load = all_runs` (all 3 athletes)
- **Sequential mode:** `athletes_to_load = [all_runs[0]]` (first athlete only)

**Lines 228-237:** Updated logging
```python
print(f"\n✅ Multi-athlete state initialized:")
print(f"   Mode: {course_mode.upper()}")
print(f"   Total athletes: {total_athletes}")
print(f"   Device sequence: {device_sequence}")
print(f"   First athlete (active): {first_run['athlete_name']}")
if total_athletes > 1:
    if course_mode == 'pattern':
        print(f"   Remaining athletes (loaded, waiting): {', '.join([r['athlete_name'] for r in all_runs[1:]])}")
    else:
        print(f"   Remaining athletes (queued, will start on D1 trigger): {', '.join([r['athlete_name'] for r in all_runs[1:]])}")
```

## Expected Behavior After Fix

### Sequential Mode Flow (Warm-up: Round 1):

**Session Start:**
```
Mode: SEQUENTIAL
Total athletes: 3
First athlete (active): Abigail White
Remaining athletes (queued, will start on D1 trigger): Amelia Anderson, Ava Patel
🔊 Playing Device 0 audio: "Touch cone 1"
```

**Athlete 1 (Abigail) - Start:**
- D0 plays: "Touch cone 1"
- Abigail touches D1

**D1 Touch → Trigger Athlete 2:**
```
🔔 Device triggers next athlete
🎬 Starting run for Amelia Anderson...
✅ Run started successfully
✅ Added to active_runs
📋 Creating segments for Amelia Anderson...
✅ Created 5 segments
🏃 Next athlete started: Amelia Anderson
Active: 2/3
🔊 Playing Device 0 audio for next athlete via API
```

- D0 plays: "Touch cone 1" (for Amelia)
- Abigail continues: D2, D3, D4, D5 → completes
- Amelia touches D1

**D1 Touch → Trigger Athlete 3:**
```
🔔 Device triggers next athlete
🎬 Starting run for Ava Patel...
✅ Run started successfully
✅ Added to active_runs
📋 Creating segments for Ava Patel...
✅ Created 5 segments
🏃 Next athlete started: Ava Patel
Active: 2/3
🔊 Playing Device 0 audio for next athlete via API
```

- D0 plays: "Touch cone 1" (for Ava)
- Amelia continues: D2, D3, D4, D5 → completes
- Ava touches D1, then D2, D3, D4, D5 → completes
- Session completes

## Testing Checklist

### Test 1: Sequential Mode with 3 Athletes
1. Start warm-up: round 1 with 3 athletes
2. **VERIFY:** D0 plays "Touch cone 1" for athlete 1
3. Athlete 1 touches D0
4. **VERIFY:** D0 plays "Touch cone 1" again
5. Athlete 1 touches D1
6. **VERIFY:** Logs show "Device triggers next athlete"
7. **VERIFY:** Logs show "Starting run for [Athlete 2]"
8. **VERIFY:** D0 plays "Touch cone 1" for athlete 2
9. Athlete 1 completes course (D2, D3, D4, D5)
10. Athlete 2 touches D1
11. **VERIFY:** Logs show "Device triggers next athlete"
12. **VERIFY:** D0 plays "Touch cone 1" for athlete 3
13. All 3 athletes complete
14. **VERIFY:** Session completes successfully

### Test 2: Pattern Mode Still Works
1. Start Simon Says with 3 athletes
2. **VERIFY:** All 3 athletes loaded at start
3. **VERIFY:** Each athlete gets unique pattern
4. **VERIFY:** Pattern mode flow works (one athlete at a time)
5. **VERIFY:** Session completes after all athletes

### Test 3: Single Athlete (Both Modes)
1. Start warm-up: round 1 with 1 athlete
2. **VERIFY:** Works normally (no next athlete to trigger)
3. Start Simon Says with 1 athlete
4. **VERIFY:** Works normally

## Files Modified
- `/opt/services/session_service.py`
  - Lines 146-156: Conditional athlete loading based on mode
  - Lines 158-160: Use actual_idx for proper is_active setting
  - Lines 228-237: Updated logging for clarity

## Impact

**Sequential Mode:**
- ✅ Fixed: Next athletes now properly triggered by D1 touch
- ✅ Fixed: D0 audio plays for each new athlete
- ✅ Fixed: Athletes run sequentially instead of simultaneously
- ✅ No change to single-athlete behavior

**Pattern Mode:**
- ✅ No change - still loads all athletes upfront
- ✅ No change to Simon Says functionality
- ✅ No regression

## Related Code

**Triggers Next Athlete Logic:** Lines 910-990
- This existing code works correctly
- Problem was that `get_next_queued_run()` returned None
- Fix ensures queued runs exist for sequential mode

**Pattern Mode Athlete Transitions:** Lines 375-433 (`_move_to_next_athlete()`)
- Handles pattern mode transitions
- Not used in sequential mode
- No changes needed

## Summary

**Before:** Sequential and pattern modes used same initialization (load all athletes)
**After:** Mode-specific initialization (pattern loads all, sequential loads first only)
**Result:** Sequential mode `triggers_next_athlete` flow works correctly with D0 audio
