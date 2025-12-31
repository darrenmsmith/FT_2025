# Simon Says Pattern Drill - Development Plan

**Goal**: Implement full Simon Says functionality with visual pattern display, touch tracking, and pattern validation

---

## Current State (What Works)

✅ Course created with color assignments in Custom Rules
✅ 5 devices configured (1 home base + 4 colored cones)
✅ Diamond formation defined
✅ Device colors stored: Red, Green, Yellow, Blue

## What's Missing (From Screenshot)

❌ Device boxes don't show cone colors
❌ No pattern display when "Go" is clicked
❌ No pattern generation logic
❌ No touch sequence tracking
❌ No pattern validation (correct vs incorrect)
❌ No return-to-home-base requirement

---

## Step 1: Add Color Display to Session Monitor

### Files to Modify
- `/opt/field_trainer/templates/session_monitor.html` (or similar)
- Backend route that serves session data

### What to Add
1. **Extract colors from behavior_config** in backend
2. **Pass colors to template** as part of device data
3. **Apply color styling** to device boxes in HTML/CSS
4. **Display color name** on each device card

### Expected Result
Device boxes show:
- Device 1: Red background or border
- Device 2: Green background or border
- Device 3: Yellow background or border
- Device 4: Blue background or border
- Device 0: Gray/neutral (home base)

---

## Step 2: Pattern Generation Logic

### Files to Create/Modify
- New: `/opt/field_trainer/pattern_generator.py`
- Modify: Backend session start logic

### What to Implement
```python
def generate_simon_says_pattern(devices, difficulty, sequence_length):
    """
    Generate random pattern from colored devices

    Args:
        devices: List of device configs with colors
        difficulty: 1-5 (affects display speed)
        sequence_length: Number of devices in pattern (e.g., 4)

    Returns:
        pattern: ['red', 'yellow', 'blue', 'red']
        device_sequence: [101, 103, 104, 101]
    """
    # Extract colored devices (skip home base)
    colored_devices = [d for d in devices if 'color' in d.get('behavior_config', '')]

    # Extract colors
    colors = []
    for device in colored_devices:
        config = device['behavior_config']
        # Parse "color: red" from config string
        if 'color:' in config:
            color = extract_color(config)
            colors.append({'device_id': device['device_id'], 'color': color})

    # Generate random sequence
    import random
    pattern = random.choices(colors, k=sequence_length)

    return pattern
```

### Expected Result
When session starts, system generates pattern like:
- Pattern: [RED, YELLOW, BLUE, RED]
- Device IDs: [101, 103, 104, 101]

---

## Step 3: Pattern Display in UI

### Files to Modify
- Session monitor template
- JavaScript for pattern animation

### What to Add
1. **Pattern Display Area**: Show the sequence visually
2. **Animation**: Flash each color in sequence
3. **Timing**: Based on difficulty level
   - Level 1: 2 seconds per color
   - Level 3: 1 second per color
   - Level 5: 0.5 seconds per color

### UI Mockup
```
┌─────────────────────────────────────────┐
│ Memorize This Pattern:                  │
│                                          │
│  🔴 RED  ▶  🟡 YELLOW  ▶  🔵 BLUE  ▶  🔴 RED │
│                                          │
│  [Pattern will display in 3 seconds...] │
└─────────────────────────────────────────┘

After display:
┌─────────────────────────────────────────┐
│ Now Execute The Pattern!                │
│                                          │
│  Touch: RED → YELLOW → BLUE → RED       │
│  Return to home base after each touch   │
└─────────────────────────────────────────┘
```

### Expected Result
- Pattern displays visually before athlete starts
- Athlete has time to memorize
- Clear instructions shown

---

## Step 4: Touch Sequence Tracking

### Files to Modify
- Session monitoring backend
- Touch event handlers

### What to Implement
```python
class SimonSaysSession:
    def __init__(self, pattern):
        self.expected_pattern = pattern  # ['red', 'yellow', 'blue', 'red']
        self.current_step = 0
        self.touch_sequence = []
        self.at_home_base = True
        self.errors = []

    def process_touch(self, device_id, device_color):
        # Check if at home base when required
        if not self.at_home_base and device_id == 'home_base':
            self.at_home_base = True
            return {'status': 'returned_home', 'next_required': self.expected_pattern[self.current_step]}

        # Check if should be at home base
        if device_id != 'home_base' and not self.at_home_base:
            self.errors.append({'step': self.current_step, 'error': 'Did not return to home base'})
            return {'status': 'error', 'message': 'Return to home base first!'}

        # Check if correct device
        expected_color = self.expected_pattern[self.current_step]
        if device_color == expected_color:
            self.touch_sequence.append(device_color)
            self.current_step += 1
            self.at_home_base = False

            if self.current_step >= len(self.expected_pattern):
                return {'status': 'completed', 'score': calculate_score()}
            else:
                return {'status': 'correct', 'next': self.expected_pattern[self.current_step]}
        else:
            self.errors.append({'step': self.current_step, 'expected': expected_color, 'actual': device_color})
            return {'status': 'error', 'message': f'Wrong! Expected {expected_color}, got {device_color}'}
```

