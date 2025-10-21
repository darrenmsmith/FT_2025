# Field Trainer Test Programs Registry

## Overview
This document tracks all automated test programs for the Field Trainer system.

---

## Test Programs

### 1. Database Integrity Test Suite ✅ COMPLETE
**File:** `/opt/test_database_integrity.py`  
**Status:** Production Ready  
**Last Updated:** 2025-10-20  
**Duration:** ~0.5 seconds

**Purpose:**  
Validates database schema, constraints, and data integrity

**Tests Included:**
- ✅ Test 1: Duplicate Segment Prevention
  - Verifies UNIQUE(run_id, sequence) constraint
  - Tests create_segments_for_run() duplicate detection
  - Validates database-level constraint enforcement

- ✅ Test 2: Foreign Key Cascade Deletion
  - Confirms session deletion cascades to runs
  - Confirms run deletion cascades to segments
  - Detects orphaned data

- ✅ Test 3: Data Integrity Validation
  - Checks sequence number uniqueness per run
  - Validates no negative segment times
  - Verifies timing calculation accuracy

- ✅ Test 4: Database Constraint Validation
  - Tests NOT NULL constraints
  - Tests CHECK constraints (alert_type)
  - Validates schema completeness

**Prerequisites:**
- At least one team in database
- At least one athlete (Billie, Jill, Sarah, Bobby, or Ella)
- Course A (course_id=1) configured

**Usage:**
```bash
cd /opt
sudo python3 test_database_integrity.py
```

**Success Criteria:**
- All 4 tests pass
- No orphaned data
- All constraints enforced
- Results saved to `/tmp/db_test_results_YYYYMMDD_HHMMSS.txt`

**Known Limitations:**
- Requires real team/athlete data (cannot run on empty database)
- Foreign keys must be enabled (PRAGMA foreign_keys = ON)
- Tests clean up after themselves (safe to run repeatedly)

---

### 2. Attribution Logic Tests ✅ COMPLETE
**File:** `/opt/test_attribution_logic.py`  
**Status:** Production Ready  
**Last Updated:** 2025-10-20  
**Duration:** ~1 second

**Purpose:**  
Unit tests for multi-athlete touch attribution algorithm

**Tests Included:**
- ✅ Category 1: Gap Calculation (6 tests)
  - Sequential touch (gap=1)
  - Skip one device (gap=2)
  - Skip multiple devices (gap=4)
  - Same device twice (gap=0)
  - Backwards touch (gap<0)
  - Not started yet (gap from -1)

- ✅ Category 2: Priority Sorting (4 tests)
  - Multiple Priority 1 athletes - queue tiebreaker
  - Priority 1 beats Priority 2
  - Priority 2 - closest gap wins
  - Priority 2 - same gap, queue tiebreaker

- ✅ Category 3: Edge Cases (5 tests)
  - No active athletes
  - Device not in course sequence
  - All athletes filtered out
  - Athlete at finish, early device touched
  - Missing queue_position in data

- ✅ Category 4: Multi-Athlete Scenarios (4 tests)
  - Three athletes staggered positions
  - Wave start at D1
  - Simultaneous skip
  - Sequential vs skip (Priority 1 wins)

**Prerequisites:**
- coach_interface.py must be importable
- find_athlete_for_touch() function available
- active_session_state accessible

**Usage:**
```bash
cd /opt
sudo python3 test_attribution_logic.py
```

**Success Criteria:**
- All 19 tests pass (4 categories)
- No crashes on edge cases
- Priority system validated
- Results saved to `/tmp/attribution_test_results_YYYYMMDD_HHMMSS.txt`

**Known Limitations:**
- Tests logic only, not actual device integration
- Requires coach_interface module to be working
- Does not test database updates after attribution

---

### 3. Touch Sequence Simulation Tests 🚧 PLANNED
**File:** `/opt/test_touch_sequences.py`  
**Status:** Not Yet Created  
**Estimated Duration:** ~2 seconds

**Purpose:**  
Simulated multi-athlete touch scenarios

**Planned Tests:**
- Skip detection (various gap sizes)
- Same device double-touch rejection
- Backwards touch rejection
- Out-of-order multi-athlete attribution
- Simultaneous touches on same device

---

### 4. API Integration Tests 🚧 PLANNED
**File:** `/opt/test_api_integration.py`  
**Status:** Not Yet Created  
**Estimated Duration:** ~3 seconds

**Purpose:**  
REST API endpoint validation

**Planned Tests:**
- Session lifecycle (create/start/stop)
- Course deployment and activation
- State transitions
- Error handling and validation
- Concurrent API calls

---

### 5. Load & Stress Tests 🚧 PLANNED
**File:** `/opt/test_load_stress.py`  
**Status:** Not Yet Created  
**Estimated Duration:** ~30 seconds

**Purpose:**  
Performance and scalability testing

**Planned Tests:**
- 10+ simultaneous athletes
- 100+ sessions with segments
- Database query performance
- Memory usage monitoring
- Sustained load (marathon session)

