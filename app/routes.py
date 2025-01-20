from flask import Blueprint, render_template, jsonify, request, current_app
from app.models import Team, Application, System
import logging
import csv

logger = logging.getLogger(__name__)
main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/api/teams', methods=['GET'])
def get_teams():
    try:
        teams = Team.objects.all()
        return jsonify([team.to_dict() for team in teams])
    except Exception as e:
        logger.error(f"Error getting teams: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications', methods=['GET'])
def get_applications():
    try:
        applications = Application.objects.all()
        return jsonify([app.to_dict() for app in applications])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/systems', methods=['GET'])
def get_systems():
    try:
        systems = System.objects.all()
        return jsonify([system.to_dict() for system in systems])
    except Exception as e:
        logger.error(f"Error getting systems: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications/<app_id>/systems', methods=['GET'])
def get_application_systems(app_id):
    try:
        app = Application.objects.get(id=app_id)
        return jsonify([system.to_dict() for system in app.systems])
    except Application.DoesNotExist:
        return jsonify({"error": "Application not found"}), 404

@main.route('/api/applications/<app_id>/test', methods=['POST'])
def test_application(app_id):
    try:
        app = Application.objects.get(id=app_id)
        for system in app.systems:
            system.status = "running"
            system.save()
        return jsonify({"message": "Test started successfully"})
    except Application.DoesNotExist:
        return jsonify({"error": "Application not found"}), 404

@main.route('/api/applications/<app_id>/state', methods=['PUT'])
def update_app_state(app_id):
    try:
        data = request.get_json()
        app = Application.objects.get(id=app_id)
        app.state = data.get('state', 'notStarted')
        app.save()
        return jsonify({"message": "State updated successfully"})
    except Application.DoesNotExist:
        return jsonify({"error": "Application not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/import', methods=['POST'])
def import_data():
    try:
        if 'file' not in request.files:
            return jsonify({"error": "No file provided"}), 400
            
        file = request.files['file']
        if not file.filename.endswith('.csv'):
            return jsonify({"error": "Only CSV files are supported"}), 400

        content = file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(content)
        
        for row in reader:
            team_name = row.get('team')
            app_name = row.get('application')
            system_name = row.get('system')
            host = row.get('host')
            port = row.get('port')
            webui_url = row.get('webui_url')
            
            if not all([team_name, app_name, system_name, host]):
                continue
                
            # Create or get team
            team = Team.objects(name=team_name).first()
            if not team:
                team = Team(name=team_name).save()
                
            # Create or get application
            app = Application.objects(name=app_name, team=team).first()
            if not app:
                app = Application(name=app_name, team=team).save()
                
            # Create system if it doesn't exist
            if not System.objects(name=system_name, application=app).first():
                system = System(
                    name=system_name,
                    application=app,
                    host=host,
                    port=int(port) if port else 80,
                    webui_url=webui_url
                ).save()
        
        return jsonify({"message": "Import successful"})
    except Exception as e:
        return jsonify({"error": str(e)}), 500