### Expected Result
- System tracks each touch
- Validates against expected pattern
- Detects errors immediately
- Requires return to home base between touches

---

## Step 5: Visual Feedback

### UI Updates Needed
1. **Current Step Indicator**
   ```
   Pattern: 🔴 RED ▶ 🟡 YELLOW ▶ 🔵 BLUE ▶ 🔴 RED
   Progress: ✅     ⏺ (current)
   ```

2. **Device Highlighting**
   - Next required device: Pulsing glow
   - Correct touch: Green flash
   - Wrong touch: Red flash
   - Home base: Dim when not at home

3. **Error Display**
   ```
   ❌ Wrong cone! Expected YELLOW, touched BLUE
   ```

4. **Success Display**
   ```
   ✅ Pattern Complete! Time: 12.5s
   ```

### Expected Result
- Athlete knows which cone to touch next
- Immediate feedback on correct/wrong
- Clear success/failure indication

---

## Step 6: Scoring & Results

### Metrics to Track
- **Time**: Total time to complete pattern
- **Errors**: Number of wrong touches
- **Accuracy**: Correct touches / total touches
- **Speed**: Average time per touch
- **Perfect Run**: Zero errors bonus

### Results Display
```
┌──────────────────────────────────┐
│ Pattern Completed!               │
│                                   │
│ Time:     12.5 seconds           │
│ Pattern:  RED→YELLOW→BLUE→RED    │
│ Errors:   0 (Perfect!)           │
│ Score:    100 points             │
└──────────────────────────────────┘
```

---

## Implementation Priority

### Phase 1 (MVP - Minimal Viable Product)
1. ✅ Step 1: Color display on devices
2. ✅ Step 2: Pattern generation
3. ✅ Step 3: Pattern display to athlete
4. ✅ Step 4: Touch tracking

### Phase 2 (Enhanced)
5. ⏸ Step 5: Visual feedback
6. ⏸ Step 6: Scoring system

### Phase 3 (Advanced)
7. ⏸ Difficulty scaling (speed/length)
8. ⏸ Leaderboards
9. ⏸ Pattern replay
10. ⏸ Multi-athlete patterns

---

## Technical Decisions Needed

### Question 1: Where to Store Active Pattern?
**Options**:
- A) Session state in memory (REGISTRY)
- B) Database (athlete_patterns table)
- C) Redis/cache
- D) JavaScript localStorage (client-side)

**Recommendation**: B) Database - already have `athlete_patterns` table created in Phase 2

### Question 2: Pattern Display Timing
**Options**:
- A) Show full pattern at once (static)
- B) Animate one color at a time
- C) Both: animate first, then show static

**Recommendation**: C) Animate then static - helps memorization

### Question 3: Home Base Requirement
**Options**:
- A) Strict: Must return after every touch
- B) Relaxed: Only return when ready for next
- C) Optional: Configurable per course

**Recommendation**: A) Strict - true to Simon Says game

---

## Files to Create/Modify

### New Files
- `/opt/field_trainer/pattern_generator.py` - Pattern generation logic
- `/opt/field_trainer/pattern_validator.py` - Touch sequence validation
- `/opt/SIMON_SAYS_IMPLEMENTATION.md` - This detailed plan

### Modified Files
- `/opt/coach_interface.py` - Session start endpoint
- `/opt/field_trainer/templates/session_monitor.html` - Color display
- `/opt/field_trainer/ft_registry.py` - Pattern tracking state
- `/opt/field_trainer/db_manager.py` - Pattern storage methods (already added in Phase 2!)

---

## Next Steps

**Immediate Action**: Start with Step 1 - Add color display to session monitor

**Your Decision Needed**:
1. Should we proceed with Step 1 now?
2. Do you want to review/modify this plan first?
3. Any specific behavior preferences (strict vs relaxed rules)?

**Development Approach**:
- Build incrementally (one step at a time)
- Test each step before moving to next
- Use existing Simon Says course as test case

---

## Success Criteria

✅ **Step 1 Complete When**:
- Device boxes show colored backgrounds/borders
- Colors match Custom Rules configuration
- Home base shows as neutral/gray

✅ **Full Feature Complete When**:
- Random pattern generates on "Go"
- Pattern displays visually to athlete
- System tracks touches correctly
- Validates pattern matches expected
- Shows results with time/accuracy
- Stores pattern in database

---

**Ready to start Step 1?**
