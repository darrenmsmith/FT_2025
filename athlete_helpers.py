"""
Simplified athlete management functions
Optimized for <100 athletes on Raspberry Pi
"""

import sqlite3
import json
import csv
from datetime import datetime, date, timedelta
from contextlib import contextmanager
import os
import base64
from PIL import Image
import io
import logging

# Configuration
DB_PATH = '/opt/data/field_trainer.db'
PHOTO_DIR = '/field_trainer_data/athlete_photos'
MAX_PHOTO_SIZE = (800, 800)
VALID_GENDERS = ['male', 'female', 'non-binary']

logger = logging.getLogger(__name__)

@contextmanager
def get_db():
    """Simple database connection"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception as e:
        conn.rollback()
        logger.error(f"Database error: {e}")
        raise
    finally:
        conn.close()

def generate_athlete_number():
    """Generate unique athlete ID: ATH-YYYY-NNNN"""
    year = datetime.now().year
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT MAX(CAST(SUBSTR(athlete_number, -4) AS INTEGER)) FROM athletes WHERE athlete_number LIKE ?",
            (f"ATH-{year}-%",)
        )
        result = cursor.fetchone()
        last_num = result[0] if result and result[0] else 0
        next_num = last_num + 1
        return f"ATH-{year}-{next_num:04d}"

def calculate_age(birthdate):
    """Calculate age and COPPA status"""
    if isinstance(birthdate, str):
        birthdate = datetime.strptime(birthdate, '%Y-%m-%d').date()
    elif not birthdate:
        return {'age': 0, 'is_minor': True, 'requires_coppa': True, 'age_group': 'Unknown'}

    today = date.today()
    age = today.year - birthdate.year - ((today.month, today.day) < (birthdate.month, birthdate.day))

    return {
        'age': age,
        'is_minor': age < 18,
        'requires_coppa': age < 13,
        'age_group': f"U{((age // 2) + 1) * 2}"  # U10, U12, U14, etc.
    }

def create_athlete(first_name, last_name, birthdate, gender=None,
                  display_name=None, consent_given_by=None):
    """Create new athlete with automatic number generation"""

    # Validate age and consent (consent tracking, but not strictly required)
    age_info = calculate_age(birthdate)
    # Note: consent_given_by can be provided later via contacts

    athlete_number = generate_athlete_number()

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO athletes (
                athlete_number, first_name, last_name, display_name,
                birthdate, gender, consent_given_by, consent_date
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            athlete_number, first_name, last_name, display_name,
            birthdate, gender, consent_given_by,
            datetime.now() if consent_given_by else None
        ))

        athlete_id = cursor.lastrowid
        logger.info(f"Created athlete: {athlete_number} - {first_name} {last_name}")

        return athlete_id, athlete_number

def add_contact(athlete_id, name, phone, relationship='parent',
                email=None, is_primary=False, can_pickup=True):
    """Add contact for athlete"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO athlete_contacts
            (athlete_id, name, phone, email, relationship, is_primary, can_pickup, emergency_contact)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (athlete_id, name, phone, email, relationship, is_primary, can_pickup, True))

        contact_id = cursor.lastrowid
        logger.info(f"Added contact for athlete {athlete_id}: {name}")
        return contact_id

