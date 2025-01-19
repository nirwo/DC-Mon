from flask import Blueprint, render_template, request, jsonify, current_app
from app.models import db, Team, Application, ApplicationInstance
from app.utils import check_application_status, check_host_status
import csv
from datetime import datetime
import socket
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

@main.route('/import_apps', methods=['POST'])
def import_apps():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file or not file.filename.endswith('.csv'):
        return jsonify({'error': 'Invalid file format. Please upload a CSV file.'}), 400
    
    merge_mode = request.form.get('merge_mode', 'skip')
    encoding = request.form.get('encoding', 'utf-8')
    
    if merge_mode not in ['skip', 'merge', 'replace']:
        return jsonify({'error': 'Invalid merge mode'}), 400
    
    try:
        # Read CSV file with specified encoding
        try:
            csv_data = file.read().decode(encoding).splitlines()
        except UnicodeDecodeError:
            # Try common encodings if specified one fails
            for enc in ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']:
                try:
                    file.seek(0)
                    csv_data = file.read().decode(enc).splitlines()
                    encoding = enc
                    break
                except UnicodeDecodeError:
                    continue
            else:
                return jsonify({'error': 'Unable to decode file. Please specify correct encoding.'}), 400
        
        # Validate headers
        required_fields = ['name', 'team', 'host']
        missing_fields = [field for field in required_fields if field not in csv.DictReader(csv_data).fieldnames]
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
        rows = list(csv.DictReader(csv_data))
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
                    
                    # Create or update instance
                    host = row['host'].strip()
                    port = row.get('port', '').strip()
                    webui_url = row.get('webui_url', '').strip()
                    db_host = row.get('db_host', '').strip()
                    
                    # Check for existing instance
                    instance = ApplicationInstance.query.filter_by(
                        application_id=app.id,
                        host=host
                    ).first()
                    
                    if instance:
                        # Update existing instance
                        instance.port = port if port else None
                        instance.webui_url = webui_url if webui_url else None
                        instance.db_host = db_host if db_host else None
                    else:
                        # Create new instance
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
                errors.append(f"Database error: {str(e)}")
                return jsonify({
                    'error': 'Database error occurred',
                    'details': errors
                }), 500
        
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
            errors.append(f"Database error: {str(e)}")
            return jsonify({
                'error': 'Database error occurred',
                'details': errors
            }), 500
        
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
    try:
        app = Application.query.get_or_404(app_id)
        results = []
        
        for instance in app.instances:
            # Check host status
            is_running, details = check_host_status(instance.host, instance.port)
            
            # Check WebUI if configured
            webui_status = True
            webui_message = None
            if instance.webui_url:
                try:
                    response = requests.get(instance.webui_url, timeout=5)
                    if response.status_code != 200:
                        webui_status = False
                        webui_message = f'WebUI returned status code: {response.status_code}'
                except Exception as e:
                    webui_status = False
                    webui_message = f'WebUI error: {str(e)}'
            
            status = 'running' if is_running and webui_status else 'stopped'
            
            # Combine host and WebUI status messages
            messages = details
            if webui_message:
                messages.append(webui_message)
            
            results.append({
                'host': instance.host,
                'port': instance.port,
                'status': status,
                'details': messages,
                'webui_url': instance.webui_url
            })
        
        return jsonify({'results': results})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/check_instance_status/<int:instance_id>')
