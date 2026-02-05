# Built-in Courses System - Simon Says & More

**Last Updated:** January 24, 2026
**Status:** ✅ Production Ready

---

## 📋 Overview

The Field Trainer system includes **5 built-in courses** that are automatically created when the system starts. These courses are embedded in code and will work out-of-the-box after a git pull and fresh database creation.

### Built-in Courses

1. **Warm-up: Round 1** - High knees, walking lunge, backpedal, high skips, butt kicks, jog (135 yards)
2. **Warm-up: Round 2** - Walking lunge, internal hip, external hip, carioca right/left, jog (135 yards)
3. **Warm-up: Round 3** - Backpedal, side shuffle left/right, bounds, jog (135 yards)
4. **Simon Says - 4 Colors** - Pattern memory drill with LED sequences (40 yards)
5. **Beep Test** - Multi-stage fitness test (Léger Protocol) for aerobic capacity (40 yards)

---

## 🎯 Simon Says - Complete Feature Set

### What is Simon Says?

Simon Says is a **pattern mode drill** where athletes must memorize and repeat a sequence of colored cone touches:

1. LED lights show a random pattern (e.g., RED → BLUE → YELLOW → GREEN)
2. Athlete memorizes the sequence
3. Athlete touches cones in the correct order
4. Athlete touches **Start cone (D0)** to submit pattern
5. Success = all boxes turn green, failure = boxes turn red with error indicator

### Multi-Athlete Sessions

Simon Says supports **multiple athletes** with these features:

- **Pre-session pattern preview**: Pattern boxes visible BEFORE clicking GO button
- **Unique patterns per athlete**: Each athlete gets a different random pattern (no consecutive duplicates)
- **Rapid touch support**: No global debounce blocking - athletes can touch cones as fast as they can move
- **Coach-controlled pacing**: Modal dialog appears after each athlete (success or failure)
  - Button shows next athlete's name: "Continue to [Name]"
  - Gives athletes time to clear the field
  - Coach must click to advance to next athlete
- **Proper status tracking**: Athletes stay 'queued' until their turn, only active athlete is 'running'

### Pattern Configuration

Default pattern settings (configurable in session setup):
- **Pattern Length**: 4 touches (range: 3-8)
- **Allow Repeats**: Yes (same color can appear multiple times, but not consecutively)
- **Error Feedback Duration**: 4 seconds (how long red boxes stay visible)
- **Debounce**: 1000ms per-device (prevents hardware double-bounces)

### Interactive Diagram

Simon Says includes an **interactive SVG diagram** (5,880 characters) stored in the database:
- Draggable cones for custom layouts
- Editable arrow directions
- Grid background (50x50 yards)
- Layout instructions: "Arrange 4 colored cones in a line or square pattern..."

---

## 🔧 Technical Implementation

### Core Components

#### 1. **Pattern Generator** (`/opt/field_trainer/pattern_generator.py`)
- ✅ Committed to git repository
- Generates random sequences avoiding consecutive duplicates
- Ensures pattern variety (different from previous pattern)
- Returns device list with colors for chase animations

```python
from field_trainer.pattern_generator import pattern_generator

pattern = pattern_generator.generate_simon_says_pattern(
    colored_devices=[
        {'device_id': '192.168.99.101', 'device_name': 'Red', 'color': 'red'},
        {'device_id': '192.168.99.102', 'device_name': 'Green', 'color': 'green'},
        # ...
    ],
    sequence_length=4,
    allow_repeats=True
)
# Returns: [{'device_id': '...', 'color': 'red'}, ...]
```

#### 2. **Restore Built-in Courses** (`/opt/restore_builtin_courses.py`)
- ✅ Committed to git repository
- ✅ Runs automatically on app startup
- ✅ Checks for existing courses (skips duplicates)
- ✅ Includes interactive SVG diagram for Simon Says
- Creates all 5 built-in courses with `is_builtin = 1` flag

**Automatic Execution:**
The restore script is called in `/opt/field_trainer_main.py` during startup:

```python
# Line 115-139 in field_trainer_main.py
REGISTRY.log("Checking built-in courses...")
try:
    import subprocess
    result = subprocess.run(
        [sys.executable, '/opt/restore_builtin_courses.py'],
        capture_output=True,
        text=True,
        timeout=30
    )
    if result.returncode == 0:
        created = result.stdout.count('Creating...')
        skipped = result.stdout.count('Already exists')
        if created > 0:
            REGISTRY.log(f"Built-in courses: created {created}, already existed {skipped}")
        else:
            REGISTRY.log(f"Built-in courses: all {skipped} already exist")
except Exception as e:
    REGISTRY.log(f"Built-in course restore error: {e}", level="warning")
```

