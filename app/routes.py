from flask import Blueprint, render_template, request, jsonify, current_app
from app.models import db, Team, Application, ApplicationInstance
from app.utils import check_application_status
import csv
from datetime import datetime
import socket

main = Blueprint('main', __name__)

@main.route('/')
def index():
    applications = Application.query.all()
    return render_template('applications.html', applications=applications)

@main.route('/teams')
def teams():
    teams = Team.query.all()
    return render_template('teams.html', teams=teams)

@main.route('/systems')
def systems():
    instances = ApplicationInstance.query.join(Application).join(Team).order_by(Team.name, Application.name).all()
    return render_template('systems.html', instances=instances)

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
        
        # Process rows in chunks
        CHUNK_SIZE = 100
        rows = list(reader)
        total_rows = len(rows)
        
        for i in range(0, total_rows, CHUNK_SIZE):
            chunk = rows[i:i + CHUNK_SIZE]
            
            # Process each row in the chunk
            for row in chunk:
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
                        shutdown_order = int(row.get('shutdown_order', 0))
                        app.shutdown_order = max(0, min(100, shutdown_order))
                    except (ValueError, TypeError):
                        app.shutdown_order = 0
                    
                    # Create instance
                    host = row['host'].strip()
                    port = row.get('port', '').strip()
                    webui_url = row.get('webui_url', '').strip()
                    db_host = row.get('db_host', '').strip()
                    
                    instance = ApplicationInstance(
                        host=host,
                        port=port if port else None,
                        webui_url=webui_url if webui_url else None,
                        db_host=db_host if db_host else None
                    )
                    
                    app.instances.append(instance)
                    db.session.add(instance)
                    
                    # Store dependencies
                    if 'dependencies' in row and row['dependencies']:
                        dependencies_to_process.append((app, row['dependencies']))
                    
                    db.session.add(app)
                
                except Exception as e:
                    errors.append(f"Error processing row {imported + updated + skipped + 1}: {str(e)}")
            
            # Commit chunk
            try:
                db.session.commit()
            except Exception as e:
                db.session.rollback()
                errors.append(f"Error committing chunk: {str(e)}")
                continue
        
        # Process dependencies after all apps are created
        for app, dependencies in dependencies_to_process:
            try:
                dep_names = [d.strip() for d in dependencies.split(';') if d.strip()]
                for dep_name in dep_names:
                    dep_app = Application.query.filter_by(name=dep_name).first()
                    if dep_app:
                        app.dependencies.append(dep_app)
                    else:
                        errors.append(f"Warning: Dependency '{dep_name}' not found for app '{app.name}'")
            except Exception as e:
                errors.append(f"Error processing dependencies for {app.name}: {str(e)}")
        
        # Final commit for dependencies
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            errors.append(f"Error committing dependencies: {str(e)}")
        
        return jsonify({
            'imported': imported,
            'updated': updated,
            'skipped': skipped,
            'total': total_rows,
            'errors': errors if errors else None
        })
    
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main.route('/check_status/<int:app_id>')
def check_status(app_id):
    app = Application.query.get_or_404(app_id)
    results = []
    for instance in app.instances:
        try:
            # Try to connect to the host and port
            if not instance.port:  # Skip if no port specified
                instance.status = 'unknown'
                results.append({
                    'host': instance.host,
                    'port': None,
                    'status': 'unknown',
                    'message': 'No port specified'
                })
                continue
                
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)  # 2 second timeout
            result = sock.connect_ex((instance.host, instance.port))
            sock.close()
            
            if result == 0:
                instance.status = 'running'
            else:
                instance.status = 'stopped'
                
            instance.last_checked = datetime.utcnow()
            results.append({
                'host': instance.host,
                'port': instance.port,
                'status': instance.status
            })
        except Exception as e:
            instance.status = 'unknown'
            instance.last_checked = datetime.utcnow()
            results.append({
                'host': instance.host,
                'port': instance.port,
                'status': 'error',
                'message': str(e)
            })
    
    db.session.commit()
    return jsonify({'status': 'success', 'results': results})

@main.route('/check_instance_status/<int:instance_id>')
def check_instance_status(instance_id):
    instance = ApplicationInstance.query.get_or_404(instance_id)
    try:
        if not instance.port:  # Skip if no port specified
            instance.status = 'unknown'
            instance.last_checked = datetime.utcnow()
            db.session.commit()
            return jsonify({
                'status': 'warning',
                'host': instance.host,
                'port': None,
                'message': 'No port specified'
            })
            
        # Try to connect to the host and port
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)  # 2 second timeout
        result = sock.connect_ex((instance.host, instance.port))
        sock.close()
        
        if result == 0:
            instance.status = 'running'
        else:
            instance.status = 'stopped'
            
        instance.last_checked = datetime.utcnow()
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'host': instance.host,
            'port': instance.port,
            'current_status': instance.status
        })
    except Exception as e:
        instance.status = 'unknown'
        instance.last_checked = datetime.utcnow()
        db.session.commit()
        return jsonify({
            'status': 'error',
            'host': instance.host,
            'port': instance.port,
            'message': str(e)
        })

@main.route('/shutdown_app/<int:app_id>', methods=['POST'])
def shutdown_app(app_id):
    app = Application.query.get_or_404(app_id)
    try:
        # Mark all instances as in_progress
        for instance in app.instances:
            instance.status = 'in_progress'
        db.session.commit()
        
        # Here you would typically trigger an async task to handle the actual shutdown
        # For now, we'll just simulate success
        return jsonify({
            'status': 'success',
            'message': f'Shutdown initiated for {app.name}'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main.route('/shutdown_instance/<int:instance_id>', methods=['POST'])
def shutdown_instance(instance_id):
    instance = ApplicationInstance.query.get_or_404(instance_id)
    try:
        # Mark instance as in_progress
        instance.status = 'in_progress'
        db.session.commit()
        
        # Here you would typically trigger an async task to handle the actual shutdown
        # For now, we'll just simulate success
        return jsonify({
            'status': 'success',
            'message': f'Shutdown initiated for {instance.application.name} on {instance.host}'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main.route('/check_all_status')
def check_all_status():
    apps = Application.query.all()
    results = []
    for app in apps:
        app_results = []
        for instance in app.instances:
            try:
                # Try to connect to the host and port
                if not instance.port:  # Skip if no port specified
                    instance.status = 'unknown'
                    instance.last_checked = datetime.utcnow()
                    app_results.append({
                        'host': instance.host,
                        'port': None,
                        'status': 'unknown',
                        'message': 'No port specified'
                    })
                    continue
                    
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(2)  # 2 second timeout
                result = sock.connect_ex((instance.host, instance.port))
                sock.close()
                
                if result == 0:
                    instance.status = 'running'
                else:
                    instance.status = 'stopped'
                    
                instance.last_checked = datetime.utcnow()
                app_results.append({
                    'host': instance.host,
                    'port': instance.port,
                    'status': instance.status
                })
            except Exception as e:
                instance.status = 'unknown'
                instance.last_checked = datetime.utcnow()
                app_results.append({
                    'host': instance.host,
                    'port': instance.port,
                    'status': 'error',
                    'message': str(e)
                })
        results.append({
            'id': app.id,
            'name': app.name,
            'instances': app_results
        })
    db.session.commit()
    return jsonify(results)
