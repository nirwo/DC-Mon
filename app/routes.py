from flask import Blueprint, render_template, request, jsonify, send_file, make_response
from app.models import db, Team, Application, ApplicationDependency, ApplicationInstance
from app.utils import get_application_status, get_shutdown_sequence, check_application_status
import csv
from io import StringIO
from datetime import datetime

main = Blueprint('main', __name__)

def clean_csv_value(value):
    """Clean and validate CSV value"""
    if value is None:
        return None
    value = str(value).strip()
    return value if value else None

def map_csv_columns(headers):
    """Map CSV headers to expected column names"""
    column_mappings = {
        'name': ['name', 'application_name', 'app_name', 'application'],
        'team': ['team', 'team_name', 'team_id'],
        'host': ['host', 'hostname', 'server', 'address'],
        'port': ['port', 'app_port', 'server_port'],
        'webui_url': ['webui_url', 'webui', 'web_url', 'url'],
        'db_host': ['db_host', 'database_host', 'db_server', 'database'],
        'shutdown_order': ['shutdown_order', 'order', 'priority'],
        'dependencies': ['dependencies', 'depends_on', 'dependency']
    }
    
    mapped_columns = {}
    headers_lower = [h.lower().strip() for h in headers]
    
    for target_col, possible_names in column_mappings.items():
        for name in possible_names:
            if name in headers_lower:
                mapped_columns[target_col] = headers[headers_lower.index(name)]
                break
                
    return mapped_columns

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

@main.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    app = Application.query.get_or_404(app_id)
    
    # Delete dependencies
    ApplicationDependency.query.filter_by(application_id=app_id).delete()
    ApplicationDependency.query.filter_by(dependency_id=app_id).delete()
    
    # Delete application
    db.session.delete(app)
    db.session.commit()
    
    return jsonify({'message': 'Application deleted successfully'})