#### 3. **Session Service** (`/opt/services/session_service.py`)

**Key Changes:**

**Pattern Pre-generation (Lines 255-310)**
- Patterns generated during **deployment phase** (not session start)
- Stored in `session_service.pre_generated_patterns[session_id]`
- Pattern boxes visible on monitor page before GO button

**Global Debounce Disabled (Lines 811-824, 1000-1005)**
```python
# DISABLED for pattern mode - athletes need rapid touches
if course_mode != 'pattern':
    global_debounce_key = f"{run_id}_last_touch_time"
    global_debounce_window = 0.5  # 500ms
    # ... check and reject ...
```

**Pause Logic (Lines 767-796, 978-1010)**
- After athlete completes/fails, session PAUSES
- Coach must click "Continue to Next Athlete"
- Only first athlete started in database, others stay 'queued'

**Next Athlete Progression (Lines 500-510)**
```python
def _move_to_next_athlete(self):
    # Find next athlete in queue
    # Start their run in database (changes status from 'queued' to 'running')
    self.db.start_run(next_run_id, run_start_time)
    # Display their pattern
```

#### 4. **Session Routes** (`/opt/routes/sessions_bp.py`)

**Deploy Course (Lines 498-620)**
- Generates patterns for all athletes during deployment
- Creates segments immediately (boxes appear in UI)
- Stores in `session_service.pre_generated_patterns`

**Session Status API (Lines 183-217)**
- Returns pre-generated patterns even in 'setup' status
- Allows UI to show pattern boxes before GO button

**Next Athlete Endpoint (Lines 253-273)**
```python
@sessions_bp.route('/<session_id>/next-athlete', methods=['POST'])
def next_athlete(session_id):
    """Continue to Next Athlete button"""
    has_next_athlete = session_service._move_to_next_athlete()
    if has_next_athlete:
        return jsonify({'success': True, 'message': 'Advanced to next athlete'})
    else:
        session_service._complete_session(session_id)
        return jsonify({'success': True, 'message': 'Session completed'})
```

#### 5. **Session Monitor UI** (`/opt/field_trainer/templates/session_monitor.html`)

**Modal Dialog (Lines 131-153)**
```html
<div class="modal fade" id="nextAthleteModal" data-bs-backdrop="static">
    <div class="modal-content">
        <div class="modal-header">
            <h5 id="modalTitle">Athlete Finished</h5>
        </div>
        <div class="modal-body">
            <p><strong id="athleteName"></strong> has finished.</p>
        </div>
        <div class="modal-footer">
            <button id="continueNextAthleteBtn">
                Continue to Next Athlete
            </button>
        </div>
    </div>
</div>
```

**Pause Detection (Lines 319-347)**
```javascript
// Detect pause state: queued > 0 AND running = 0 AND finished > 0
if (queuedAthletes.length > 0 &&
    runningAthletes.length === 0 &&
    finishedAthletes.length > 0) {

    const lastFinished = finishedAthletes[finishedAthletes.length - 1];
    const nextAthlete = queuedAthletes[0];

    showNextAthleteModal(
        lastFinished.athlete_name,
        lastFinished.status,
        nextAthlete.athlete_name
    );
}
```

**Button with Next Athlete Name (Lines 533-555)**
```javascript
function showNextAthleteModal(athleteName, status, nextAthleteName) {
    const btn = document.getElementById('continueNextAthleteBtn');
    btn.innerHTML = `<i class="fas fa-arrow-right"></i> Continue to ${nextAthleteName}`;

    // Update title based on success/failure
    if (status === 'completed') {
        modalTitle.innerHTML = '<i class="fas fa-check-circle"></i> Athlete Succeeded';
    } else if (status === 'incomplete') {
        modalTitle.innerHTML = '<i class="fas fa-times-circle"></i> Athlete Failed';
    }
}
```

**Immediate Modal Close (Lines 557-580)**
```javascript
async function continueToNextAthlete() {
    // IMMEDIATELY hide modal (don't wait for API)
    const modal = bootstrap.Modal.getInstance(document.getElementById('nextAthleteModal'));
    modal.hide();
    modalShown = false;
    waitingForCoach = false;

    // Make API call in background
    await fetch(`/session/${sessionId}/next-athlete`, {method: 'POST'});
    refreshStatus();
}
```

---

## 🐛 Bugs Fixed (January 24, 2026)

### 1. Pattern Boxes Not Visible Before GO Button
- **Problem**: Patterns only appeared after clicking GO
- **Fix**: Move pattern generation to deployment phase, store in `pre_generated_patterns`
- **Files**: `routes/sessions_bp.py`, `services/session_service.py`

