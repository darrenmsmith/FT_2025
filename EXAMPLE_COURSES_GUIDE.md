# Advanced Course Examples - Coach's Guide

**Date**: November 21, 2025
**Status**: ✅ 5 Example Courses Created
**View at**: `http://192.168.7.116:5001/courses`

---

## Overview

Five example courses have been created to demonstrate the advanced field capabilities. Each course showcases different advanced features and real-world coaching scenarios.

---

## Example Course #1: Yo-Yo IR Test Level 1

### Description
Progressive shuttle run with active recovery periods - simulates the famous Yo-Yo Intermittent Recovery Test used by professional soccer teams worldwide.

### Advanced Features Used
- **Device Function**: `start_finish` and `turnaround`
- **Detection Method**: `touch` on all devices
- **Device Groups**: `start_line` and `turnaround_point`
- **Custom Rules**: Recovery period timing constraints

### Course Layout
```
Start/Finish Line                      Turnaround Point
(Device 0)                             (Device 1)
     ●────────────────20 yards────────────►●
     ◄────────────────20 yards───────────────
                     (Recovery jog)
```

### How It Works
1. **Start**: Touch Device 0 → Sprint to turnaround
2. **Turnaround**: Touch Device 1 → Sprint back immediately
3. **Recovery**: Touch Device 0 → Jog for 8-12 seconds (enforced by Custom Rules)
4. Repeat with decreasing rest periods

### Custom Rules Explained
```
min_time: 8.0, max_time: 12.0, recovery_period: true
```
- Athlete must take 8-12 seconds for recovery jog
- System enforces minimum rest time
- Flag marks this as active recovery, not max effort

### Coaching Application
- Test aerobic capacity and recovery
- Progressive difficulty (shorten recovery in later stages)
- Track improvements over season

---

## Example Course #2: 5-10-5 Pro Agility Test

### Description
NFL Combine standard agility test - the classic "Pro Agility" drill used to evaluate lateral quickness and change-of-direction speed.

### Advanced Features Used
- **Device Function**: `start_finish` at center, `turnaround` at sides
- **Detection Method**: `touch` required at all cones
- **Device Groups**: `center_line`, `right_cone`, `left_cone`
- **Custom Rules**: Split timing enabled at each checkpoint

### Course Layout
```
     Left Cone         Center Line        Right Cone
     (Device 2)        (Device 0)         (Device 1)
         ●──────5 yards──────●──────5 yards──────●

Path: Start at center → Right 5 yards → Left 10 yards → Right 5 yards (finish)
```

### How It Works
1. **Start**: Touch Device 0 in 3-point stance
2. **First Turn**: Sprint right 5 yards, touch Device 1 with hand
3. **Second Turn**: Change direction, sprint left 10 yards, touch Device 2
4. **Finish**: Change direction, sprint right 5 yards through Device 0

### Custom Rules Explained
```
timer: true, split_timing: true, scoring: true
```
- Records split times at each checkpoint
- Final time used for scoring/comparison
- Tracks change-of-direction efficiency

### Coaching Application
- NFL Combine standard test (compare to pro benchmarks)
- Evaluate lateral quickness
- Identify left/right imbalances
- Track improvement in COD (change of direction) speed

---

## Example Course #3: Simon Says Reaction Drill

### Description
Random pattern reaction training where devices light up in a sequence and the athlete must touch them in the correct order - trains cognitive processing under pressure.

### Advanced Features Used
- **Device Function**: `start_finish` at home, `waypoint` at targets
- **Detection Method**: `touch` required
- **Device Groups**: `home_base` and `pattern_group`
- **Custom Rules**: Pattern-based gameplay with difficulty scaling

### Course Layout
```
         Device 2
             ●

Device 1 ●      ● Device 3

         Home Base
         (Device 0)
             ●

        Device 4
             ●
```

### How It Works
1. **Pattern Display**: System shows sequence (e.g., Device 2 → 4 → 1 → 3)
2. **Memorize**: Athlete has 3 seconds to memorize
3. **Execute**: Touch devices in exact order, returning to home base after each
4. **Score**: Speed + accuracy combined score

### Custom Rules Explained
```
pattern_type: simon_says, difficulty: 3, sequence_length: 4, pattern_member: true
```
- `pattern_type: simon_says` - Random sequence generation
- `difficulty: 3` - Medium difficulty (speed of display)
- `sequence_length: 4` - Number of devices in pattern
- `pattern_member: true` - This device is part of the pattern pool