def add_medical_info(athlete_id, allergies=None, allergy_severity=None, conditions=None,
                     physician_name=None, physician_phone=None):
    """Add or update medical information"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO athlete_medical
            (athlete_id, allergies, allergy_severity, medical_conditions,
             physician_name, physician_phone, last_updated)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (athlete_id, allergies, allergy_severity, conditions,
              physician_name, physician_phone, date.today()))

        logger.info(f"Updated medical info for athlete {athlete_id}")

def save_athlete_photo(athlete_id, image_data, source='upload'):
    """Save athlete photo (file upload or camera)"""
    athlete = get_athlete(athlete_id)
    if not athlete:
        raise ValueError("Athlete not found")

    # Create filename with year/month organization
    year = datetime.now().strftime('%Y')
    month = datetime.now().strftime('%m')
    filename = f"{athlete['athlete_number']}.jpg"

    # Create directory if needed
    photo_dir = os.path.join(PHOTO_DIR, year, month)
    os.makedirs(photo_dir, exist_ok=True)

    filepath = os.path.join(photo_dir, filename)

    # Process image
    if isinstance(image_data, str) and image_data.startswith('data:image'):
        # Base64 from camera
        image_data = image_data.split(',')[1]
        image = Image.open(io.BytesIO(base64.b64decode(image_data)))
    else:
        # File upload
        image = Image.open(image_data)

    # Resize and save
    image.thumbnail(MAX_PHOTO_SIZE, Image.Resampling.LANCZOS)

    # Convert to RGB if necessary
    if image.mode in ('RGBA', 'P'):
        rgb_image = Image.new('RGB', image.size, (255, 255, 255))
        if image.mode == 'RGBA':
            rgb_image.paste(image, mask=image.split()[3])
        else:
            rgb_image.paste(image)
        image = rgb_image

    image.save(filepath, 'JPEG', quality=85, optimize=True)

    # Get file size
    file_size_kb = os.path.getsize(filepath) / 1024

    # Update database
    photo_path = f"{year}/{month}/{filename}"
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE athletes
            SET photo_filename = ?, photo_size_kb = ?, photo_upload_date = ?, photo_type = ?
            WHERE id = ?
        """, (photo_path, file_size_kb, datetime.now(), source, athlete_id))

    logger.info(f"Saved photo for athlete {athlete_id}: {photo_path} ({file_size_kb:.1f} KB)")
    return filename

def get_athlete(athlete_id):
    """Get athlete with calculated age"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT a.*,
                   COUNT(DISTINCT ta.team_id) as team_count,
                   GROUP_CONCAT(DISTINCT t.name) as teams
            FROM athletes a
            LEFT JOIN team_athletes ta ON a.id = ta.athlete_id
            LEFT JOIN teams t ON ta.team_id = t.team_id
            WHERE a.id = ? AND a.deleted = 0
            GROUP BY a.id
        """, (athlete_id,))

        row = cursor.fetchone()
        if row:
            athlete = dict(row)
            if athlete['birthdate']:
                athlete['age_info'] = calculate_age(athlete['birthdate'])
            else:
                athlete['age_info'] = {'age': 0, 'is_minor': True, 'requires_coppa': True, 'age_group': 'Unknown'}
            return athlete
        return None

def get_all_athletes(active_only=True, team_id=None):
    """Get all athletes with basic info"""
    with get_db() as conn:
        cursor = conn.cursor()

        query = """
            SELECT a.*,
                   COUNT(DISTINCT ta.team_id) as team_count,
                   GROUP_CONCAT(DISTINCT t.name) as teams,
                   (SELECT COUNT(*) FROM athlete_medical WHERE athlete_id = a.id
                    AND (allergies IS NOT NULL OR medical_conditions IS NOT NULL)) as has_medical,
                   am.allergy_severity,
                   (SELECT name FROM athlete_contacts WHERE athlete_id = a.id AND is_primary = 1 LIMIT 1) as primary_contact_name,
                   (SELECT phone FROM athlete_contacts WHERE athlete_id = a.id AND is_primary = 1 LIMIT 1) as primary_contact_phone
            FROM athletes a
            LEFT JOIN team_athletes ta ON a.id = ta.athlete_id
            LEFT JOIN teams t ON ta.team_id = t.team_id
            LEFT JOIN athlete_medical am ON a.id = am.athlete_id
            WHERE a.deleted = 0
        """

        params = []

        if active_only:
            query += " AND a.active = 1"

        if team_id:
            query += " AND ta.team_id = ?"
            params.append(team_id)

        query += " GROUP BY a.id ORDER BY a.last_name, a.first_name"

        cursor.execute(query, params)

        athletes = []
        for row in cursor.fetchall():
            athlete = dict(row)
            if athlete['birthdate']:
                athlete['age_info'] = calculate_age(athlete['birthdate'])
            else:
                athlete['age_info'] = {'age': 0, 'is_minor': True, 'requires_coppa': True, 'age_group': 'Unknown'}
            athletes.append(athlete)

        return athletes

def update_athlete(athlete_id, **kwargs):
    """Update athlete information"""
    allowed_fields = ['first_name', 'last_name', 'display_name', 'birthdate', 'gender',
                     'active', 'photo_consent', 'medical_clearance_date', 'medical_clearance_expires']

    updates = []
    values = []

    for key, value in kwargs.items():
        if key in allowed_fields:
            updates.append(f"{key} = ?")
            values.append(value)

    if not updates:
        return False

    values.append(athlete_id)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute(f"""
            UPDATE athletes
            SET {', '.join(updates)}
            WHERE id = ?
        """, values)

        success = cursor.rowcount > 0
        if success:
            logger.info(f"Updated athlete {athlete_id}")
        return success