@main.route('/api/applications/bulk_delete', methods=['POST'])
def bulk_delete_applications():
    """Delete multiple applications at once"""
    app_ids = request.json.get('app_ids', [])
    if not app_ids:
        return jsonify({'error': 'No applications selected'}), 400
    
    try:
        # Delete dependencies first
        for app_id in app_ids:
            ApplicationDependency.query.filter_by(application_id=app_id).delete()
            ApplicationDependency.query.filter_by(dependency_id=app_id).delete()
        
        # Delete applications
        deleted = Application.query.filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        db.session.commit()
        
        return jsonify({
            'message': f'Successfully deleted {deleted} applications',
            'deleted': deleted
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 400

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
    
    merge_mode = request.form.get('merge_mode', 'skip')  # skip, merge, or replace
    
    try:
        # Read CSV content
        content = file.read().decode('utf-8-sig')  # Handle BOM if present
        reader = csv.DictReader(StringIO(content))
        
        # Map columns
        column_mapping = map_csv_columns(reader.fieldnames)
        
        # Validate required fields
        required_fields = ['name', 'team', 'host']
        missing_fields = [field for field in required_fields if field not in column_mapping]
        if missing_fields:
            return jsonify({'error': f'Missing required fields: {", ".join(missing_fields)}'}), 400

        # If replace mode, delete all existing applications
        if merge_mode == 'replace':
            ApplicationDependency.query.delete()
            ApplicationInstance.query.delete()
            Application.query.delete()
            db.session.commit()
        
        # Start transaction
        imported = 0
        updated = 0
        skipped = 0
        errors = []
        
        # Create dictionaries to store teams and applications to minimize database queries
        teams_cache = {}
        apps_cache = {}
        pending_dependencies = []
        
        # Process all rows
        for row in reader:
            try:
                # Clean and map values
                name = clean_csv_value(row.get(column_mapping['name']))
                team_name = clean_csv_value(row.get(column_mapping['team']))
                host = clean_csv_value(row.get(column_mapping['host']))
                
                # Skip row if required fields are empty
                if not all([name, team_name, host]):
                    errors.append(f"Skipping row: missing required fields (name: {name}, team: {team_name}, host: {host})")
                    continue
                
                # Get optional values
                port = clean_csv_value(row.get(column_mapping.get('port')))
                webui_url = clean_csv_value(row.get(column_mapping.get('webui_url')))
                db_host = clean_csv_value(row.get(column_mapping.get('db_host')))
                shutdown_order = clean_csv_value(row.get(column_mapping.get('shutdown_order')))
                dependencies = clean_csv_value(row.get(column_mapping.get('dependencies')))
                
                # Get or create team using cache
                if team_name not in teams_cache:
                    team = Team.query.filter_by(name=team_name).first()
                    if not team:
                        team = Team(name=team_name)
                        db.session.add(team)
                        db.session.flush()
                    teams_cache[team_name] = team
                team = teams_cache[team_name]
                
                # Get or create application
                app = apps_cache.get(name) or Application.query.filter_by(name=name).first()
                
                if not app:
                    app = Application(
                        name=name,
                        team_id=team.id,
                        shutdown_order=int(shutdown_order) if shutdown_order and shutdown_order.isdigit() else 100
                    )
                    db.session.add(app)
                    db.session.flush()
                    apps_cache[name] = app
                    imported += 1
                elif merge_mode == 'skip':
                    skipped += 1
                    continue
                elif merge_mode == 'merge':
                    app.team_id = team.id
                    if shutdown_order and shutdown_order.isdigit():
                        app.shutdown_order = int(shutdown_order)
                    updated += 1
                
                # Get or create instance
                instance = ApplicationInstance.query.filter_by(
                    application_id=app.id,
                    host=host
                ).first()
                
                if not instance:
                    instance = ApplicationInstance(
                        application_id=app.id,
                        host=host,
                        port=int(port) if port and port.isdigit() else None,
                        webui_url=webui_url,
                        db_host=db_host
                    )
                    db.session.add(instance)
                else:
                    instance.port = int(port) if port and port.isdigit() else instance.port
                    instance.webui_url = webui_url if webui_url else instance.webui_url
                    instance.db_host = db_host if db_host else instance.db_host
                
                # Store dependencies for later processing
                if dependencies:
                    for dep_name in dependencies.split(';'):
                        if dep_name := clean_csv_value(dep_name):
                            # Add to pending dependencies to process after all apps are created
                            pending_dependencies.append((app.id, dep_name))
                
            except Exception as e:
                errors.append(f"Error processing row {name}: {str(e)}")
                continue
        
        # Process dependencies after all applications are created
        for app_id, dep_name in pending_dependencies:
            if dep_app := Application.query.filter_by(name=dep_name).first():
                if not ApplicationDependency.query.filter_by(
                    application_id=app_id,
                    dependency_id=dep_app.id
                ).first():
                    dependency = ApplicationDependency(
                        application_id=app_id,
                        dependency_id=dep_app.id,
                        dependency_type='shutdown_before'
                    )
                    db.session.add(dependency)
        
        # Final commit
        db.session.commit()
        
        return jsonify({
            'message': f'Import completed: {imported} imported, {updated} updated, {skipped} skipped',
            'imported': imported,
            'updated': updated,
            'skipped': skipped,
            'errors': errors if errors else None
        })
            
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': f'Error processing CSV: {str(e)}'}), 400

@main.route('/check_status/<int:app_id>')
def check_status(app_id):
    app = Application.query.get_or_404(app_id)
    all_running = True
    details = []
    
    for instance in app.instances:
        is_running, instance_details = check_application_status(instance)
        instance.is_running = is_running
        instance.status_details = '; '.join(instance_details) if instance_details else None
        instance.last_checked = datetime.utcnow()
        if not is_running:
            all_running = False
        details.extend(instance_details)
    
    db.session.commit()
    
    return jsonify({
        'is_running': all_running,
        'details': details
    })

@main.route('/shutdown/<int:app_id>')
def shutdown_app(app_id):
    app = Application.query.get_or_404(app_id)
    sequence = get_shutdown_sequence(app)
    return jsonify(sequence)

@main.route('/api/teams/<int:team_id>', methods=['DELETE'])
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    
    # Check if team has applications
    if team.applications:
        return jsonify({
            'error': 'Cannot delete team with applications',
            'applications': [app.name for app in team.applications]
        }), 400
    
    # Delete team
    db.session.delete(team)
    db.session.commit()
    
    return jsonify({'message': 'Team deleted successfully'})
