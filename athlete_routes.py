"""
Flask routes for athlete management
Simplified for Raspberry Pi deployment
"""

from flask import Blueprint, jsonify, request, send_file, render_template
from werkzeug.utils import secure_filename
import io
import os
import logging

# Import athlete helpers
import sys
sys.path.insert(0, '/opt')
from athlete_helpers import *

athlete_bp = Blueprint('athletes', __name__)
logger = logging.getLogger(__name__)

# List/Search athletes
@athlete_bp.route('/api/athletes')
def list_athletes():
    try:
        team_id = request.args.get('team_id')
        active_only = request.args.get('active', 'true').lower() == 'true'

        athletes = get_all_athletes(active_only=active_only, team_id=team_id)
        return jsonify({'success': True, 'athletes': athletes})
    except Exception as e:
        logger.error(f"Error listing athletes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Get single athlete
@athlete_bp.route('/api/athletes/<int:athlete_id>')
def get_athlete_details(athlete_id):
    try:
        athlete = get_athlete(athlete_id)
        if not athlete:
            return jsonify({'success': False, 'error': 'Athlete not found'}), 404

        # Get contacts
        with get_db() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM athlete_contacts WHERE athlete_id = ? ORDER BY is_primary DESC",
                (athlete_id,)
            )
            athlete['contacts'] = [dict(row) for row in cursor.fetchall()]

            # Get medical info
            cursor.execute("SELECT * FROM athlete_medical WHERE athlete_id = ?", (athlete_id,))
            medical = cursor.fetchone()
            athlete['medical'] = dict(medical) if medical else {}

            # Get teams
            cursor.execute("""
                SELECT t.team_id, t.name, ta.jersey_number, ta.position
                FROM teams t
                JOIN team_athletes ta ON t.team_id = ta.team_id
                WHERE ta.athlete_id = ?
            """, (athlete_id,))
            athlete['team_list'] = [dict(row) for row in cursor.fetchall()]

        return jsonify({'success': True, 'athlete': athlete})
    except Exception as e:
        logger.error(f"Error getting athlete {athlete_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Create athlete
@athlete_bp.route('/api/athletes', methods=['POST'])
def create_athlete_route():
    try:
        data = request.json

        # Validate required fields
        if not data.get('first_name') or not data.get('last_name') or not data.get('birthdate'):
            return jsonify({'success': False, 'error': 'Missing required fields'}), 400

        # Create athlete
        athlete_id, athlete_number = create_athlete(
            first_name=data['first_name'],
            last_name=data['last_name'],
            birthdate=data['birthdate'],
            gender=data.get('gender'),
            display_name=data.get('display_name'),
            consent_given_by=data.get('consent_given_by')
        )

        # Add contacts if provided
        for contact in data.get('contacts', []):
            if contact.get('name') and contact.get('phone'):
                add_contact(
                    athlete_id=athlete_id,
                    name=contact['name'],
                    phone=contact['phone'],
                    email=contact.get('email'),
                    relationship=contact.get('relationship', 'parent'),
                    is_primary=contact.get('is_primary', False),
                    can_pickup=contact.get('can_pickup', True)
                )

        # Add medical info if provided
        medical = data.get('medical', {})
        if medical and (medical.get('allergies') or medical.get('medical_conditions')):
            add_medical_info(
                athlete_id=athlete_id,
                allergies=medical.get('allergies'),
                allergy_severity=medical.get('allergy_severity'),
                conditions=medical.get('medical_conditions'),
                physician_name=medical.get('physician_name'),
                physician_phone=medical.get('physician_phone')
            )

        # Add to teams if specified
        for team_id in data.get('team_ids', []):
            add_to_team(athlete_id, team_id)

        return jsonify({
            'success': True,
            'athlete_id': athlete_id,
            'athlete_number': athlete_number
        }), 201

    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error(f"Error creating athlete: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Update athlete
@athlete_bp.route('/api/athletes/<int:athlete_id>', methods=['PUT', 'PATCH'])
def update_athlete_route(athlete_id):
    try:
        data = request.json

        # Update basic info
        success = update_athlete(athlete_id, **data)

        if not success:
            return jsonify({'success': False, 'error': 'Athlete not found'}), 404

        # Update medical if provided
        if 'medical' in data:
            medical = data['medical']
            if medical:
                add_medical_info(
                    athlete_id=athlete_id,
                    allergies=medical.get('allergies'),
                    allergy_severity=medical.get('allergy_severity'),
                    conditions=medical.get('medical_conditions'),
                    physician_name=medical.get('physician_name'),
                    physician_phone=medical.get('physician_phone')
                )

        # Update contacts if provided
        if 'contacts' in data:
            contacts = data['contacts']

            # Get existing contact IDs
            with get_db() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT id FROM athlete_contacts WHERE athlete_id = ?", (athlete_id,))
                existing_ids = [row[0] for row in cursor.fetchall()]

                # Track which contacts are in the update
                updated_ids = []

                # Process each contact
                for contact in contacts:
                    contact_id = contact.get('id')

                    # Convert empty string to None and ensure it's an integer if present
                    if contact_id == '' or contact_id == 'null' or contact_id is None:
                        contact_id = None
                    else:
                        try:
                            contact_id = int(contact_id)
                        except (ValueError, TypeError):
                            contact_id = None

                    if contact_id and contact_id in existing_ids:
                        # Update existing contact
                        cursor.execute("""
                            UPDATE athlete_contacts
                            SET name = ?, phone = ?, email = ?, relationship = ?, is_primary = ?
                            WHERE id = ? AND athlete_id = ?
                        """, (
                            contact['name'],
                            contact['phone'],
                            contact.get('email'),
                            contact.get('relationship', 'parent'),
                            contact.get('is_primary', False),
                            contact_id,
                            athlete_id
                        ))
                        updated_ids.append(contact_id)
                        logger.info(f"Updated contact {contact_id} for athlete {athlete_id}")
                    else:
                        # Add new contact
                        cursor.execute("""
                            INSERT INTO athlete_contacts
                            (athlete_id, name, phone, email, relationship, is_primary, can_pickup, emergency_contact)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            athlete_id,
                            contact['name'],
                            contact['phone'],
                            contact.get('email'),
                            contact.get('relationship', 'parent'),
                            contact.get('is_primary', False),
                            True,
                            True
                        ))
                        new_id = cursor.lastrowid
                        updated_ids.append(new_id)
                        logger.info(f"Added new contact {new_id} for athlete {athlete_id}")

                # Delete contacts that weren't included in the update
                for existing_id in existing_ids:
                    if existing_id not in updated_ids:
                        cursor.execute("DELETE FROM athlete_contacts WHERE id = ? AND athlete_id = ?",
                                     (existing_id, athlete_id))
                        logger.info(f"Deleted contact {existing_id} for athlete {athlete_id}")

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error updating athlete {athlete_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Delete athlete (soft delete)
@athlete_bp.route('/api/athletes/<int:athlete_id>', methods=['DELETE'])
def delete_athlete_route(athlete_id):
    try:
        success = delete_athlete(athlete_id, soft=True)
        if not success:
            return jsonify({'success': False, 'error': 'Athlete not found'}), 404

        return jsonify({'success': True})

    except Exception as e:
        logger.error(f"Error deleting athlete {athlete_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Upload photo
@athlete_bp.route('/api/athletes/<int:athlete_id>/photo', methods=['POST'])
def upload_photo(athlete_id):
    try:
        if 'photo' in request.files:
            # File upload
            file = request.files['photo']
            if file.filename == '':
                return jsonify({'success': False, 'error': 'No file selected'}), 400

            filename = save_athlete_photo(athlete_id, file, source='upload')
            return jsonify({'success': True, 'filename': filename})

        elif request.json and 'photo_data' in request.json:
            # Camera capture (base64)
            filename = save_athlete_photo(athlete_id, request.json['photo_data'], source='camera')
            return jsonify({'success': True, 'filename': filename})

        else:
            return jsonify({'success': False, 'error': 'No photo provided'}), 400

    except Exception as e:
        logger.error(f"Error uploading photo for athlete {athlete_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Get photo
@athlete_bp.route('/api/athletes/<int:athlete_id>/photo')
def get_photo(athlete_id):
    try:
        athlete = get_athlete(athlete_id)
        if athlete and athlete.get('photo_filename'):
            filepath = os.path.join(PHOTO_DIR, athlete['photo_filename'])
            if os.path.exists(filepath):
                return send_file(filepath, mimetype='image/jpeg')

        # Return default avatar
        default_avatar = '/opt/static/default-avatar.png'
        if os.path.exists(default_avatar):
            return send_file(default_avatar, mimetype='image/png')
        else:
            # Return empty 1x1 transparent PNG
            return send_file(io.BytesIO(b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'), mimetype='image/png')

    except Exception as e:
        logger.error(f"Error getting photo for athlete {athlete_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Import CSV
@athlete_bp.route('/api/athletes/import', methods=['POST'])
def import_csv():
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': 'No file provided'}), 400

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': 'No file selected'}), 400

        team_id = request.form.get('team_id')
        skip_duplicates = request.form.get('skip_duplicates', 'true').lower() == 'true'

        # Read file
        file_wrapper = io.TextIOWrapper(file.stream, encoding='utf-8')
        results = import_athletes_csv(file_wrapper, team_id=team_id, skip_duplicates=skip_duplicates)

        return jsonify({'success': True, **results})

    except Exception as e:
        logger.error(f"Error importing CSV: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Export all athletes
@athlete_bp.route('/api/athletes/export')
def export_all_athletes():
    try:
        csv_data = export_all_athletes_csv()

        return send_file(
            io.BytesIO(csv_data.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'all_athletes_{datetime.now().strftime("%Y%m%d")}.csv'
        )

    except Exception as e:
        logger.error(f"Error exporting all athletes: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Export team roster
@athlete_bp.route('/api/teams/<team_id>/roster/export')
def export_roster(team_id):
    try:
        csv_data = export_team_roster_csv(team_id)

        return send_file(
            io.BytesIO(csv_data.encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'roster_team_{team_id}_{datetime.now().strftime("%Y%m%d")}.csv'
        )

    except Exception as e:
        logger.error(f"Error exporting roster for team {team_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Add athlete to team
@athlete_bp.route('/api/teams/<team_id>/athletes', methods=['POST'])
def add_athlete_to_team_route(team_id):
    try:
        data = request.json
        athlete_id = data.get('athlete_id')

        if not athlete_id:
            return jsonify({'success': False, 'error': 'athlete_id required'}), 400

        success = add_to_team(
            athlete_id=athlete_id,
            team_id=team_id,
            jersey_number=data.get('jersey_number'),
            position=data.get('position')
        )

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Failed to add athlete to team'}), 500

    except Exception as e:
        logger.error(f"Error adding athlete to team {team_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Remove athlete from team
@athlete_bp.route('/api/teams/<team_id>/athletes/<int:athlete_id>', methods=['DELETE'])
def remove_athlete_from_team_route(team_id, athlete_id):
    try:
        success = remove_from_team(athlete_id, team_id)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Athlete not on this team'}), 404

    except Exception as e:
        logger.error(f"Error removing athlete {athlete_id} from team {team_id}: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

# Render athletes page
@athlete_bp.route('/athletes')
def athletes_page():
    return render_template('athletes.html')

# Render athlete detail page
@athlete_bp.route('/athlete/<int:athlete_id>')
def athlete_detail_page(athlete_id):
    return render_template('athlete_detail.html', athlete_id=athlete_id)
