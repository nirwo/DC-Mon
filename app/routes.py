from flask import Blueprint, render_template, request, jsonify
from app.models import db, Team, Application, ApplicationDependency
from app.utils import get_application_status, get_shutdown_sequence
import csv
from io import StringIO
from datetime import datetime

main = Blueprint('main', __name__)

@main.route('/')
def index():
    teams = Team.query.all()
    applications = Application.query.all()
    return render_template('index.html', teams=teams, applications=applications)

@main.route('/teams')
def teams():
    teams = Team.query.all()
    return render_template('teams.html', teams=teams)

@main.route('/applications')
def applications():
    applications = Application.query.order_by(Application.shutdown_order.desc()).all()
    teams = Team.query.all()
    return render_template('applications.html', applications=applications, teams=teams)

@main.route('/api/teams', methods=['POST'])
def add_team():
    data = request.get_json()
    
    if not data or 'name' not in data:
        return jsonify({'error': 'Team name is required'}), 400
    
    team = Team(name=data['name'])
    try:
        db.session.add(team)
        db.session.commit()
        return jsonify({'message': 'Team added successfully', 'id': team.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@main.route('/api/applications', methods=['POST'])
def add_application():
    data = request.get_json()
    required_fields = ['name', 'team_id', 'host', 'port', 'shutdown_order']
    
    if not data or not all(field in data for field in required_fields):
        return jsonify({'error': 'Missing required fields'}), 400
    
    app = Application(
        name=data['name'],
        team_id=data['team_id'],
        host=data['host'],
        port=data['port'],
        webui_url=data.get('webui_url'),
        db_host=data.get('db_host'),
        shutdown_order=data['shutdown_order']
    )
    
    try:
        db.session.add(app)
        db.session.commit()
        return jsonify({'message': 'Application added successfully', 'id': app.id})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@main.route('/import_csv', methods=['POST'])
def import_csv():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
    
    content = file.read().decode('utf-8')
    csv_file = StringIO(content)
    csv_reader = csv.DictReader(csv_file)
    
    try:
        for row in csv_reader:
            team = Team.query.filter_by(name=row['team_name']).first()
            if not team:
                team = Team(name=row['team_name'])
                db.session.add(team)
                db.session.flush()
            
            app = Application(
                name=row['app_name'],
                team_id=team.id,
                host=row['host'],
                port=int(row['port']) if row['port'] else None,
                webui_url=row['webui_url'],
                db_host=row['db_host'],
                shutdown_order=int(row['shutdown_order'])
            )
            db.session.add(app)
            
            # Handle dependencies if present
            if 'dependencies' in row and row['dependencies']:
                for dep in row['dependencies'].split(';'):
                    if not dep:
                        continue
                    host, port = dep.split(':')
                    dep_app = Application.query.filter_by(host=host, port=port).first()
                    if dep_app:
                        dependency = ApplicationDependency(
                            application_id=app.id,
                            dependency_id=dep_app.id,
                            dependency_type='shutdown_before'
                        )
                        db.session.add(dependency)
        
        db.session.commit()
        return jsonify({'message': 'Import successful'}), 200
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

@main.route('/check_status/<int:app_id>')
def check_status(app_id):
    app = Application.query.get_or_404(app_id)
    status = get_application_status(app)
    
    app.status = 'running' if status['is_running'] else 'stopped'
    app.last_checked = status['last_checked']
    db.session.commit()
    
    return jsonify({
        'status': app.status,
        'details': status['details'],
        'last_checked': app.last_checked.isoformat()
    })

@main.route('/check_all_status')
def check_all_status():
    apps = Application.query.all()
    results = {}
    
    for app in apps:
        status = get_application_status(app)
        app.status = 'running' if status['is_running'] else 'stopped'
        app.last_checked = status['last_checked']
        results[app.id] = {
            'name': app.name,
            'status': app.status,
            'details': status['details'],
            'last_checked': app.last_checked.isoformat()
        }
    
    db.session.commit()
    return jsonify(results)

@main.route('/shutdown_sequence/<int:app_id>')
def get_app_shutdown_sequence(app_id):
    app = Application.query.get_or_404(app_id)
    sequence = get_shutdown_sequence(app)
    
    return jsonify({
        'sequence': [{
            'id': app.id,
            'name': app.name,
            'team': app.team.name,
            'status': app.status,
            'shutdown_order': app.shutdown_order
        } for app in sequence]
    })

@main.route('/shutdown/<int:app_id>', methods=['POST'])
def shutdown_application(app_id):
    app = Application.query.get_or_404(app_id)
    sequence = get_shutdown_sequence(app)
    
    try:
        for app in sequence:
            app.status = 'stopped'
        db.session.commit()
        return jsonify({'message': 'Shutdown sequence completed successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400