### Coaching Application
- Cognitive training under physical stress
- Reaction speed development
- Memory and focus under pressure
- Adjustable difficulty for different skill levels

---

## Example Course #4: Box Drill - Timed Zones

### Description
4-corner box drill with minimum time requirements per zone - teaches athletes to maintain technique throughout the drill rather than rushing.

### Advanced Features Used
- **Device Function**: `start_finish` and `waypoint` at corners
- **Detection Method**: `touch` required
- **Device Groups**: `corner_1` through `corner_4`
- **Custom Rules**: Zone-based timing with min/max constraints

### Course Layout
```
Corner 1              Corner 2
(Device 0) ●─────10 yards─────● (Device 1)
    │                             │
10 yards  Side shuffle right  10 yards
    │                             │
    │         Backpedal            │
    │                             │
(Device 3) ●─────10 yards─────● (Device 2)
Corner 4              Corner 3
```

### Movement Pattern
1. **Zone 1→2**: Side shuffle right (min 2 seconds, max 5 seconds)
2. **Zone 2→3**: Backpedal (min 2.5 seconds, max 6 seconds)
3. **Zone 3→4**: Side shuffle left (min 2 seconds, max 5 seconds)
4. **Zone 4→1**: Sprint (min 1 second, max 3 seconds)

### Custom Rules Explained
```
zone: 2, min_time: 2.0, max_time: 5.0
```
- `zone: 2` - Identifies which zone this checkpoint represents
- `min_time: 2.0` - Athlete MUST take at least 2 seconds (enforces technique)
- `max_time: 5.0` - Athlete must complete within 5 seconds (prevents loafing)

