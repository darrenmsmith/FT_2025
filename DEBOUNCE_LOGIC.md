# Simon Says Debounce Logic

## Problem
Hardware touch sensors can "bounce" - registering a single physical touch multiple times in quick succession. Without debounce, this causes false failures when athletes touch correctly but hardware double-registers.

## Solution: Smart Debounce

### How It Works
1. **Track Last Touch Time**: For each athlete's run, track `{device_id: timestamp}` of last touch
2. **Debounce Window**: Configurable threshold (default 1000ms / 1 second)
3. **Rapid Repeat Detection**: When a touch comes in:
   - Check if SAME device was touched within debounce window
   - If yes → ignore (it's a hardware bounce)
   - If no → proceed with validation

### Key Features

**✅ Prevents False Failures**
- Athlete touches D2 once
- Hardware registers D2 twice (50ms apart)
- First D2: validates as correct
- Second D2: ignored (within 1000ms debounce window)
- Result: Success!

**✅ Still Catches Real Mistakes**
- Pattern: D1 → D2 → D3 → D4
- Athlete touches: D1, D2, D2 (intentional)
- First D2: correct (position 1)
- Second D2: FAILS (expected D3, got D2)
- Debounce doesn't apply because validation happens before we update timestamp

**✅ Supports Pattern Repeats**
- Pattern: D1 → D2 → D3 → D1 (D1 appears twice)
- Athlete touches D1, waits, touches D2, touches D3, touches D1 again
- All touches succeed because they match expected sequence
- Debounce only filters rapid (<1000ms) repeats, not legitimate pattern repeats

## Configuration

```json
{
  "pattern_length": 4,        // 3-8 supported
  "allow_repeats": true,      // Allow same device in pattern (non-consecutive)
  "error_feedback_duration": 4.0,  // Seconds
  "debounce_ms": 1000        // Milliseconds (default 1000ms / 1 second)
}
```

## Pattern Length Scaling

- **Minimum**: 3 devices
- **Maximum**: 8 devices
- **Default**: 4 devices
- Automatically validated and clamped to 3-8 range
- Pattern generator supports all lengths in this range

## Example Scenarios

### Scenario 1: Hardware Bounce (Prevented)
```
Pattern: RED → YELLOW → BLUE → GREEN
Athlete touches: RED (registers at t=0ms)
Hardware bounces: RED (registers at t=50ms)
Result:
  - t=0ms: ✅ RED correct (position 0)
  - t=50ms: 🔇 Debounce - ignored
  - Athlete continues with YELLOW
```

### Scenario 2: Intentional Wrong Touch (Caught)
```
Pattern: RED → YELLOW → BLUE → GREEN
Athlete touches: RED, YELLOW, YELLOW (intentional mistake)
Result:
  - RED: ✅ Correct (position 0)
  - YELLOW: ✅ Correct (position 1)
  - YELLOW: ❌ WRONG (expected BLUE) → FAILS
```

### Scenario 3: Pattern with Repeating Device
```
Pattern: RED → YELLOW → BLUE → RED
Athlete touches: RED (t=0), YELLOW (t=1.5s), BLUE (t=3s), RED (t=4.5s)
Result:
  - RED @ t=0: ✅ Correct (position 0)
  - YELLOW @ t=1.5s: ✅ Correct (position 1)
  - BLUE @ t=3s: ✅ Correct (position 2)
  - RED @ t=4.5s: ✅ Correct (position 3)
  - No debounce applied (touches are >1000ms apart)
```

### Scenario 4: Rapid Intentional Touch During Pattern
```
Pattern: RED → YELLOW → BLUE → GREEN
Athlete rapidly touches: RED, RED (t=300ms apart, both intentional)
Result:
  - First RED: ✅ Correct (position 0)
  - Second RED: 🔇 Debounced (within 1000ms window)
  - Athlete continues with YELLOW
```

## Implementation Details

**Location**: `/opt/services/session_service.py`

**Lines 671-690**: Debounce check (before validation)
- Tracks per-athlete touch timestamps
- Filters rapid repeats on same device
- Returns early if bounce detected

**Lines 821-829**: Timestamp update (after validation)
- Only updates timestamp AFTER successful validation
- Ensures failed touches don't update debounce tracking
- Allows detection of intentional wrong repeats

**Lines 118-122**: Pattern length validation
- Clamps to 3-8 range
- Prevents invalid configurations
