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
                  display_name=None, consent_given_by=None, team_id=None):
    """Create new athlete with automatic number generation"""

    # Validate age and consent (consent tracking, but not strictly required)
    age_info = calculate_age(birthdate)
    # Note: consent_given_by can be provided later via contacts

    athlete_number = generate_athlete_number()

    # Combine first_name and last_name for Field Trainer schema
    full_name = display_name if display_name else f"{first_name} {last_name}".strip()

    # Calculate age from birthdate for Field Trainer schema
    age = age_info.get('age')

    # Generate UUID for athlete_id to match Field Trainer schema
    import uuid
    athlete_id = str(uuid.uuid4())

    # Use a default team_id if none provided (will be updated when adding to team)
    if not team_id:
        # Use a placeholder - should be updated when athlete is added to a team
        team_id = ''

    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO athletes (
                athlete_id, team_id, name, athlete_number,
                birthdate, gender, age, created_at, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            athlete_id, team_id, full_name, athlete_number,
            birthdate, gender, age,
            datetime.now().isoformat(),
            datetime.now().isoformat()
        ))

        logger.info(f"Created athlete: {athlete_number} - {full_name}")

        return athlete_id, athlete_number

def add_contact(athlete_id, name, phone, relationship='parent',
                email=None, is_primary=False, can_pickup=True):
    """Add contact for athlete"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO athlete_contacts
            (athlete_id, name, phone, email, relationship, is_primary, can_pickup)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (athlete_id, name, phone, email, relationship, is_primary, can_pickup))

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
            (athlete_id, allergies, allergy_severity, medical_conditions, updated_at)
            VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """, (athlete_id, allergies, allergy_severity, conditions))

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

    # Note: Simple schema doesn't have photo columns in athletes table
    # Photo is stored in file system only, indexed by athlete_number
    photo_path = f"{year}/{month}/{filename}"

    logger.info(f"Saved photo for athlete {athlete_id}: {photo_path} ({file_size_kb:.1f} KB)")
    return photo_path

