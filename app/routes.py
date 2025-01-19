from datetime import datetime
import json
from flask import Blueprint, render_template, jsonify, request
from app.models import db, Team, Application, ApplicationInstance
from sqlalchemy import desc
import csv

main = Blueprint('main', __name__)

@main.route('/')
def index():
    applications = Application.query.all()
    return render_template('index.html', applications=applications)

@main.route('/systems')
def systems():
    instances = ApplicationInstance.query.join(Application).join(Team).order_by(Team.name, Application.name).all()
    return render_template('systems.html', instances=instances)

@main.route('/import_data', methods=['POST'])
def import_data():
    try:
        if 'file' not in request.files:
            return jsonify({'status': 'error', 'message': 'No file uploaded'}), 400
            
        file = request.files['file']
        if not file.filename:
            return jsonify({'status': 'error', 'message': 'No file selected'}), 400
            
        if file.filename.endswith('.csv'):
            # Handle CSV import
            content = file.read().decode('utf-8')
            reader = csv.DictReader(content.splitlines())
            
            # Group by team and application
            data = {'teams': [], 'applications': []}
            app_instances = {}
            
            for row in reader:
                team_name = row['team'].strip()
                app_name = row['name'].strip()
                key = f"{team_name}:{app_name}"
                
                if team_name not in [t['name'] for t in data['teams']]:
                    data['teams'].append({'name': team_name})
                
                if key not in app_instances:
                    app_instances[key] = {
                        'name': app_name,
                        'team': team_name,
                        'instances': []
                    }
                
                app_instances[key]['instances'].append({
                    'host': row['host'].strip(),
                    'port': int(row['port']) if 'port' in row and row['port'] else None,
                    'webui_url': row['webui_url'].strip() if 'webui_url' in row else None,
                    'db_host': row['db_host'].strip() if 'db_host' in row else None
                })
            
            data['applications'] = list(app_instances.values())
            
        elif file.filename.endswith('.json'):
            # Handle JSON import
            content = file.read().decode('utf-8')
            data = json.loads(content)
            
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid file format. Please upload a CSV or JSON file.'
            }), 400
        
        # First create teams
        for team_data in data.get('teams', []):
            if not isinstance(team_data, dict) or 'name' not in team_data:
                continue
                
            team = Team.query.filter_by(name=team_data['name']).first()
            if not team:
                team = Team(name=team_data['name'])
                db.session.add(team)
        db.session.commit()
        
        # Then create applications and instances
        for app_data in data.get('applications', []):
            if not isinstance(app_data, dict) or 'name' not in app_data or 'team' not in app_data:
                continue
                
            team = Team.query.filter_by(name=app_data['team']).first()
            if not team:
                continue
                
            app = Application.query.filter_by(name=app_data['name'], team_id=team.id).first()
            if not app:
                app = Application(
                    name=app_data['name'],
                    team_id=team.id,
                    shutdown_order=app_data.get('shutdown_order')
                )
                db.session.add(app)
            
            for instance_data in app_data.get('instances', []):
                if not isinstance(instance_data, dict) or 'host' not in instance_data:
                    continue
                    
                instance = ApplicationInstance.query.filter_by(
                    application_id=app.id,
                    host=instance_data['host']
                ).first()
                
                if not instance:
                    instance = ApplicationInstance(
                        application_id=app.id,
                        host=instance_data['host'],
                        port=instance_data.get('port'),
                        webui_url=instance_data.get('webui_url'),
                        db_host=instance_data.get('db_host'),
                        status='unknown'
                    )
                    db.session.add(instance)
                else:
                    instance.port = instance_data.get('port', instance.port)
                    instance.webui_url = instance_data.get('webui_url', instance.webui_url)
                    instance.db_host = instance_data.get('db_host', instance.db_host)
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'Data imported successfully'})
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Import failed: {str(e)}'
        }), 500

@main.route('/check_all_status')
def check_all_status():
    try:
        instances = ApplicationInstance.query.all()
        for instance in instances:
            instance.status = 'checking'
            instance.details = json.dumps(['Status check initiated'])
            instance.last_checked = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Status check initiated'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/check_status/<int:instance_id>')
def check_status(instance_id):
    try:
        instance = ApplicationInstance.query.get_or_404(instance_id)
        instance.status = 'checking'
        instance.details = json.dumps(['Status check initiated'])
        instance.last_checked = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Status check initiated'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
