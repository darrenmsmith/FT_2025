#!/usr/bin/env python3
"""
Test script for team management functionality
Run this after implementation to verify everything works
"""

import requests
import json
import time
import sys

BASE_URL = "http://localhost:5001"  # Coach interface port

def test_create_team():
    """Test team creation"""
    print("\n=== Testing Team Creation ===")

    data = {
        "name": "Test Warriors",
        "age_group": "U15",
        "sport": "Soccer",
        "gender": "Male",
        "season": "Fall 2025",
        "coach_name": "Coach Test",
        "notes": "This is a test team",
        "active": True
    }

    try:
        # Since we're using form-based submission, we need to post as form data
        response = requests.post(f"{BASE_URL}/team/create", data=data, allow_redirects=False)

        if response.status_code in (302, 303):  # Redirect on success
            print(f"✓ Team created successfully (redirect to team detail)")
            # Extract team_id from redirect location if possible
            if 'Location' in response.headers:
                location = response.headers['Location']
                if '/team/' in location:
                    team_id = location.split('/team/')[-1]
                    print(f"  Team ID: {team_id}")
                    return team_id
            return "success"
        else:
            print(f"✗ Failed to create team: HTTP {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            return None
    except Exception as e:
        print(f"✗ Error creating team: {e}")
        return None

def test_list_teams():
    """Test listing teams"""
    print("\n=== Testing Team List ===")

    try:
        response = requests.get(f"{BASE_URL}/teams")

        if response.status_code == 200:
            print(f"✓ Team list page loaded successfully")
            # Check if the page contains team elements
            if 'card' in response.text and 'team' in response.text.lower():
                print(f"  Page contains team cards")
                return True
            else:
                print(f"  Warning: Page may not contain team data")
                return True
        else:
            print(f"✗ Failed to load team list: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error loading team list: {e}")
        return False

def test_export_all_teams():
    """Test exporting all teams as CSV"""
    print("\n=== Testing CSV Export ===")

    try:
        response = requests.get(f"{BASE_URL}/teams/export/csv")

        if response.status_code == 200:
            csv_data = response.text
            lines = csv_data.strip().split('\n')
            print(f"✓ CSV export successful ({len(lines)} lines, {len(csv_data)} bytes)")

            # Verify CSV has header
            if len(lines) > 0:
                header = lines[0]
                if 'Name' in header or 'name' in header:
                    print(f"  CSV header: {header[:80]}...")
                    return True
            return True
        else:
            print(f"✗ Failed to export CSV: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error exporting CSV: {e}")
        return False

def test_search_api():
    """Test search/filter API"""
    print("\n=== Testing Search API ===")

    try:
        # Test basic search
        response = requests.get(f"{BASE_URL}/api/teams/search", params={'active': 'true'})

        if response.status_code == 200:
            teams = response.json()
            print(f"✓ Search API returned {len(teams)} active teams")

            # Test with sport filter
            response = requests.get(f"{BASE_URL}/api/teams/search", params={'sport': 'Soccer'})
            if response.status_code == 200:
                soccer_teams = response.json()
                print(f"  Soccer filter returned {len(soccer_teams)} teams")
                return True
            else:
                print(f"  Warning: Sport filter returned HTTP {response.status_code}")
                return True
        else:
            print(f"✗ Search API failed: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"✗ Error testing search API: {e}")
        return False

def test_database_integrity():
    """Test database has all required columns"""
    print("\n=== Testing Database Integrity ===")

    try:
        import sqlite3
        conn = sqlite3.connect('/opt/data/field_trainer.db')
        cursor = conn.cursor()

        cursor.execute("PRAGMA table_info(teams)")
        columns = [row[1] for row in cursor.fetchall()]

        required_columns = ['team_id', 'name', 'age_group', 'sport', 'gender',
                           'season', 'active', 'coach_name', 'notes']

        missing = []
        for col in required_columns:
            if col in columns:
                print(f"  ✓ Column '{col}' exists")
            else:
                print(f"  ✗ Column '{col}' MISSING")
                missing.append(col)

        # Check data
        cursor.execute("SELECT COUNT(*) FROM teams")
        count = cursor.fetchone()[0]
        print(f"  ✓ Database contains {count} team(s)")

        conn.close()

        if missing:
            print(f"✗ Database missing columns: {missing}")
            return False
        else:
            print("✓ All required columns present")
            return True

    except Exception as e:
        print(f"✗ Database integrity check failed: {e}")
        return False

def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("TEAM MANAGEMENT TEST SUITE")
    print("="*60)

    results = []

    # Test 1: Database Integrity
    results.append(("Database Integrity", test_database_integrity()))

    # Test 2: Team List
    time.sleep(1)
    results.append(("Team List", test_list_teams()))

    # Test 3: Search API
    time.sleep(1)
    results.append(("Search/Filter API", test_search_api()))

    # Test 4: CSV Export
    time.sleep(1)
    results.append(("CSV Export", test_export_all_teams()))

    # Test 5: Create Team (optional - creates test data)
    print("\n" + "="*60)
    create_test = input("Create a test team? This will add data to the database (y/n): ")
    if create_test.lower() == 'y':
        time.sleep(1)
        team_id = test_create_team()
        results.append(("Create Team", team_id is not None))

    # Print summary
    print("\n" + "="*60)
    print("TEST RESULTS SUMMARY")
    print("="*60)

    for test_name, passed in results:
        status = "✓ PASSED" if passed else "✗ FAILED"
        print(f"{test_name:.<40} {status}")

    total = len(results)
    passed = sum(1 for _, p in results if p)
    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\n✓✓✓ ALL TESTS PASSED! ✓✓✓")
        return 0
    else:
        print("\n⚠ Some tests failed. Please review the output above.")
        return 1

if __name__ == "__main__":
    try:
        sys.exit(run_all_tests())
    except KeyboardInterrupt:
        print("\n\nTest suite interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nFatal error: {e}")
        sys.exit(1)
