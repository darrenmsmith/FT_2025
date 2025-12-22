# Critical Bug Fix: Session Ending Prematurely When Athlete Fails

## Problem Report (Test 5)
**User Report:** "ended session, should have only failed Abigail not the whole session"

When Abigail failed her pattern, the entire session ended instead of moving to Amelia and Ava.

## Root Cause Analysis

### The Bug
When an athlete made a wrong touch:

1. **Line 725** (OLD): `run_info['is_active'] = False`
   - Marked athlete INACTIVE to prevent touches during error feedback

2. **Line 799** (after error feedback): Called `_move_to_next_athlete()`

3. **Line 382** in `_move_to_next_athlete()`:
   ```python
   if run_info.get('is_active', False):  # Looking for TRUE
       current_run_id = run_id
   ```
   - Searched for athlete with `is_active = True`
   - But we JUST set it to False at line 725!
   - **Result**: Can't find current athlete → returns False → session ends

### Why This Happened
We marked the athlete inactive EARLY to prevent touches during the 4-second error feedback animation. This broke the `_move_to_next_athlete()` logic which relies on finding the currently-active athlete.

## The Fix

### Part 1: Block Touches During Error Feedback (New: Lines 671-675)
```python
# Block touches during error feedback (athlete is still marked active, but feedback is playing)
if self.registry.error_feedback_active:
    print(f"🚫 ERROR FEEDBACK ACTIVE - Touch ignored (feedback animation playing)")
    print(f"{'='*80}\n")
    return
```

**Why This Works:**
- `error_feedback_active` flag already existed (set at line 727)
- Check this flag BEFORE processing touches
- Athlete remains `is_active = True` during error feedback
- `_move_to_next_athlete()` can find them correctly

### Part 2: Don't Mark Inactive Early (Updated: Lines 725-731)
```python
# Set error_feedback_active to block further touches during error animation
# This also blocks heartbeat LED commands during error feedback
self.registry.error_feedback_active = True
print(f"   🚫 Error feedback active - touches blocked, heartbeat LED commands blocked")

# NOTE: We do NOT mark athlete as inactive here - _move_to_next_athlete() will do that
# Marking inactive early would prevent _move_to_next_athlete() from finding current athlete
```

**Removed:**
```python
# CRITICAL: Mark athlete as INACTIVE immediately to prevent further touch processing
run_info['is_active'] = False
print(f"   🚫 Athlete marked INACTIVE - no further touches will be processed")
```

**Why This Works:**
- Athlete stays `is_active = True` during error feedback
- Touches are blocked by checking `error_feedback_active` flag (Part 1)
- `_move_to_next_athlete()` can find the current athlete at line 382
- `_move_to_next_athlete()` marks them inactive at line 385 (as designed)

## Test Results (From Logs)

### Test 5 - Before Fix (16:39:45 session)
```
Dec 20 16:40:17: ❌ Pattern Error: Abigail White touched Cone 4 but expected BLUE (Cone 3)
Dec 20 16:40:23: ❌ Abigail White failed after 16.97 seconds
Dec 20 16:40:23: 🎉 All athletes complete - completing session d6abcd9a...
```

**Result:** Session ended after Abigail failed (WRONG!)

### Expected Behavior - After Fix
```
1. Abigail makes wrong touch
2. Error feedback plays (chase red, 4 seconds)
3. Touches during error feedback ignored via error_feedback_active check
4. _move_to_next_athlete() called:
   - Finds Abigail (is_active=True)
   - Marks Abigail inactive
   - Marks Amelia active
   - Displays Amelia's pattern
   - Returns True
5. Session continues with Amelia
6. After Amelia: Continues with Ava
7. After Ava: Session completes
```

## Files Modified
- `/opt/services/session_service.py`
  - Lines 671-675: Added error_feedback_active check
  - Lines 725-731: Updated to NOT mark inactive early

## Related Systems

### Success Path (D0 Touch After Completing Pattern)
- No changes needed
- Line 636: Calls `_move_to_next_athlete()`
- Athlete is still `is_active=True`
- Works correctly

### Error Feedback Flag
- `registry.error_feedback_active` set at line 727 (on error)
- Cleared at line 769 (after error feedback completes)
- Now also checked at line 672 to block touches

## Testing Recommendations

### Test A: Athlete Fails Mid-Pattern
1. Start session with 3 athletes
2. Athlete 1 touches wrong device at step 2/4
3. **VERIFY**: Chase red plays, touches ignored
4. **VERIFY**: Session moves to Athlete 2 (not ending)
5. Athlete 2 completes successfully
6. **VERIFY**: Session moves to Athlete 3
7. Athlete 3 completes successfully
8. **VERIFY**: Session ends after all 3 athletes

### Test B: Multiple Athletes Fail
1. Start session with 3 athletes
2. Athlete 1 fails
3. **VERIFY**: Moves to Athlete 2
4. Athlete 2 fails
5. **VERIFY**: Moves to Athlete 3
6. Athlete 3 completes
7. **VERIFY**: Session ends

### Test C: Touches During Error Feedback
1. Athlete touches wrong device
2. Chase red starts playing
3. **Touch other devices during 4-second animation**
4. **VERIFY**: All touches ignored (logs show "ERROR FEEDBACK ACTIVE")
5. **VERIFY**: Session moves to next athlete after error feedback

## Summary

**Before:** Marking athlete inactive early broke multi-athlete flow when failures occurred.
**After:** Use `error_feedback_active` flag to block touches, keep athlete active so `_move_to_next_athlete()` works correctly.

**Impact:** Multi-athlete sessions now work correctly when athletes fail patterns.