### Coaching Application
- Teaches controlled movement patterns
- Prevents athletes from cutting corners
- Enforces proper technique (can't rush through)
- Builds neuromuscular control

---

## Example Course #5: Proximity Detection Sprint

### Description
Sprint drill using proximity sensors instead of touch - allows athletes to run at full speed through gates without slowing down to touch cones.

### Advanced Features Used
- **Device Function**: `start_finish` at start, `waypoint` at gates
- **Detection Method**: `touch` at start, `proximity` at speed gates
- **Device Groups**: `start_gate`, `speed_gate_1`, `speed_gate_2`, `finish_gate`
- **Custom Rules**: Proximity thresholds and split timing

### Course Layout
```
Touch Start        Gate 1         Gate 2       Proximity Finish
(Device 0)       (Device 1)     (Device 2)     (Device 3)
     ●─────10y─────●─────20y─────●─────40y─────●
   (touch)     (proximity)   (proximity)    (proximity)
```

### How It Works
1. **Start**: Touch Device 0 to begin timing
2. **Gate 1**: Sprint past Device 1 (within 1.5 yards triggers sensor)
3. **Gate 2**: Sprint past Device 2 (within 1.5 yards)
4. **Finish**: Sprint through Device 3 (within 1.5 yards)
5. Split times recorded at each gate

### Custom Rules Explained
```
proximity_threshold: 1.5, split_timing: true, scoring: true
```
- `proximity_threshold: 1.5` - Sensor triggers within 1.5 yards
- `split_timing: true` - Records 10m, 30m, 70m splits
- `scoring: true` - Enables leaderboard/comparison

### Coaching Application
- Pure speed testing (no deceleration for touch)
- Measure acceleration phases (0-10y, 10-30y, 30-70y)
- Flying sprint training
- Compare to 40-yard dash benchmarks

---

## Comparison Table

| Course | Primary Goal | Advanced Features | Difficulty | Equipment |
|--------|-------------|-------------------|------------|-----------|
| Yo-Yo IR Test | Aerobic Capacity | Recovery timing, turnarounds | Medium | 2 devices |
| 5-10-5 Pro Agility | COD Speed | Split timing, scoring | Easy | 3 devices |
| Simon Says | Reaction/Cognitive | Patterns, sequence tracking | Hard | 5 devices |
| Box Drill | Technique Control | Zone timing, min/max times | Medium | 4 devices |
| Proximity Sprint | Max Speed | Proximity detection, splits | Easy | 4 devices |

---

## How to Use These Examples

### Option 1: Run As-Is
1. Go to `http://192.168.7.116:5001/courses`
2. Find the example course
3. Click "Deploy" or "Start Run"
4. Follow the instructions

### Option 2: Duplicate and Modify
1. Go to course list
2. Click "Duplicate" on example course
3. Edit distances, timing, or rules
4. Save as new course with your name

### Option 3: Learn and Create New
1. Study the advanced fields in each example
2. Create new course from scratch
3. Use similar patterns for your drills
4. Experiment with different combinations

---

## Advanced Field Quick Reference

### Device Function Options
- `start_finish` - Starting point or finish line
- `waypoint` - Checkpoint along the route
- `turnaround` - Point where athlete changes direction
- `boundary` - Edge or limit of drill area
- `timer` - Time-only checkpoint (no physical gate)

### Detection Method Options
- `touch` - Requires physical contact with sensor (default)
- `proximity` - Triggers when athlete gets within range
- `none` - Time-based only, no detection required

### Device Group Examples
- `start_line`, `finish_line` - Clear role identification
- `cone_group_1`, `pattern_group` - Logical grouping
- `speed_gate_1`, `recovery_zone` - Functional naming

### Custom Rules Examples
```
min_time: 2.5, max_time: 10.0              ← Timing constraints
timer: true, split_timing: true            ← Recording modes
scoring: true, leaderboard: true           ← Competition features
proximity_threshold: 1.5                   ← Sensor settings
pattern_type: simon_says, difficulty: 3    ← Pattern configuration
zone: 2, recovery_period: true             ← Zone identification
```

---

## Common Custom Rules

| Rule | Purpose | Example Values |
|------|---------|----------------|
| `min_time` | Minimum time required (seconds) | `2.0`, `5.5`, `10.0` |
| `max_time` | Maximum time allowed (seconds) | `8.0`, `15.0`, `30.0` |
| `timer` | Enable/disable timing | `true`, `false` |
| `split_timing` | Record intermediate times | `true`, `false` |
| `scoring` | Enable scoring system | `true`, `false` |
| `proximity_threshold` | Trigger distance (yards) | `1.0`, `1.5`, `2.0` |
| `pattern_type` | Type of pattern drill | `simon_says`, `random`, `custom` |
| `difficulty` | Difficulty level | `1-5` |
| `zone` | Zone identifier | `1`, `2`, `3`, etc. |
| `recovery_period` | Mark as recovery zone | `true`, `false` |

---

## Creating Your Own Advanced Courses

### Step 1: Plan Your Drill
- What movement pattern?
- How many checkpoints?
- What timing requirements?
- Any special rules?

### Step 2: Choose Advanced Features
- **Device Function**: What role does each cone play?
- **Detection Method**: Touch or proximity?
- **Device Groups**: Any logical groupings?
- **Custom Rules**: What timing/scoring rules?

### Step 3: Create in UI
1. Go to Course Design page
2. Add basic course info
3. Add devices with actions
4. Expand "Advanced Settings" on each device
5. Set Device Function, Detection Method
6. Add Device Group name
7. Add Custom Rules (if needed)
8. Save and test!

---

## Tips for Coaches

### Start Simple
- Try running the example courses first
- Duplicate and modify rather than creating from scratch
- Focus on one advanced feature at a time

### Common Patterns
- **Speed Work**: Use `proximity` detection for uninterrupted sprints
- **Agility**: Use `turnaround` functions and split timing
- **Conditioning**: Use `recovery_period` and min/max times
- **Skills**: Use `pattern_type` for reactive drills

### Naming Conventions
- Use descriptive Device Groups: `start_line` not `group1`
- Write rules in plain language: `min_time: 2.5` is clear
- Keep it simple - coaches understand yards/seconds, not technical jargon

### Testing
- Always test new courses with yourself first
- Start with easier difficulty and scale up
- Verify timing constraints make sense for your athletes
- Check that Device Groups are named consistently

---

## Troubleshooting

### Course Not Appearing
- Restart server: `sudo systemctl restart field-trainer-server`
- Check course was saved successfully
- Verify device IDs are correct

### Advanced Fields Not Saving
- Make sure to expand "Advanced Settings" section
- Don't leave dropdown as "-- Not Set --" if you want a value
- Custom Rules must use `key: value` format (not JSON brackets)

### Timing Not Working as Expected
- Check min_time is less than max_time
- Verify Custom Rules syntax: `min_time: 2.5, max_time: 5.0`
- Test with generous time windows first, then tighten

---

## Summary

Five example courses now available demonstrating:
1. **Yo-Yo IR Test** - Recovery intervals
2. **5-10-5 Pro Agility** - NFL Combine standard
3. **Simon Says** - Cognitive reaction training
4. **Box Drill** - Technique enforcement
5. **Proximity Sprint** - Max speed testing

All courses use advanced fields properly and are ready to run or duplicate!

**View them at**: `http://192.168.7.116:5001/courses`