def check_instance_status(instance_id):
    try:
        instance = ApplicationInstance.query.get_or_404(instance_id)
        is_running = ping_host(instance.host)
        
        # Update instance status
        instance.status = 'running' if is_running else 'stopped'
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'is_running': is_running,
            'details': []
        })
    except Exception as e:
        db.session.rollback()
        main.logger.error(f"Error checking status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/check_all_status')
def check_all_status():
    results = []
    try:
        applications = Application.query.all()
        for app in applications:
            app_results = []
            app_is_running = True
            
            for instance in app.instances:
                is_running, details = check_host_status(instance.host, instance.port)
                
                # Update instance status
                instance.status = 'running' if is_running else 'stopped'
                instance.last_checked = datetime.utcnow()
                
                if not is_running:
                    app_is_running = False
                
                app_results.append({
                    'id': instance.id,
                    'host': instance.host,
                    'port': instance.port,
                    'status': instance.status,
                    'details': details,
                    'last_checked': instance.last_checked.isoformat() if instance.last_checked else None
                })
            
            # Update application status
            app.state = 'up' if app_is_running else 'down'
            results.append({
                'id': app.id,
                'name': app.name,
                'state': app.state,
                'instances': app_results
            })
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f"Database error: {str(e)}"
            }), 500
            
        return jsonify({
            'status': 'success',
            'results': results
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main.route('/shutdown_app/<int:app_id>', methods=['POST'])
def shutdown_app(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        
        # Get shutdown sequence
        sequence = []
        visited = set()
        
        def get_dependencies(current_app):
            if current_app.id in visited:
                return
            visited.add(current_app.id)
            
            # Get dependencies and sort by shutdown order
            deps = []
            for dep_id in current_app.dependencies:
                dep = Application.query.get(dep_id)
                if dep:
                    deps.append(dep)
                    get_dependencies(dep)
            
            deps.sort(key=lambda x: x.shutdown_order)
            sequence.extend(deps)
            
            # Add current app if not already in sequence
            if current_app not in sequence:
                sequence.append(current_app)
        
        get_dependencies(app)
        
        # Start shutdown process for each app in sequence
        for app in sequence:
            app.state = 'down'
            for instance in app.instances:
                try:
                    url = instance.webui_url
                    if not url:
                        url = f"http://{instance.host}"
                        if instance.port:
                            url += f":{instance.port}"
                    
                    # Send shutdown request
                    response = requests.post(f"{url}/shutdown", timeout=5)
                    if response.status_code != 200:
                        return jsonify({
                            'status': 'error',
                            'message': f'Failed to shutdown {app.name} - {instance.host}: Unexpected status code {response.status_code}'
                        }), 400
                        
                except requests.exceptions.RequestException as e:
                    return jsonify({
                        'status': 'error',
                        'message': f'Failed to shutdown {app.name} - {instance.host}: {str(e)}'
                    }), 400
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f"Database error: {str(e)}"
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': 'Shutdown sequence initiated successfully'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

@main.route('/shutdown_instance/<int:instance_id>', methods=['POST'])
def shutdown_instance(instance_id):
    instance = ApplicationInstance.query.get_or_404(instance_id)
    try:
        # Mark instance as in_progress
        instance.status = 'in_progress'
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f"Database error: {str(e)}"
            }), 500
        
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

@main.route('/get_application/<int:app_id>')
def get_application(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        return jsonify({
            'status': 'success',
            'data': {
                'id': app.id,
                'name': app.name,
                'team_id': app.team_id,
                'state': app.state,
                'shutdown_order': app.shutdown_order,
                'dependencies': app.dependencies,
                'instances': [{
                    'id': inst.id,
                    'host': inst.host,
                    'port': inst.port,
                    'webui_url': inst.webui_url,
                    'db_host': inst.db_host,
                    'status': inst.status
                } for inst in app.instances]
            }
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 400

@main.route('/update_application/<int:app_id>', methods=['POST'])
def update_application(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        data = request.get_json()
        
        if not data:
            return jsonify({'status': 'error', 'message': 'No data provided'}), 400
        
        if 'name' not in data or not data['name']:
            return jsonify({'status': 'error', 'message': 'Application name is required'}), 400
        
        # Update application details
        app.name = data['name']
        app.team_id = data['team_id']
        app.shutdown_order = data.get('shutdown_order', 100)
        app.dependencies = data.get('dependencies', [])
        
        # Update instances
        if 'instances' in data:
            updated_ids = set()
            
            for inst_data in data['instances']:
                if 'id' in inst_data and inst_data['id']:
                    # Update existing instance
                    instance = next((i for i in app.instances if i.id == inst_data['id']), None)
                    if instance:
                        instance.host = inst_data['host']
                        instance.port = inst_data.get('port')
                        instance.webui_url = inst_data.get('webui_url')
                        instance.db_host = inst_data.get('db_host')
                        updated_ids.add(instance.id)
                else:
                    # Create new instance
                    instance = ApplicationInstance(
                        application=app,
                        host=inst_data['host'],
                        port=inst_data.get('port'),
                        webui_url=inst_data.get('webui_url'),
                        db_host=inst_data.get('db_host')
                    )
                    db.session.add(instance)
            
            # Remove instances that weren't updated
            for instance in app.instances:
                if instance.id not in updated_ids:
                    db.session.delete(instance)
        
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f"Database error: {str(e)}"
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': f'Application {app.name} updated successfully',
            'data': {
                'id': app.id,
                'name': app.name,
                'team_id': app.team_id,
                'shutdown_order': app.shutdown_order,
                'dependencies': app.dependencies
            }
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'status': 'error', 'message': str(e)}), 400

@main.route('/get_shutdown_sequence/<int:app_id>')
def get_shutdown_sequence(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        sequence = []
        visited = set()
        
        def get_dependencies(current_app):
            if current_app.id in visited:
                return
            visited.add(current_app.id)
            
            # Get dependencies and sort by shutdown order
            deps = []
            for dep_id in current_app.dependencies:
                dep = Application.query.get(dep_id)
                if dep:
                    deps.append(dep)
                    get_dependencies(dep)
            
            # Sort by shutdown order
            deps.sort(key=lambda x: x.shutdown_order)
            
            # Add current app if not already in sequence
            if current_app not in sequence:
                sequence.append(current_app)
            
            # Add dependencies after current app
            for dep in deps:
                if dep not in sequence:
                    sequence.append(dep)
        
        # Start with the target app
        get_dependencies(app)
        
        # Calculate states
        for app in sequence:
            all_running = True
            all_stopped = True
            
            for instance in app.instances:
                try:
                    url = instance.webui_url
                    if not url:
                        url = f"http://{instance.host}"
                        if instance.port:
                            url += f":{instance.port}"
                    
                    response = requests.get(url, timeout=5)
                    if response.status_code == 200:
                        instance.status = 'running'
                        all_stopped = False
                    else:
                        instance.status = 'stopped'
                        all_running = False
                except:
                    instance.status = 'stopped'
                    all_running = False
            
            if all_running:
                app.state = 'up'
            elif all_stopped:
                app.state = 'down'
            else:
                app.state = 'partial'
        
        # Format sequence for response
        sequence_data = [{
            'id': app.id,
            'name': app.name,
            'shutdown_order': app.shutdown_order,
            'state': app.state
        } for app in sequence]
        
        return jsonify({
            'status': 'success',
            'sequence': sequence_data
        })
        
    except Exception as e:
        main.logger.error(f"Error getting shutdown sequence: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

@main.route('/mark_completed/<int:app_id>', methods=['POST'])
def mark_completed(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        app.completed = True
        app.completed_at = datetime.utcnow()
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f"Database error: {str(e)}"
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': f'Application {app.name} marked as completed'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

@main.route('/reactivate_application/<int:app_id>', methods=['POST'])
def reactivate_application(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        app.completed = False
        app.completed_at = None
        try:
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({
                'status': 'error',
                'message': f"Database error: {str(e)}"
            }), 400
        
        return jsonify({
            'status': 'success',
            'message': f'Application {app.name} reactivated'
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 400

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

@main.route('/delete_selected_applications', methods=['POST'])
def delete_selected_applications():
    try:
        data = request.get_json()
        app_ids = data.get('app_ids', [])
        
        # Delete instances first
        ApplicationInstance.query.filter(ApplicationInstance.application_id.in_(app_ids)).delete(synchronize_session=False)
        
        # Then delete applications
        Application.query.filter(Application.id.in_(app_ids)).delete(synchronize_session=False)
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': f'Deleted {len(app_ids)} applications'})
    except Exception as e:
        db.session.rollback()
        main.logger.error(f"Error deleting selected applications: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/delete_all_applications', methods=['POST'])
def delete_all_applications():
    try:
        # Delete all instances first
        ApplicationInstance.query.delete(synchronize_session=False)
        
        # Then delete all applications
        Application.query.delete(synchronize_session=False)
        
        db.session.commit()
        return jsonify({'status': 'success', 'message': 'All applications deleted'})
    except Exception as e:
        db.session.rollback()
        main.logger.error(f"Error deleting all applications: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/update_system', methods=['POST'])
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
        main.logger.error(f"Error updating system: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
