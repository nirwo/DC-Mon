from flask import Blueprint, render_template, request, jsonify, send_file, make_response
from app.models import db, Team, Application, ApplicationDependency
from app.utils import get_application_status, get_shutdown_sequence, check_application_status
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

@main.route('/api/teams/<int:team_id>', methods=['PUT'])
def update_team(team_id):
    team = Team.query.get_or_404(team_id)
    data = request.json
    
    if 'name' not in data:
        return jsonify({'error': 'Name is required'}), 400
        
    # Check if another team with this name exists
    existing_team = Team.query.filter(Team.name == data['name'], Team.id != team_id).first()
    if existing_team:
        return jsonify({'error': 'Team name already exists'}), 400
        
    team.name = data['name']
    db.session.commit()
    return jsonify({'message': 'Team updated successfully'})

@main.route('/api/applications/<int:app_id>', methods=['GET'])
def get_application(app_id):
    app = Application.query.get_or_404(app_id)
    return jsonify({
        'id': app.id,
        'name': app.name,
        'team_id': app.team_id,
        'host': app.host,
        'port': app.port,
        'webui_url': app.webui_url,
        'db_host': app.db_host,
        'shutdown_order': app.shutdown_order
    })

@main.route('/api/applications/<int:app_id>', methods=['PUT'])
def update_application(app_id):
    app = Application.query.get_or_404(app_id)
    data = request.json
    
    if not all(key in data for key in ['name', 'team_id', 'host', 'port', 'shutdown_order']):
        return jsonify({'error': 'Missing required fields'}), 400
        
    # Check if another application with this name exists
    existing_app = Application.query.filter(Application.name == data['name'], Application.id != app_id).first()
    if existing_app:
        return jsonify({'error': 'Application name already exists'}), 400
        
    # Validate team exists
    team = Team.query.get(data['team_id'])
    if not team:
        return jsonify({'error': 'Team not found'}), 404
        
    app.name = data['name']
    app.team_id = data['team_id']
    app.host = data['host']
    app.port = data['port']
    app.webui_url = data.get('webui_url', '')
    app.db_host = data.get('db_host', '')
    app.shutdown_order = data['shutdown_order']
    
    db.session.commit()
    return jsonify({'message': 'Application updated successfully'})

@main.route('/export_template')
def export_template():
    return send_file('../template.csv',
                    mimetype='text/csv',
                    as_attachment=True,
                    download_name='shutdown_manager_template.csv')

@main.route('/export_apps')
def export_apps():
    si = StringIO()
    writer = csv.writer(si)
    writer.writerow(['name', 'team', 'host', 'port', 'webui_url', 'db_host', 'shutdown_order', 'dependencies'])
    
    apps = Application.query.all()
    for app in apps:
        dependencies = ';'.join([dep.dependency.name for dep in app.dependencies])
        writer.writerow([
            app.name,
            app.team.name,
            app.host,
            app.port,
            app.webui_url or '',
            app.db_host or '',
            app.shutdown_order,
            dependencies
        ])
    
    output = make_response(si.getvalue())
    output.headers["Content-Disposition"] = "attachment; filename=applications.csv"
    output.headers["Content-type"] = "text/csv"
    return output

@main.route('/import_apps', methods=['POST'])
def import_apps():
    if 'file' not in request.files:
        return jsonify({'error': 'No file uploaded'}), 400
        
    file = request.files['file']
    if not file or file.filename == '':
        return jsonify({'error': 'No file selected'}), 400
        
    if not file.filename.endswith('.csv'):
        return jsonify({'error': 'File must be a CSV'}), 400
    
    try:
        # Read CSV content
        content = file.read().decode('utf-8')
        csv_data = list(csv.DictReader(StringIO(content)))
        
        # Validate CSV structure
        required_fields = ['name', 'team', 'host', 'port', 'shutdown_order']
        for field in required_fields:
            if field not in csv_data[0]:
                return jsonify({'error': f'Missing required field: {field}'}), 400
        
        # Start transaction
        imported = 0
        skipped = 0
        errors = []
        
        for row in csv_data:
            try:
                # Get or create team
                team = Team.query.filter_by(name=row['team']).first()
                if not team:
                    team = Team(name=row['team'])
                    db.session.add(team)
                    db.session.flush()
                
                # Check if application already exists
                app = Application.query.filter_by(name=row['name']).first()
                if app:
                    skipped += 1
                    continue
                
                # Create new application
                app = Application(
                    name=row['name'],
                    team_id=team.id,
                    host=row['host'],
                    port=int(row['port']) if row['port'] else None,
                    webui_url=row['webui_url'] if row['webui_url'] else None,
                    db_host=row['db_host'] if row['db_host'] else None,
                    shutdown_order=int(row['shutdown_order']) if row['shutdown_order'] else 100
                )
                db.session.add(app)
                db.session.flush()
                
                # Handle dependencies
                if row.get('dependencies'):
                    for dep_name in row['dependencies'].split(';'):
                        if dep_name.strip():
                            dep_app = Application.query.filter_by(name=dep_name.strip()).first()
                            if dep_app:
                                dependency = ApplicationDependency(
                                    application_id=app.id,
                                    dependency_id=dep_app.id
                                )
                                db.session.add(dependency)
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Error importing {row.get('name', 'unknown')}: {str(e)}")
        
        # Commit transaction if no errors
        if not errors:
            db.session.commit()
            return jsonify({
                'message': f'Successfully imported {imported} applications ({skipped} skipped)',
                'imported': imported,
                'skipped': skipped
            })
        else:
            db.session.rollback()
            return jsonify({
                'error': 'Import failed',
                'details': errors
            }), 400
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error processing CSV: {str(e)}'}), 400

@main.route('/check_status/<int:app_id>')
def check_status(app_id):
    app = Application.query.get_or_404(app_id)
    status, details = check_application_status(app)
    app.last_checked = datetime.utcnow()
    db.session.commit()
    
    return jsonify({
        'id': app.id,
        'name': app.name,
        'status': status,
        'details': details,
        'last_checked': app.last_checked.isoformat()
    })

@main.route('/check_all_status')
def check_all_status():
    apps = Application.query.all()
    results = {}
    
    for app in apps:
        status, details = check_application_status(app)
        app.last_checked = datetime.utcnow()
        
        results[app.id] = {
            'name': app.name,
            'status': status,
            'details': details,
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
