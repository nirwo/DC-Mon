from datetime import datetime
import json
from flask import Blueprint, render_template, jsonify, request, current_app
from app.models import db, Team, Application, ApplicationInstance
from sqlalchemy import desc
import csv
import requests

main = Blueprint('main', __name__)

@main.route('/')
def index():
    applications = Application.query.all()
    teams = Team.query.all()
    return render_template('applications.html', applications=applications, teams=teams)

@main.route('/teams')
def teams():
    teams = Team.query.all()
    return render_template('teams.html', teams=teams)

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
            instance.details = 'Status check initiated'
            instance.last_checked = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Status check initiated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/check_status/<int:instance_id>')
def check_status(instance_id):
    try:
        instance = ApplicationInstance.query.get_or_404(instance_id)
        instance.status = 'checking'
        instance.details = 'Status check initiated'
        instance.last_checked = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'status': 'success', 'message': 'Status check initiated'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/delete_instance/<int:instance_id>', methods=['POST'])
def delete_instance(instance_id):
    try:
        instance = ApplicationInstance.query.get_or_404(instance_id)
        app_id = instance.application_id
        db.session.delete(instance)
        
        # Check if this was the last instance
        remaining_instances = ApplicationInstance.query.filter_by(application_id=app_id).count()
        if remaining_instances == 0:
            # If no instances left, delete the application too
            app = Application.query.get(app_id)
            if app:
                db.session.delete(app)
        
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/delete_application/<int:app_id>', methods=['POST'])
def delete_application(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        # Delete all instances first
        ApplicationInstance.query.filter_by(application_id=app_id).delete()
        # Then delete the application
        db.session.delete(app)
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/update_instance_url/<int:instance_id>', methods=['POST'])
def update_instance_url(instance_id):
    try:
        instance = ApplicationInstance.query.get_or_404(instance_id)
        data = request.get_json()
        instance.webui_url = data.get('url', '')
        db.session.commit()
        return jsonify({
            'status': 'success',
            'message': 'URL updated successfully',
            'instance': {
                'id': instance.id,
                'url': instance.webui_url,
                'host': instance.host,
                'application_id': instance.application_id
            }
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/update_system_info', methods=['POST'])
def update_system():
    try:
        data = request.get_json()
        system_id = data.get('id')
        new_name = data.get('name')
        new_team = data.get('team')
        
        instance = ApplicationInstance.query.get_or_404(system_id)
        instance.host = new_name
        
        # Update team if it exists, create if it doesn't
        team = Team.query.filter_by(name=new_team).first()
        if not team:
            team = Team(name=new_team)
            db.session.add(team)
        
        application = instance.application
        application.team_id = team.id
        
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/get_all_systems')
def get_all_systems():
    try:
        # Get all instances with their application and team info
        instances = db.session.query(
            ApplicationInstance, 
            Application.name.label('app_name'),
            Team.name.label('team_name')
        ).join(
            Application, ApplicationInstance.application_id == Application.id
        ).join(
            Team, Application.team_id == Team.id
        ).all()
        
        # Format the response
        systems = [{
            'id': instance.ApplicationInstance.id,
            'name': instance.ApplicationInstance.host,
            'team': instance.team_name,
            'application_id': instance.ApplicationInstance.application_id
        } for instance in instances]
        
        return jsonify({
            'status': 'success',
            'systems': systems
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/update_application', methods=['POST'])
def update_application():
    try:
        data = request.get_json()
        app_id = data.get('id')
        new_name = data.get('name')
        new_team = data.get('team')
        new_dependencies = data.get('dependencies', [])
        instances = data.get('instances', [])
        
        # Get application
        application = Application.query.get_or_404(app_id)
        
        # Update team if it exists, create if it doesn't
        team = Team.query.filter_by(name=new_team).first()
        if not team:
            team = Team(name=new_team)
            db.session.add(team)
            db.session.flush()
        
        # Update application
        application.name = new_name
        application.team_id = team.id
        application.dependencies = new_dependencies
        
        # Update instances if provided
        if instances:
            # Delete removed instances
            current_instance_ids = [i.get('id') for i in instances if i.get('id')]
            ApplicationInstance.query.filter(
                ApplicationInstance.application_id == app_id,
                ~ApplicationInstance.id.in_(current_instance_ids) if current_instance_ids else True
            ).delete(synchronize_session=False)
            
            # Update/create instances
            for instance_data in instances:
                instance_id = instance_data.get('id')
                if instance_id:
                    instance = ApplicationInstance.query.get(instance_id)
                    if instance:
                        instance.host = instance_data.get('host')
                        instance.port = instance_data.get('port')
                        instance.webui_url = instance_data.get('webui_url')
                        instance.db_host = instance_data.get('db_host')
                else:
                    instance = ApplicationInstance(
                        application_id=app_id,
                        host=instance_data.get('host'),
                        port=instance_data.get('port'),
                        webui_url=instance_data.get('webui_url'),
                        db_host=instance_data.get('db_host')
                    )
                    db.session.add(instance)
        
        db.session.commit()
        return jsonify({'status': 'success'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 500