def get_athlete(athlete_id):
    """Get athlete with calculated age - Compatible with simple schema"""
    with get_db() as conn:
        cursor = conn.cursor()
        # Simple schema: athletes table with athlete_id, team_id, name, athlete_number, jersey_number, age, position
        cursor.execute("""
            SELECT a.athlete_id as id,
                   a.name,
                   a.athlete_number,
                   a.jersey_number,
                   a.age,
                   a.position,
                   a.team_id,
                   t.name as team_name,
                   a.created_at,
                   a.updated_at
            FROM athletes a
            LEFT JOIN teams t ON a.team_id = t.team_id
            WHERE a.athlete_id = ?
        """, (athlete_id,))

        row = cursor.fetchone()
        if row:
            athlete = dict(row)
            # Split name into first/last for compatibility
            name_parts = athlete['name'].split(' ', 1)
            athlete['first_name'] = name_parts[0] if name_parts else ''
            athlete['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
            athlete['display_name'] = athlete['name']
            athlete['teams'] = athlete.get('team_name', '')
            athlete['team_count'] = 1 if athlete.get('team_name') else 0
            athlete['active'] = 1
            athlete['deleted'] = 0
            athlete['birthdate'] = None  # Not in simple schema
            athlete['gender'] = None  # Not in simple schema
            return athlete
        return None

def get_all_athletes(active_only=True, team_id=None):
    """Get all athletes with basic info - Compatible with simple schema"""
    with get_db() as conn:
        cursor = conn.cursor()

        # Use simple schema: athletes table has athlete_id, team_id, name, athlete_number, jersey_number, age, position
        query = """
            SELECT a.athlete_id as id,
                   a.name,
                   a.athlete_number,
                   a.jersey_number,
                   a.age,
                   a.position,
                   a.team_id,
                   t.name as team_name,
                   a.created_at,
                   a.updated_at
            FROM athletes a
            LEFT JOIN teams t ON a.team_id = t.team_id
            WHERE 1=1
        """

        params = []

        if team_id:
            query += " AND a.team_id = ?"
            params.append(team_id)

        query += " ORDER BY a.name"

        cursor.execute(query, params)

        athletes = []
        for row in cursor.fetchall():
            athlete = dict(row)
            # Split name into first/last for compatibility
            name_parts = athlete['name'].split(' ', 1)
            athlete['first_name'] = name_parts[0] if name_parts else ''
            athlete['last_name'] = name_parts[1] if len(name_parts) > 1 else ''
            athlete['display_name'] = athlete['name']
            athlete['teams'] = athlete.get('team_name', '')
            athlete['team_count'] = 1 if athlete.get('team_name') else 0
            athlete['active'] = 1  # Default to active
            athlete['deleted'] = 0
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
    """Import athletes from CSV file - Supports full schema"""
    import uuid
    from datetime import datetime
    results = {
        'imported': 0,
        'skipped': 0,
        'errors': []
    }

    reader = csv.DictReader(csv_file)

    # Check if CSV is malformed (entire row as single field)
    fieldnames = reader.fieldnames
    is_malformed = len(fieldnames) == 1 and ',' in fieldnames[0]

    if is_malformed:
        # Parse the malformed CSV manually
        logger.info("Detected malformed CSV format, parsing manually")
        csv_file.seek(0)  # Reset to beginning
        lines = csv_file.readlines()

        # Parse header from quoted string
        if lines:
            header_line = lines[0].strip().strip('"')
            headers = [h.strip() for h in header_line.split(',')]

            # Parse data rows
            for row_num, line in enumerate(lines[1:], start=2):
                try:
                    # Remove quotes and split by comma
                    data_line = line.strip().strip('"')
                    values = [v.strip() for v in data_line.split(',')]

                    # Create row dict
                    row = dict(zip(headers, values))

                    # Process the row
                    first_name = row.get('First Name', '').strip()
                    last_name = row.get('Last Name', '').strip()
                    full_name = f"{first_name} {last_name}".strip()

                    if not full_name:
                        results['errors'].append(f"Row {row_num}: Missing name")
                        continue

                    # Get age
                    age_str = row.get('Age', '')
                    age = int(age_str) if age_str and age_str.isdigit() else None

                    # Check for duplicates by name
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            SELECT athlete_id FROM athletes
                            WHERE LOWER(name) = LOWER(?)
                        """, (full_name,))

                        existing = cursor.fetchone()

                        if existing:
                            if skip_duplicates:
                                # Update team_id if specified
                                if team_id:
                                    cursor.execute("""
                                        UPDATE athletes SET team_id = ?, updated_at = CURRENT_TIMESTAMP
                                        WHERE athlete_id = ?
                                    """, (team_id, existing[0]))
                                results['skipped'] += 1
                                continue

                    # Create new athlete
                    athlete_id = str(uuid.uuid4())
                    with get_db() as conn:
                        cursor = conn.cursor()
                        cursor.execute("""
                            INSERT INTO athletes (athlete_id, team_id, name, jersey_number, age, position, created_at, updated_at)
                            VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                        """, (
                            athlete_id,
                            team_id or '',
                            full_name,
                            0,  # Default jersey_number
                            age,
                            ''  # Default position
                        ))

                    results['imported'] += 1
                    logger.info(f"Imported athlete: {full_name}")

                except Exception as e:
                    results['errors'].append(f"Row {row_num}: {str(e)}")
                    logger.error(f"CSV import error on row {row_num}: {e}")

            logger.info(f"CSV import complete: {results['imported']} imported, {results['skipped']} skipped, {len(results['errors'])} errors")
            return results

    # Normal CSV processing
    for row_num, row in enumerate(reader, start=2):
        try:
            # Get name fields
            first_name = row.get('First Name', row.get('first_name', '')).strip()
            last_name = row.get('Last Name', row.get('last_name', '')).strip()
            full_name = f"{first_name} {last_name}".strip()

            if not full_name:
                results['errors'].append(f"Row {row_num}: Missing name")
                continue

            # Get birthdate and calculate age
            birthdate = row.get('birthdate', row.get('Birthdate', '')).strip()
            age = None
            if birthdate:
                try:
                    birth_date_obj = datetime.strptime(birthdate, '%Y-%m-%d').date()
                    age_info = calculate_age(birth_date_obj)
                    age = age_info['age']
                except:
                    pass

            # Get gender
            gender = row.get('gender', row.get('Gender', '')).strip().lower()

            # Check for duplicates by name and birthdate
            with get_db() as conn:
                cursor = conn.cursor()
                if birthdate:
                    cursor.execute("""
                        SELECT athlete_id FROM athletes
                        WHERE LOWER(name) = LOWER(?) AND birthdate = ?
                    """, (full_name, birthdate))
                else:
                    cursor.execute("""
                        SELECT athlete_id FROM athletes
                        WHERE LOWER(name) = LOWER(?)
                    """, (full_name,))

                existing = cursor.fetchone()

                if existing:
                    if skip_duplicates:
                        results['skipped'] += 1
                        continue

            # Generate athlete_number
            athlete_number = generate_athlete_number()

            # Create new athlete with full schema
            athlete_id = str(uuid.uuid4())
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    INSERT INTO athletes (athlete_id, team_id, name, athlete_number, jersey_number,
                                        age, birthdate, gender, position, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """, (
                    athlete_id,
                    team_id or '',
                    full_name,
                    athlete_number,
                    0,  # Default jersey_number
                    age,
                    birthdate or None,
                    gender or None,
                    ''  # Default position
                ))

            # Add parent1 contact if provided
            parent1_name = row.get('parent1_name', '').strip()
            parent1_phone = row.get('parent1_phone', '').strip()
            parent1_email = row.get('parent1_email', '').strip()
            if parent1_name and parent1_phone:
                add_contact(
                    athlete_id=athlete_id,
                    name=parent1_name,
                    phone=parent1_phone,
                    email=parent1_email or None,
                    relationship='parent',
                    is_primary=True
                )

            # Add parent2 contact if provided
            parent2_name = row.get('parent2_name', '').strip()
            parent2_phone = row.get('parent2_phone', '').strip()
            parent2_email = row.get('parent2_email', '').strip()
            if parent2_name and parent2_phone:
                add_contact(
                    athlete_id=athlete_id,
                    name=parent2_name,
                    phone=parent2_phone,
                    email=parent2_email or None,
                    relationship='parent',
                    is_primary=False
                )

            # Add medical info if provided
            allergies = row.get('allergies', '').strip()
            medical_conditions = row.get('medical_conditions', '').strip()
            if allergies or medical_conditions:
                # Determine severity from allergies text
                severity = None
                if allergies:
                    allergies_lower = allergies.lower()
                    if 'severe' in allergies_lower or 'life-threatening' in allergies_lower:
                        severity = 'severe'
                    elif 'moderate' in allergies_lower:
                        severity = 'moderate'
                    else:
                        severity = 'mild'

                add_medical_info(
                    athlete_id=athlete_id,
                    allergies=allergies or None,
                    allergy_severity=severity,
                    conditions=medical_conditions or None
                )

            results['imported'] += 1
            logger.info(f"Imported athlete: {full_name} ({athlete_number})")

        except Exception as e:
            results['errors'].append(f"Row {row_num}: {str(e)}")
            logger.error(f"CSV import error on row {row_num}: {e}")

    logger.info(f"CSV import complete: {results['imported']} imported, {results['skipped']} skipped, {len(results['errors'])} errors")
    return results