### 2. Global Debounce Blocking Rapid Touches
- **Problem**: 500ms global debounce rejected touches < 500ms apart
- **Fix**: Disable global debounce for pattern mode only
- **Files**: `services/session_service.py` lines 811-824, 1000-1005

### 3. Modal Not Appearing After Athlete Finished
- **Problem**: All athletes showing as 'running' instead of 'queued'
- **Fix**: Only start first athlete in database, others stay 'queued'
- **Files**: `services/session_service.py` lines 229-236

### 4. Pattern Not Playing for Next Athlete
- **Problem**: Athlete marked inactive during pause, couldn't transition
- **Fix**: Keep athlete as `is_active=True` during pause
- **Files**: `services/session_service.py` lines 767-796

### 5. Modal Stayed Open During Pattern Display
- **Problem**: Modal close waited for API response
- **Fix**: Close modal immediately on button click, API call in background
- **Files**: `field_trainer/templates/session_monitor.html` lines 557-580

---

## 🚀 Deployment Instructions

### Fresh System Setup

1. **Clone repository:**
   ```bash
   git clone <repo-url>
   cd <repo-directory>
   ```

2. **Database will be created automatically:**
   - Database schema created on first run
   - Built-in courses restored automatically
   - No manual intervention needed

3. **Start the system:**
   ```bash
   python3 field_trainer_main.py
   ```

4. **Verify built-in courses:**
   - Navigate to web UI: `http://localhost:5001`
   - Click "Courses" in navigation
   - You should see all 5 built-in courses marked with `is_builtin = 1`

### Existing System Update

If you're updating an existing system:

1. **Pull latest code:**
   ```bash
   git pull origin main
   ```

2. **Restart the system:**
   ```bash
   # System will automatically check for missing built-in courses
   python3 field_trainer_main.py
   ```

3. **Manual course restoration (if needed):**
   ```bash
   # Only needed if automatic restore fails
   python3 restore_builtin_courses.py
   ```

### Verifying Simon Says is Built-in

```bash
python3 << 'EOF'
import sqlite3
conn = sqlite3.connect('/opt/data/field_trainer.db')
cursor = conn.cursor()
cursor.execute("SELECT course_name, is_builtin FROM courses WHERE course_name = 'Simon Says - 4 Colors'")
result = cursor.fetchone()
print(f"Course: {result[0]}")
print(f"Built-in: {'YES ✅' if result[1] == 1 else 'NO ❌'}")
conn.close()
EOF
```

Expected output:
```
Course: Simon Says - 4 Colors
Built-in: YES ✅
```

---

## 📊 Database Schema

### Courses Table (relevant columns)

```sql
CREATE TABLE courses (
    course_id INTEGER PRIMARY KEY AUTOINCREMENT,
    course_name TEXT NOT NULL,
    description TEXT,
    mode TEXT,  -- 'sequential' or 'pattern'
    category TEXT,
    diagram_svg TEXT,  -- Interactive SVG diagram
    layout_instructions TEXT,
    is_builtin INTEGER DEFAULT 0,  -- 1 for built-in courses
    -- ... other columns ...
);
```

### Built-in Course Flag

- `is_builtin = 1`: Course is managed by code, will be restored on fresh installs
- `is_builtin = 0`: User-created course, not automatically restored

The restore script **only creates courses that don't already exist** with `is_builtin = 1`, preventing duplicates.

---

## 🧪 Testing Simon Says

### Manual Test Procedure

1. **Create a session:**
   - Course: Simon Says - 4 Colors
   - Mode: Pattern
   - Add 3-5 athletes

2. **Deploy course:**
   - Click "Deploy Course"
   - Verify cones turn to assigned colors (Red, Green, Blue, Yellow)
   - **VERIFY**: Pattern boxes appear on monitor page BEFORE clicking GO

3. **Start session:**
   - Click "GO" button
   - First athlete's pattern displays (LED chase animation)
   - Pattern boxes show sequence (e.g., RED → BLUE → YELLOW)

4. **Test rapid touches:**
   - Touch cones quickly in sequence (< 500ms between touches)
   - **VERIFY**: All touches register (no "GLOBAL DEBOUNCE" errors in log)

5. **Complete pattern:**
   - Touch all cones in correct order
   - Touch Start cone (D0) to submit
   - **VERIFY**: Modal appears: "Athlete Succeeded" with "Continue to [Next Name]"

6. **Test wrong pattern:**
   - Touch cones in wrong order
   - Touch Start cone (D0)
   - **VERIFY**: Modal appears: "Athlete Failed" with "Continue to [Next Name]"

7. **Continue to next athlete:**
   - Click "Continue to [Name]" button
   - **VERIFY**: Modal closes immediately
   - **VERIFY**: Next athlete's pattern displays
   - **VERIFY**: Pattern boxes update with new sequence

