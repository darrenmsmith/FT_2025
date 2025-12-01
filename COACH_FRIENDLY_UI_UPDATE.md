# Coach-Friendly UI Labels & Tooltips - Update

**Date**: November 21, 2025
**Status**: ✅ COMPLETE
**Changes**: Replaced technical jargon with coach-friendly terminology + added helpful tooltips

---

## Changes Made

### Label Updates

| Old Label (Technical) | New Label (Coach-Friendly) | Tooltip Added |
|----------------------|---------------------------|---------------|
| Group Identifier | **Device Group** | ✅ Yes |
| Behavior Config (JSON) | **Custom Rules** | ✅ Yes |
| Device Function | Device Function | No change needed |
| Detection Method | Detection Method | No change needed |

---

## Tooltip Content

### Device Group Field
**Label**: Device Group
**Tooltip**: "Assign devices to groups (e.g., 'start_line', 'finish_line') to trigger them together or track patterns"
**Placeholder**: `e.g., start_line, finish_line, cone_group_1`

**Purpose**: Helps coaches understand they can:
- Group multiple devices together
- Trigger devices simultaneously
- Track patterns across device groups
- Use meaningful names instead of IDs

---

### Custom Rules Field
**Label**: Custom Rules
**Tooltip**: "Advanced settings for custom behaviors like timing rules, scoring, or special conditions"
**Placeholder**: `Example: min_time: 2.5, max_time: 10.0, scoring: true`

**Purpose**: Explains without using "JSON" that coaches can:
- Set timing requirements
- Enable scoring modes
- Add special conditions
- Customize drill behavior

**Format Change**: Instead of JSON example `{"key": "value"}`, now shows coach-friendly example:
- `min_time: 2.5, max_time: 10.0, scoring: true`

---

## Visual Design

### Tooltip Appearance
```
┌─────────────────────────────────────────────┐
│ Device Group    ?                           │ ← Hover over "?" to see tooltip
│ [                                         ] │
└─────────────────────────────────────────────┘

When hovering over "?":
┌──────────────────────────────────────────────────────┐
│ Assign devices to groups (e.g., 'start_line',       │
│ 'finish_line') to trigger them together or track    │
│ patterns                                             │
└────────────────────────┬─────────────────────────────┘
                         ▼
                         ?  ← Cursor here
```

### Tooltip Styling
- **Background**: Dark gray (#2c3e50)
- **Text**: White, 12px
- **Icon**: Circular gray button with "?" symbol
- **Behavior**: Appears on hover above the icon
- **Mobile**: Wraps text on small screens (max-width: 200px)

---

## Complete Advanced Settings Section

```
┌─────────────────────────────────────────────────────────┐
│ ▼ Advanced Settings (Optional)                          │
├─────────────────────────────────────────────────────────┤
│ Device Function           Detection Method              │
│ [-- Not Set --    ▼]     [-- Not Set --       ▼]       │
│                                                          │
│ Device Group ?            Custom Rules ?                 │
│ [start_line           ]   [min_time: 2.5, ...        ]  │
│                           [                           ]  │
└─────────────────────────────────────────────────────────┘
```

### Field Descriptions for Coaches:

1. **Device Function**: What role does this device play?
   - Start/Finish: Beginning or end point
   - Waypoint: Checkpoint along the way
   - Turnaround: Point where athlete changes direction
   - Boundary: Edge or limit of drill area
   - Timer: Time-only checkpoint

2. **Detection Method**: How does the device detect the athlete?
   - Touch: Physical contact with sensor
   - Proximity: Gets close but doesn't touch
   - None: Time-based only, no detection

3. **Device Group** ✨ (with tooltip): Group devices together
   - Example: All cones on "line_a" activate together
   - Example: Track "start_line" and "finish_line" separately
   - Use descriptive names coaches understand

4. **Custom Rules** ✨ (with tooltip): Add special drill requirements
   - Example: `min_time: 2.5` = must take at least 2.5 seconds
   - Example: `max_time: 10.0` = must finish within 10 seconds
   - Example: `scoring: true` = enable point tracking
   - Use simple key-value format (not JSON jargon)

---

## Why These Changes Matter

### Before (Technical)
❌ "Group Identifier" - What's an identifier?
❌ "Behavior Config (JSON)" - What's JSON?
❌ Placeholder: `{"key": "value"}` - Confusing syntax
❌ No tooltips - Coaches have to guess

### After (Coach-Friendly)
✅ "Device Group" - Clear, simple term
✅ "Custom Rules" - Coaches understand "rules"
✅ Placeholder: `min_time: 2.5, max_time: 10.0` - Real examples
✅ Tooltips explain what each field does
✅ Hover hints show use cases

---

## Implementation Details

### CSS Added (Lines 242-299)
```css
.field-label-with-tooltip {
    display: flex;
    align-items: center;
    gap: 6px;
}

.tooltip-icon {
    width: 16px;
    height: 16px;
    border-radius: 50%;
    background: #6c757d;
    color: white;
    font-size: 11px;
    cursor: help;
}

.tooltip-icon:hover::after {
    content: attr(data-tooltip);
    position: absolute;
    padding: 8px 12px;
    background: #2c3e50;
    color: white;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}
```

### HTML Structure
```html
<label class="field-label-with-tooltip">
    <span>Device Group</span>
    <span class="tooltip-icon"
          data-tooltip="Assign devices to groups...">?</span>
</label>
<input type="text"
       placeholder="e.g., start_line, finish_line, cone_group_1">
```

---

## Testing the Tooltips

### Desktop
1. Go to `http://192.168.7.116:5001/courses/design`
2. Add a device
3. Click "▶ Advanced Settings (Optional)"
4. Hover mouse over the "?" icon next to "Device Group"
5. **Expected**: Tooltip appears above the icon with help text
6. Hover over "?" next to "Custom Rules"
7. **Expected**: Tooltip appears with different help text

### Mobile/Tablet
1. Tap a device to add it
2. Expand advanced settings
3. Tap and hold the "?" icon
4. **Expected**: Tooltip appears with wrapped text (max 200px width)

---

## Backwards Compatibility

✅ **Database fields unchanged** - Still stores:
- `group_identifier` (TEXT)
- `behavior_config` (TEXT)

✅ **API unchanged** - Backend still expects same field names

✅ **Only UI labels changed** - Technical fields remain in code, only user-facing text improved

---

## Future Enhancements (Optional)

### Potential Improvements
1. **Interactive Examples**: Click tooltip to insert example values
2. **Validation Messages**: "Custom Rules format: key: value, key: value"
3. **Preset Templates**: Dropdown with common group names
4. **Video Tutorials**: Link tooltips to short explainer videos
5. **Context-Sensitive Help**: Show different tips based on course type

---

## Summary

### What Changed
- ❌ "Group Identifier" → ✅ "Device Group"
- ❌ "Behavior Config (JSON)" → ✅ "Custom Rules"
- ❌ JSON example → ✅ Coach-friendly example format
- ✨ Added tooltips with helpful explanations
- ✨ Added "?" help icons that appear on hover

### Coach Benefits
- Clear, understandable terminology
- Helpful tooltips explain each field
- Real-world examples instead of technical syntax
- No need to understand JSON or programming terms
- Hover hints provide guidance without cluttering UI

### Technical Details
- Tooltips use pure CSS (no JavaScript needed)
- Responsive on mobile (text wraps)
- Accessible (cursor: help, proper contrast)
- Lightweight (~60 lines CSS)

---

**Status**: LIVE at `http://192.168.7.116:5001/courses/design`

Coaches can now create advanced courses with confidence, understanding exactly what each field does!
