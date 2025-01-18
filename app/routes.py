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
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file or not file.filename.endswith('.csv'):
        return jsonify({'error': 'Invalid file format. Please upload a CSV file.'}), 400
    
    merge_mode = request.form.get('merge_mode', 'skip')
    if merge_mode not in ['skip', 'merge', 'replace']:
        return jsonify({'error': 'Invalid merge mode'}), 400
    
    try:
        # Read CSV file
        csv_data = file.read().decode('utf-8').splitlines()
        reader = csv.DictReader(csv_data)
        
        # Validate headers
        required_fields = ['name', 'team', 'host']
        missing_fields = [field for field in required_fields if field not in reader.fieldnames]
        if missing_fields:
            return jsonify({
                'error': f'Missing required fields: {", ".join(missing_fields)}'
            }), 400
        
        # Start transaction
        imported = updated = skipped = 0
        errors = []
        
        # Cache teams and apps for better performance
        team_cache = {}
        app_cache = {}
        
        # Store dependencies for later processing
        dependencies_to_process = []
        
        # Delete all if replace mode
        if merge_mode == 'replace':
            ApplicationInstance.query.delete()
            Application.query.delete()
            Team.query.delete()
            db.session.commit()
        
        # Process each row
        for row in reader:
            try:
                # Get or create team
                team_name = row['team'].strip()
                if team_name in team_cache:
                    team = team_cache[team_name]
                else:
                    team = Team.query.filter_by(name=team_name).first()
                    if not team:
                        team = Team(name=team_name)
                        db.session.add(team)
                    team_cache[team_name] = team
                
                # Get or create application
                app_name = row['name'].strip()
                if app_name in app_cache:
                    app = app_cache[app_name]
                    if merge_mode == 'skip':
                        skipped += 1
                        continue
                else:
                    app = Application.query.filter_by(name=app_name).first()
                    if app:
                        if merge_mode == 'skip':
                            skipped += 1
                            continue
                        elif merge_mode == 'merge':
                            updated += 1
                    else:
                        app = Application(name=app_name)
                        imported += 1
                    app_cache[app_name] = app
                
                # Update application
                app.team = team
                
                # Safely parse shutdown_order
                try:
                    shutdown_order = int(row.get('shutdown_order', '100').strip())
                except (ValueError, TypeError):
                    shutdown_order = 100
                app.shutdown_order = shutdown_order
                
                # Store dependencies for later processing
                dependencies = row.get('dependencies', '').strip()
                if dependencies:
                    dependencies_to_process.append((app, dependencies))
                
                if not app.id:
                    db.session.add(app)
                
                # Safely parse port
                port_str = row.get('port', '').strip()
                try:
                    port = int(port_str) if port_str else None
                except ValueError:
                    port = None
                    if port_str:  # Only add error if port was provided but invalid
                        errors.append(f"Invalid port number '{port_str}' in row {reader.line_num}, using None")
                
                # Create instance
                instance = ApplicationInstance(
                    application=app,
                    host=row['host'].strip(),
                    port=port,
                    webui_url=row.get('webui_url', '').strip() or None,
                    db_host=row.get('db_host', '').strip() or None
                )
                db.session.add(instance)
                
            except Exception as e:
                errors.append(f"Error processing row {reader.line_num}: {str(e)}")
                continue
        
        # Process dependencies after all applications are created
        for app, dependencies_str in dependencies_to_process:
            dependency_names = [d.strip() for d in dependencies_str.split(';') if d.strip()]
            app.dependencies = []  # Clear existing dependencies
            for dep_name in dependency_names:
                if dep_app := app_cache.get(dep_name):
                    app.dependencies.append(dep_app.name)
                else:
                    errors.append(f"Warning: Dependency '{dep_name}' for application '{app.name}' not found")
        
        # Commit all changes at once
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Database error: {str(e)}'}), 500
        
        return jsonify({
            'imported': imported,
            'updated': updated,
            'skipped': skipped,
            'errors': errors if errors else None,
            'message': f'Import completed: {imported} imported, {updated} updated, {skipped} skipped'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

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