def add_to_team(athlete_id, team_id, jersey_number=None, position=None):
    """Add athlete to team (Field Trainer uses single team per athlete)"""
    with get_db() as conn:
        cursor = conn.cursor()
        # Update athlete's team_id, jersey_number, and position in athletes table
        cursor.execute("""
            UPDATE athletes
            SET team_id = ?,
                jersey_number = COALESCE(?, jersey_number),
                position = COALESCE(?, position),
                updated_at = ?
            WHERE athlete_id = ?
        """, (team_id, jersey_number, position, datetime.now().isoformat(), athlete_id))

        if cursor.rowcount > 0:
            logger.info(f"Added athlete {athlete_id} to team {team_id}")
        return cursor.rowcount > 0

def remove_from_team(athlete_id, team_id):
    """Remove athlete from team (Field Trainer: set team_id to empty)"""
    with get_db() as conn:
        cursor = conn.cursor()
        # Clear the athlete's team_id if it matches the specified team
        cursor.execute("""
            UPDATE athletes
            SET team_id = '',
                updated_at = ?
            WHERE athlete_id = ? AND team_id = ?
        """, (datetime.now().isoformat(), athlete_id, team_id))

        if cursor.rowcount > 0:
            logger.info(f"Removed athlete {athlete_id} from team {team_id}")
        return cursor.rowcount > 0