---
### 6. Concurrent Operations Tests ✅ COMPLETE
**File:** `/opt/test_concurrency.py`  
**Status:** Production Ready  
**Last Updated:** 2025-10-20  
**Duration:** ~14 seconds

**Purpose:**  
Tests race conditions, concurrent operations, and database locking behavior

**Tests Included:**
- ✅ Test 1: Simultaneous Session Starts
  - 5 threads starting runs concurrently
  - Validates UNIQUE constraint prevents duplicate segments
  - Tests create_segments_for_run() race condition protection

- ✅ Test 2: Concurrent Database Writes
  - 10 threads writing touch data simultaneously
  - Validates database connection pooling
  - Ensures data integrity under concurrent load

- ✅ Test 3: Touch Handler Under Load
  - 20 concurrent touches to attribution system
  - Tests find_athlete_for_touch() thread safety
  - Validates active_session_state doesn't corrupt

- ✅ Test 4: Database Lock Handling
  - Long-running transaction blocking others
  - Tests SQLite lock timeout behavior
  - Validates graceful error handling

**Prerequisites:**
- Real team and athletes in database
- coach_interface.py importable
- Database write access

**Usage:**
```bash
cd /opt
sudo python3 test_concurrency.py
```

**Success Criteria:**
- All 4 tests pass
- No deadlocks or hangs
- Graceful lock timeout handling
- Results saved to `/tmp/concurrency_test_results_YYYYMMDD_HHMMSS.txt`

## Test Execution Matrix

| Test Program | Automated | Hardware Required | Database Required | Duration |
|--------------|-----------|-------------------|-------------------|----------|
| Database Integrity | ✅ Yes | ❌ No | ✅ Yes | 0.5s |
| Attribution Logic | ✅ Yes | ❌ No | ✅ Yes | 1s |
| Touch Sequences | ✅ Yes | ⚠️ Simulated | ✅ Yes | 2s |
| API Integration | ✅ Yes | ❌ No | ✅ Yes | 3s |
| Load & Stress | ✅ Yes | ❌ No | ✅ Yes | 30s |
| Concurrency | ✅ Yes | ❌ No | ✅ Yes | 5s |

**Legend:**
- ✅ = Available/Required
- ❌ = Not needed
- ⚠️ = Partial/simulated
- 🚧 = In development

---

## Running All Tests

### Quick Test Suite (Essential Tests Only)
```bash
cd /opt
sudo python3 test_database_integrity.py
```

### Full Test Suite (When Complete)
```bash
cd /opt
./run_all_tests.sh
```

---

## Test Results Location

All test results are saved to `/tmp/` with timestamped filenames:
- `/tmp/db_test_results_YYYYMMDD_HHMMSS.txt`
- `/tmp/attribution_test_results_YYYYMMDD_HHMMSS.txt`
- `/tmp/touch_sequence_results_YYYYMMDD_HHMMSS.txt`
- etc.

---

## Production Testing Checklist

Before deploying to production, ensure:

- [ ] All database integrity tests pass
- [ ] All attribution logic tests pass
- [ ] Skip detection working correctly
- [ ] 10+ athlete load test passes
- [ ] Foreign key cascades verified
- [ ] No duplicate segments possible
- [ ] Timing accuracy within ±100ms
- [ ] System recovers from crashes gracefully

---

## Continuous Integration

### Pre-Commit Tests (Fast)
Run before committing code changes:
```bash
sudo python3 /opt/test_database_integrity.py
```

### Pre-Deployment Tests (Comprehensive)
Run before system updates:
```bash
# All quick tests
sudo python3 /opt/test_database_integrity.py
sudo python3 /opt/test_attribution_logic.py
sudo python3 /opt/test_touch_sequences.py
```

### Weekly Regression Tests
Full suite including load tests:
```bash
./run_all_tests.sh
```

---

## Troubleshooting Test Failures

### Database Tests Failing
1. Check foreign keys enabled: `PRAGMA foreign_keys`
2. Verify team/athlete data exists
3. Check database file permissions
4. Review `/tmp/db_test_results_*.txt` for details

### Attribution Tests Failing
1. Verify active_session_state structure
2. Check device_sequence populated
3. Review touch handler registration
4. Inspect test output for gap calculations

### Touch Sequence Tests Failing
1. Verify REGISTRY is accessible
2. Check database has test data
3. Review timing calculations
4. Inspect segment creation logic

---

## Adding New Tests

When creating a new test program:

1. Follow naming convention: `test_<category>_<name>.py`
2. Add to this registry with status, purpose, tests
3. Save results to `/tmp/<name>_results_YYYYMMDD_HHMMSS.txt`
4. Update test execution matrix
5. Document prerequisites and usage
6. Add to appropriate test suite (quick/full)

---

## Version History

| Date | Version | Changes | Author |
|------|---------|---------|--------|
| 2025-10-20 | 1.0 | Initial registry, Database Integrity Tests complete | System |
| | | | |

---

## Contact & Support

For questions about test programs:
- Review test output files in `/tmp/`
- Check this registry for test documentation
- Review individual test file docstrings

---

**Last Updated:** 2025-10-20  
**Registry Version:** 1.0