def delete_athlete(athlete_id, soft=True):
    """Delete or soft-delete athlete"""
    with get_db() as conn:
        cursor = conn.cursor()
        if soft:
            cursor.execute("""
                UPDATE athletes
                SET deleted = 1, deleted_date = ?, active = 0
                WHERE id = ?
            """, (datetime.now(), athlete_id))
        else:
            cursor.execute("DELETE FROM athletes WHERE id = ?", (athlete_id,))

        logger.info(f"{'Soft-' if soft else ''}deleted athlete {athlete_id}")
        return cursor.rowcount > 0

def import_athletes_csv(csv_file, team_id=None, skip_duplicates=True):
    """Import athletes from CSV file"""
    results = {
        'imported': 0,
        'skipped': 0,
        'errors': []
    }

    reader = csv.DictReader(csv_file)

    for row_num, row in enumerate(reader, start=2):
        try:
            # Check for duplicates
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    SELECT id FROM athletes
                    WHERE LOWER(first_name) = LOWER(?)
                    AND LOWER(last_name) = LOWER(?)
                    AND birthdate = ?
                    AND deleted = 0
                """, (row['first_name'], row['last_name'], row['birthdate']))

                existing = cursor.fetchone()

                if existing:
                    if skip_duplicates:
                        if team_id:
                            # Add to team if not already on it
                            add_to_team(existing[0], team_id)
                        results['skipped'] += 1
                        continue

            # Create athlete
            athlete_id, athlete_number = create_athlete(
                first_name=row['first_name'],
                last_name=row['last_name'],
                birthdate=row['birthdate'],
                gender=row.get('gender'),
                consent_given_by=row.get('parent1_name')
            )

            # Add primary contact
            if row.get('parent1_name') and row.get('parent1_phone'):
                add_contact(
                    athlete_id=athlete_id,
                    name=row['parent1_name'],
                    phone=row['parent1_phone'],
                    email=row.get('parent1_email'),
                    is_primary=True
                )

            # Add secondary contact
            if row.get('parent2_name') and row.get('parent2_phone'):
                add_contact(
                    athlete_id=athlete_id,
                    name=row['parent2_name'],
                    phone=row['parent2_phone'],
                    email=row.get('parent2_email')
                )

            # Add medical info
            if row.get('allergies') or row.get('medical_conditions'):
                # Determine severity from allergies text
                severity = None
                if row.get('allergies'):
                    allergies_lower = row['allergies'].lower()
                    if 'severe' in allergies_lower or 'life-threatening' in allergies_lower:
                        severity = 'severe'
                    elif 'moderate' in allergies_lower:
                        severity = 'moderate'

                add_medical_info(
                    athlete_id=athlete_id,
                    allergies=row.get('allergies'),
                    allergy_severity=severity,
                    conditions=row.get('medical_conditions')
                )

            # Add to team
            if team_id:
                add_to_team(athlete_id, team_id)

            results['imported'] += 1

        except Exception as e:
            results['errors'].append(f"Row {row_num}: {str(e)}")
            logger.error(f"CSV import error on row {row_num}: {e}")

    logger.info(f"CSV import complete: {results['imported']} imported, {results['skipped']} skipped, {len(results['errors'])} errors")
    return results

def add_to_team(athlete_id, team_id, jersey_number=None, position=None):
    """Add athlete to team (handles multi-team)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT OR IGNORE INTO team_athletes
            (athlete_id, team_id, jersey_number, position)
            VALUES (?, ?, ?, ?)
        """, (athlete_id, team_id, jersey_number, position))

        if cursor.rowcount > 0:
            logger.info(f"Added athlete {athlete_id} to team {team_id}")
        return cursor.rowcount > 0

def remove_from_team(athlete_id, team_id):
    """Remove athlete from team"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            DELETE FROM team_athletes
            WHERE athlete_id = ? AND team_id = ?
        """, (athlete_id, team_id))

        if cursor.rowcount > 0:
            logger.info(f"Removed athlete {athlete_id} from team {team_id}")
        return cursor.rowcount > 0

def export_all_athletes_csv():
    """Export all athletes as CSV"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.athlete_number, a.first_name, a.last_name, a.birthdate, a.gender, a.display_name,
                (SELECT name FROM athlete_contacts WHERE athlete_id = a.id AND is_primary = 1 LIMIT 1) as primary_contact,
                (SELECT phone FROM athlete_contacts WHERE athlete_id = a.id AND is_primary = 1 LIMIT 1) as primary_phone,
                (SELECT email FROM athlete_contacts WHERE athlete_id = a.id AND is_primary = 1 LIMIT 1) as primary_email,
                am.allergies, am.allergy_severity, am.medical_conditions,
                GROUP_CONCAT(DISTINCT t.name) as teams
            FROM athletes a
            LEFT JOIN athlete_medical am ON a.id = am.athlete_id
            LEFT JOIN team_athletes ta ON a.id = ta.athlete_id
            LEFT JOIN teams t ON ta.team_id = t.team_id
            WHERE a.deleted = 0 AND a.active = 1
            GROUP BY a.id
            ORDER BY a.last_name, a.first_name
        """)

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Athlete Number', 'First Name', 'Last Name', 'Birthdate', 'Age', 'Gender', 'Display Name',
            'Primary Contact', 'Phone', 'Email', 'Teams',
            'Allergies', 'Allergy Severity', 'Medical Conditions'
        ])

        # Data
        for row in cursor.fetchall():
            athlete = dict(row)
            age = calculate_age(athlete['birthdate'])['age'] if athlete['birthdate'] else ''
            writer.writerow([
                athlete['athlete_number'] or '',
                athlete['first_name'],
                athlete['last_name'],
                athlete['birthdate'] or '',
                age,
                athlete['gender'] or '',
                athlete['display_name'] or '',
                athlete['primary_contact'] or '',
                athlete['primary_phone'] or '',
                athlete['primary_email'] or '',
                athlete['teams'] or '',
                athlete['allergies'] or '',
                athlete['allergy_severity'] or '',
                athlete['medical_conditions'] or ''
            ])

        return output.getvalue()

def export_team_roster_csv(team_id):
    """Export team roster as CSV"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.first_name, a.last_name, a.birthdate, a.gender,
                ta.jersey_number, ta.position,
                (SELECT name FROM athlete_contacts WHERE athlete_id = a.id AND is_primary = 1 LIMIT 1) as primary_contact,
                (SELECT phone FROM athlete_contacts WHERE athlete_id = a.id AND is_primary = 1 LIMIT 1) as primary_phone,
                (SELECT email FROM athlete_contacts WHERE athlete_id = a.id AND is_primary = 1 LIMIT 1) as primary_email,
                am.allergies, am.medical_conditions
            FROM athletes a
            JOIN team_athletes ta ON a.id = ta.athlete_id
            LEFT JOIN athlete_medical am ON a.id = am.athlete_id
            WHERE ta.team_id = ? AND a.deleted = 0
            ORDER BY a.last_name, a.first_name
        """, (team_id,))

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'First Name', 'Last Name', 'Birthdate', 'Age', 'Gender',
            'Jersey', 'Position', 'Primary Contact', 'Phone', 'Email',
            'Allergies', 'Medical Conditions'
        ])

        # Data
        for row in cursor.fetchall():
            athlete = dict(row)
            age = calculate_age(athlete['birthdate'])['age'] if athlete['birthdate'] else ''
            writer.writerow([
                athlete['first_name'],
                athlete['last_name'],
                athlete['birthdate'] or '',
                age,
                athlete['gender'] or '',
                athlete['jersey_number'] or '',
                athlete['position'] or '',
                athlete['primary_contact'] or '',
                athlete['primary_phone'] or '',
                athlete['primary_email'] or '',
                athlete['allergies'] or '',
                athlete['medical_conditions'] or ''
            ])

        return output.getvalue()

def check_data_retention():
    """Archive athletes inactive for 3+ years (COPPA compliance)"""
    three_years_ago = datetime.now().date() - timedelta(days=3*365)

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE athletes
            SET deleted = 1, deleted_date = CURRENT_TIMESTAMP
            WHERE active = 0
            AND inactive_date < ?
            AND deleted = 0
        """, (three_years_ago,))

        count = cursor.rowcount
        if count > 0:
            logger.info(f"Auto-archived {count} athletes due to 3-year retention policy")
        return count
