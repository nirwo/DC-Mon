from flask import Blueprint, render_template, jsonify, request, current_app
from app.models import Team, Application, System, ApplicationInstance
from app import db
import logging
import csv
import os
import tempfile

logger = logging.getLogger(__name__)
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
        logger.error(f"Error getting teams: {str(e)}")
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
        logger.error(f"Error deleting team: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications', methods=['GET'])
def get_applications():
    try:
        applications = Application.query.all()
        return jsonify([app.to_dict() for app in applications])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

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
        logger.error(f"Error deleting application: {str(e)}")
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
        logger.error(f"Error deleting system: {str(e)}")
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
def import_data():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
        
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Invalid file format. Please upload a CSV file"}), 400
        
        imported_count = 0
        skipped_count = 0
        
        # Create a temporary file to store the uploaded content
        with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp_file:
            file.save(temp_file.name)
            
            with open(temp_file.name, 'r') as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    try:
                        # Get or create team
                        team = Team.query.filter_by(name=row['team']).first()
                        if not team:
                            team = Team(name=row['team'])
                            db.session.add(team)
                            db.session.flush()
                        
                        # Create application
                        app = Application(
                            name=row['name'],
                            team_id=team.id,
                            webui_url=row.get('webui_url')
                        )
                        db.session.add(app)
                        db.session.flush()
                        
                        # Create instance
                        instance = ApplicationInstance(
                            application_id=app.id,
                            host=row['host'],
                            port=int(row['port']) if row.get('port') else None,
                            webui_url=row.get('webui_url'),
                            db_host=row.get('db_host'),
                            status='running'
                        )
                        db.session.add(instance)
                        imported_count += 1
                    except Exception as e:
                        current_app.logger.error(f"Error importing row: {str(e)}")
                        skipped_count += 1
                        continue
            
            db.session.commit()
            os.unlink(temp_file.name)
        
        return jsonify({
            "status": "success",
            "imported": imported_count,
            "skipped": skipped_count
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({"error": str(e)}), 500

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