8. **Complete all athletes:**
   - Repeat for all athletes
   - **VERIFY**: Session completes after last athlete

### Expected Log Output

```
🎨 Simon Says detected - setting assigned colors NOW...
   Color setting response: 200
   ✅ Assigned colors set successfully

🎲 Generating patterns for all athletes...
✓ Using pre-generated pattern for Alice: RED → BLUE → YELLOW → GREEN
✓ Using pre-generated pattern for Bob: GREEN → RED → BLUE → YELLOW
✓ Using pre-generated pattern for Charlie: YELLOW → GREEN → RED → BLUE
   ✓ Segments already exist for Alice (created during deployment)

✅ Alice succeeded - waiting for coach
   ⏸️  PAUSED - Waiting for coach to click 'Continue to Next Athlete'

👥 NEXT ATHLETE BUTTON CLICKED
   ✅ Advanced to next athlete
✓ Next athlete: Bob (run started in database)
```

### Troubleshooting

**Issue:** Pattern boxes don't appear before GO button
**Fix:** Check that patterns were generated during deployment in `session_service.pre_generated_patterns`

**Issue:** Touches rejected with "GLOBAL DEBOUNCE" error
**Fix:** Verify `course_mode == 'pattern'` and global debounce is disabled (line 811 in session_service.py)

**Issue:** Modal doesn't appear after athlete finishes
**Fix:** Check athlete status counts in browser console: `queued > 0, running = 0, finished > 0`

**Issue:** Next athlete's pattern doesn't play
**Fix:** Verify `_move_to_next_athlete()` is calling `db.start_run()` for next athlete

---

## 📝 Files Modified

### Production Code (Committed)

- `/opt/field_trainer/pattern_generator.py` - Pattern generation logic ✅ IN GIT
- `/opt/routes/sessions_bp.py` - Deploy course, session status, next-athlete endpoint
- `/opt/services/session_service.py` - Pattern pre-gen, debounce, pause logic, athlete progression
- `/opt/field_trainer/templates/session_monitor.html` - Modal UI, pause detection, button text
- `/opt/field_trainer_main.py` - Auto-restore built-in courses on startup
- `/opt/restore_builtin_courses.py` - Built-in course definitions with SVG ✅ ADDED TO GIT

### Documentation

- `/opt/BUILTIN_COURSES_README.md` - This file (comprehensive documentation)
- `/tmp/SIMON_SAYS_FIXES_SUMMARY.md` - Detailed fix summary with before/after code
- `/tmp/simon_says_timing.txt` - Complete changelog with timing analysis

### Database Backups

- `/opt/data/field_trainer.db.backup_20260124_113518` - Backup before fixes (676K)

---

## 🔐 Production Readiness Checklist

- ✅ Pattern generator code committed to git
- ✅ Restore script committed to git
- ✅ Restore script runs automatically on startup
- ✅ Duplicate-check prevents course duplication
- ✅ Interactive SVG diagram included in restore script
- ✅ Simon Says course marked as `is_builtin = 1`
- ✅ All multi-athlete features tested and working
- ✅ Pattern boxes visible before GO button
- ✅ Global debounce disabled for pattern mode
- ✅ Pause dialog with next athlete name
- ✅ Proper athlete status tracking (queued/running/completed)
- ✅ Modal closes immediately on continue
- ✅ Comprehensive documentation created

---

## 💡 Future Enhancements

### Potential Improvements

1. **Pattern Difficulty Levels:**
   - Easy: 3 colors, 3 length, no repeats
   - Medium: 4 colors, 4 length, repeats allowed (current default)
   - Hard: 4 colors, 6-8 length, repeats allowed

2. **Leaderboard:**
   - Track fastest completion times per athlete
   - Success rate percentage
   - Difficulty-adjusted scoring

3. **Custom Color Sets:**
   - Allow coaches to create custom Simon Says courses
   - 5-8 colored cones for advanced athletes
   - Different cone layouts (line, square, circle)

4. **Progressive Difficulty:**
   - Start with 3-length pattern
   - Increase length after each success
   - Stop when athlete fails or reaches max length

5. **Audio Feedback:**
   - "Correct!" for successful pattern completion
   - "Try again!" for failures
   - Color names during pattern display: "Red... Blue... Yellow"

---

## 📞 Support

For issues or questions about Simon Says or built-in courses:

1. Check system logs: `/var/log/field_trainer.log`
2. Run restore script manually: `python3 /opt/restore_builtin_courses.py`
3. Verify database: Query `courses` table for `is_builtin = 1` entries
4. Review this documentation for troubleshooting steps

---

**Document Version:** 1.0
**Last Review:** January 24, 2026
**Status:** ✅ Production Ready - Ready for Git Push
