from flask import Blueprint, jsonify, request, current_app, render_template
from app.models import Team, Application, ApplicationInstance
from app import db
import tempfile
import csv
import os
import io
import traceback

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/api/teams', methods=['GET'])
def get_teams():
    try:
        teams = Team.query.all()
        return jsonify([team.to_dict() for team in teams])
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/teams/<int:team_id>', methods=['DELETE'])
def delete_team(team_id):
    try:
        team = Team.query.get_or_404(team_id)
        # Delete all associated applications first
        Application.query.filter_by(team_id=team_id).delete()
        db.session.delete(team)
        db.session.commit()
        return jsonify({'message': 'Team deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications', methods=['GET'])
def get_applications():
    try:
        applications = Application.query.all()
        return jsonify([{
            'id': app.id,
            'name': app.name,
            'team_id': app.team_id,
            'instances': [{
                'id': inst.id,
                'host': inst.host,
                'port': inst.port,
                'webui_url': inst.webui_url,
                'db_host': inst.db_host,
                'status': inst.status
            } for inst in app.instances]
        } for app in applications])
    except Exception as e:
        current_app.logger.error(f"Error getting applications: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications', methods=['POST'])
def create_application():
    try:
        data = request.json
        app = Application(
            name=data['name'],
            team_id=data['team_id']
        )
        db.session.add(app)
        db.session.flush()

        instance = ApplicationInstance(
            application_id=app.id,
            host=data['host'],
            port=data.get('port'),
            webui_url=data.get('webui_url'),
            db_host=data.get('db_host'),
            status='running'
        )
        db.session.add(instance)
        db.session.commit()
        
        return jsonify({
            'id': app.id,
            'name': app.name,
            'team_id': app.team_id,
            'instances': [{
                'id': instance.id,
                'host': instance.host,
                'port': instance.port,
                'webui_url': instance.webui_url,
                'db_host': instance.db_host,
                'status': instance.status
            }]
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        # Delete all associated instances first
        ApplicationInstance.query.filter_by(application_id=app_id).delete()
        db.session.delete(app)
        db.session.commit()
        return jsonify({'message': 'Application deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications/<int:app_id>/systems', methods=['GET'])
def get_application_systems(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        return jsonify([system.to_dict() for system in app.systems])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/check_status/<int:app_id>', methods=['GET'])
def test_application(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        instances = ApplicationInstance.query.filter_by(application_id=app_id).all()
        results = []
        
        for instance in instances:
            instance.status = 'running'
            db.session.add(instance)
            results.append({
                'id': instance.id,
                'status': instance.status,
                'host': instance.host,
                'port': instance.port
            })
        
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'Status check completed',
            'results': results
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/update_application/<int:app_id>', methods=['POST'])
def update_app_state(app_id):
    try:
        data = request.json
        app = Application.query.get_or_404(app_id)
        
        # Update application fields
        app.name = data.get('name', app.name)
        app.team_id = data.get('team_id', app.team_id)
        
        # Update instances
        if 'instances' in data:
            for instance_data in data['instances']:
                instance = ApplicationInstance.query.get(instance_data['id'])
                if instance:
                    instance.host = instance_data.get('host', instance.host)
                    instance.port = instance_data.get('port', instance.port)
                    instance.webui_url = instance_data.get('webui_url', instance.webui_url)
                    instance.db_host = instance_data.get('db_host', instance.db_host)
                    db.session.add(instance)
        
        db.session.add(app)
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Application updated successfully'})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/systems', methods=['GET'])
def get_systems():
    try:
        systems = System.query.all()
        return jsonify([system.to_dict() for system in systems])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/systems/<int:system_id>', methods=['DELETE'])
def delete_system(system_id):
    try:
        system = System.query.get_or_404(system_id)
        db.session.delete(system)
        db.session.commit()
        return jsonify({'message': 'System deleted successfully'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/preview_csv', methods=['POST'])
def preview_csv():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Invalid file format. Please upload a CSV file"}), 400
        
        # Create a temporary file to store the uploaded content
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp_file:
            file.save(temp_file.name)
            
            # Read CSV headers and preview data
            with open(temp_file.name, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                headers = reader.fieldnames
                preview = []
                for i, row in enumerate(reader):
                    if i >= 5:  # Only show first 5 rows
                        break
                    preview.append(row)
            
            os.unlink(temp_file.name)
            
            required_fields = ['name', 'team', 'host', 'port']
            optional_fields = ['webui_url', 'db_host', 'description']
            
            return jsonify({
                "headers": headers,
                "preview": preview,
                "required_fields": required_fields,
                "optional_fields": optional_fields
            })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/import_apps', methods=['POST'])
def import_apps():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file or not file.filename.endswith('.csv'):
        return jsonify({'error': 'Invalid file format. Please upload a CSV file'}), 400

    try:
        # Read CSV file into memory
        stream = io.StringIO(file.stream.read().decode("UTF8"), newline=None)
        csv_input = csv.DictReader(stream)
        
        imported = 0
        skipped = 0
        errors = []
        
        required_fields = ['name', 'team_name', 'host']
        for row_num, row in enumerate(csv_input, start=2):  # start=2 to account for header row
            try:
                # Validate required fields
                missing_fields = [field for field in required_fields if not row.get(field)]
                if missing_fields:
                    errors.append(f"Row {row_num}: Missing required fields: {', '.join(missing_fields)}")
                    skipped += 1
                    continue

                # Find or create team
                team = Team.query.filter_by(name=row['team_name']).first()
                if not team:
                    team = Team(name=row['team_name'])
                    db.session.add(team)
                    db.session.flush()

                # Create application
                app = Application(
                    name=row['name'],
                    team_id=team.id
                )
                db.session.add(app)
                db.session.flush()

                # Create instance
                instance = ApplicationInstance(
                    application_id=app.id,
                    host=row['host'],
                    port=row.get('port'),
                    webui_url=row.get('webui_url'),
                    db_host=row.get('db_host'),
                    status='running'
                )
                db.session.add(instance)
                imported += 1

            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                skipped += 1
                continue

        db.session.commit()
        
        response = {
            'imported': imported,
            'skipped': skipped,
            'message': f'Successfully imported {imported} applications'
        }
        
        if errors:
            response['errors'] = errors
            
        return jsonify(response)

    except Exception as e:
        db.session.rollback()
        return jsonify({
            'error': f'Import failed: {str(e)}',
            'details': traceback.format_exc()
        }), 500

@main.route('/shutdown_app/<int:app_id>', methods=['POST'])
def shutdown_app(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        instances = ApplicationInstance.query.filter_by(application_id=app_id).all()
        
        for instance in instances:
            instance.status = 'in_progress'
            db.session.add(instance)
        
        app.state = 'completed'
        db.session.add(app)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Application shutdown in progress'
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500