def export_all_athletes_csv():
    """Export all athletes as CSV (Field Trainer schema)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.athlete_number, a.name, a.birthdate, a.age, a.gender,
                a.jersey_number, a.position,
                (SELECT name FROM athlete_contacts WHERE athlete_id = a.athlete_id AND is_primary = 1 LIMIT 1) as primary_contact,
                (SELECT phone FROM athlete_contacts WHERE athlete_id = a.athlete_id AND is_primary = 1 LIMIT 1) as primary_phone,
                (SELECT email FROM athlete_contacts WHERE athlete_id = a.athlete_id AND is_primary = 1 LIMIT 1) as primary_email,
                am.allergies, am.allergy_severity, am.medical_conditions,
                t.name as team_name
            FROM athletes a
            LEFT JOIN athlete_medical am ON a.athlete_id = am.athlete_id
            LEFT JOIN teams t ON a.team_id = t.team_id
            ORDER BY a.name
        """)

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Athlete Number', 'Name', 'Birthdate', 'Age', 'Gender',
            'Jersey Number', 'Position', 'Team',
            'Primary Contact', 'Phone', 'Email',
            'Allergies', 'Allergy Severity', 'Medical Conditions'
        ])

        # Data
        for row in cursor.fetchall():
            athlete = dict(row)
            writer.writerow([
                athlete['athlete_number'] or '',
                athlete['name'] or '',
                athlete['birthdate'] or '',
                athlete['age'] or '',
                athlete['gender'] or '',
                athlete['jersey_number'] or '',
                athlete['position'] or '',
                athlete['team_name'] or '',
                athlete['primary_contact'] or '',
                athlete['primary_phone'] or '',
                athlete['primary_email'] or '',
                athlete['allergies'] or '',
                athlete['allergy_severity'] or '',
                athlete['medical_conditions'] or ''
            ])

        return output.getvalue()

def export_team_roster_csv(team_id):
    """Export team roster as CSV (Field Trainer schema)"""
    with get_db() as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT
                a.name, a.birthdate, a.age, a.gender,
                a.jersey_number, a.position,
                (SELECT name FROM athlete_contacts WHERE athlete_id = a.athlete_id AND is_primary = 1 LIMIT 1) as primary_contact,
                (SELECT phone FROM athlete_contacts WHERE athlete_id = a.athlete_id AND is_primary = 1 LIMIT 1) as primary_phone,
                (SELECT email FROM athlete_contacts WHERE athlete_id = a.athlete_id AND is_primary = 1 LIMIT 1) as primary_email,
                am.allergies, am.medical_conditions
            FROM athletes a
            LEFT JOIN athlete_medical am ON a.athlete_id = am.athlete_id
            WHERE a.team_id = ?
            ORDER BY a.name
        """, (team_id,))

        # Create CSV
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        writer.writerow([
            'Name', 'Birthdate', 'Age', 'Gender',
            'Jersey', 'Position', 'Primary Contact', 'Phone', 'Email',
            'Allergies', 'Medical Conditions'
        ])

        # Data
        for row in cursor.fetchall():
            athlete = dict(row)
            writer.writerow([
                athlete['name'] or '',
                athlete['birthdate'] or '',
                athlete['age'] or '',
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
