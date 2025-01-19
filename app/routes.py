from flask import Blueprint, render_template, request, jsonify, current_app
from app import db
from app.models import Application, ApplicationInstance, Team
from datetime import datetime
import socket
import requests
import threading
import time
import json

main = Blueprint('main', __name__)

def get_cached_status(app_id):
    """Get cached status from DB without checking"""
    try:
        app = Application.query.get_or_404(app_id)
        total_instances = len(app.instances)
        down_instances = sum(1 for i in app.instances if i.status == 'DOWN')
        
        status = 'UP' if down_instances == 0 else f'DOWN ({down_instances}/{total_instances})'
        last_checked = max([i.last_checked for i in app.instances if i.last_checked] or [app.last_checked]) if app.last_checked else None
        
        return jsonify({
            'status': 'success',
            'app_status': status,
            'last_checked': last_checked.isoformat() if last_checked else None
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

def get_cached_instance_status(instance_id):
    """Get cached instance status from DB without checking"""
    try:
        instance = ApplicationInstance.query.get_or_404(instance_id)
        error_message = None
        
        if instance.status == 'DOWN':
            error_message = f"Port {instance.port} is not accessible on {instance.host}"
        
        response = {
            'status': 'success',
            'instance_status': instance.status or 'DOWN',
            'last_checked': instance.last_checked.isoformat() if instance.last_checked else None
        }
        
        if error_message:
            response['message'] = error_message
            
        return jsonify(response)
        
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

@main.route('/check_status/<int:app_id>')
def check_status(app_id):
    # Return cached status immediately
    return get_cached_status(app_id)

@main.route('/check_instance_status/<int:instance_id>')
def check_instance_status(instance_id):
    # Return cached status immediately
    return get_cached_instance_status(instance_id)

def background_status_check():
    """Background task to check all application statuses"""
    with current_app.app_context():
        try:
            applications = Application.query.all()
            for app in applications:
                down_count = 0
                total_instances = len(app.instances)
                
                for instance in app.instances:
                    try:
                        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                        sock.settimeout(2)
                        result = sock.connect_ex((instance.host, instance.port or 80))
                        sock.close()
                        
                        instance.status = 'UP' if result == 0 else 'DOWN'
                        if instance.status == 'DOWN':
                            down_count += 1
                            
                    except Exception:
                        instance.status = 'DOWN'
                        down_count += 1
                    
                    instance.last_checked = datetime.utcnow()
                
                app.status = 'UP' if down_count == 0 else 'DOWN'
                app.last_checked = datetime.utcnow()
            
            db.session.commit()
            
        except Exception as e:
            current_app.logger.error(f"Background status check error: {str(e)}")
            db.session.rollback()

def start_background_checker():
    """Start the background status checker thread"""
    def run_checker():
        while True:
            background_status_check()
            time.sleep(30)  # Check every 30 seconds
    
    checker_thread = threading.Thread(target=run_checker, daemon=True)
    checker_thread.start()

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
        # Try to get JSON data first
        if request.is_json:
            data = request.get_json()
        # If not JSON, try form data
        elif 'file' in request.files:
            file = request.files['file']
            if file.filename.endswith('.json'):
                data = json.loads(file.read().decode('utf-8'))
            else:
                return jsonify({
                    'status': 'error',
                    'message': 'Invalid file format. Please upload a JSON file.'
                }), 400
        else:
            return jsonify({
                'status': 'error',
                'message': 'No data provided. Send either JSON data or upload a JSON file.'
            }), 400
            
        if not isinstance(data, dict):
            return jsonify({
                'status': 'error',
                'message': 'Invalid data format. Expected JSON object.'
            }), 400
            
        # First create teams
        for team_data in data.get('teams', []):
            if not isinstance(team_data, dict) or 'name' not in team_data:
                continue
                
            team = Team.query.filter_by(name=team_data['name']).first()
            if not team:
                team = Team(name=team_data['name'])
                db.session.add(team)
        db.session.commit()  # Commit teams first
        
        # Then create applications and instances
        for app_data in data.get('applications', []):
            if not isinstance(app_data, dict) or 'name' not in app_data or 'team' not in app_data:
                continue
                
            team = Team.query.filter_by(name=app_data['team']).first()
            if not team:
                continue  # Skip if team doesn't exist
                
            app = Application.query.filter_by(name=app_data['name'], team_id=team.id).first()
            if not app:
                app = Application(
                    name=app_data['name'],
                    team_id=team.id,
                    shutdown_order=app_data.get('shutdown_order')
                )
                db.session.add(app)
                
            # Create or update instances
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
        
    except json.JSONDecodeError as e:
        return jsonify({
            'status': 'error',
            'message': f'Invalid JSON format: {str(e)}'
        }), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({
            'status': 'error',
            'message': f'Import failed: {str(e)}'
        }), 500

@main.route('/check_all_status')
def check_all_status():
    results = []
    try:
        applications = Application.query.all()
        for app in applications:
            app_results = []
            app_is_running = True
            
            for instance in app.instances:
                try:
                    # Check if host is reachable
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)  # 2 second timeout
                    result = sock.connect_ex((instance.host, instance.port or 80))
                    sock.close()
                    
                    if result != 0:
                        app_is_running = False
                        app_results.append({
                            'id': instance.id,
                            'host': instance.host,
                            'port': instance.port,
                            'status': 'DOWN',
                            'last_checked': instance.last_checked.isoformat() if instance.last_checked else None
                        })
                    else:
                        app_results.append({
                            'id': instance.id,
                            'host': instance.host,
                            'port': instance.port,
                            'status': 'UP',
                            'last_checked': instance.last_checked.isoformat() if instance.last_checked else None
                        })
                    
                except socket.gaierror:
                    app_is_running = False
                    app_results.append({
                        'id': instance.id,
                        'host': instance.host,
                        'port': instance.port,
                        'status': 'DOWN',
                        'last_checked': instance.last_checked.isoformat() if instance.last_checked else None
                    })
                except socket.timeout:
                    app_is_running = False
                    app_results.append({
                        'id': instance.id,
                        'host': instance.host,
                        'port': instance.port,
                        'status': 'DOWN',
                        'last_checked': instance.last_checked.isoformat() if instance.last_checked else None
                    })
                except Exception as e:
                    app_is_running = False
                    app_results.append({
                        'id': instance.id,
                        'host': instance.host,
                        'port': instance.port,
                        'status': 'DOWN',
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
def update_application_details(app_id):
    try:
        data = request.get_json()
        
        # Get application
        application = Application.query.get_or_404(app_id)
        
        # Update team if it exists, create if it doesn't
        team = Team.query.filter_by(name=data['team']).first()
        if not team:
            team = Team(name=data['team'])
            db.session.add(team)
        
        # Update application
        application.name = data['name']
        application.team_id = team.id
        application.shutdown_order = data.get('shutdown_order', 100)
        application.dependencies = data.get('dependencies', [])
        
        # Update instances
        if 'instances' in data:
            # Delete removed instances
            current_instance_ids = [i.get('id') for i in data['instances'] if i.get('id')]
            ApplicationInstance.query.filter(
                ApplicationInstance.application_id == app_id,
                ~ApplicationInstance.id.in_(current_instance_ids) if current_instance_ids else True
            ).delete(synchronize_session=False)
            
            # Update/create instances
            for instance_data in data['instances']:
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
        main.logger.error(f"Error updating application: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

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
            
            deps.sort(key=lambda x: x.shutdown_order)
            sequence.extend(deps)
            
            # Add current app if not already in sequence
            if current_app not in sequence:
                sequence.append(current_app)
        
        get_dependencies(app)
        
        # Calculate states
        for app in sequence:
            all_running = True
            all_stopped = True
            
            for instance in app.instances:
                try:
                    # Check if host is reachable
                    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    sock.settimeout(2)  # 2 second timeout
                    result = sock.connect_ex((instance.host, instance.port or 80))
                    sock.close()
                    
                    if result != 0:
                        all_running = False
                        all_stopped = False
                    else:
                        instance.status = 'running'
                except:
                    all_running = False
                    all_stopped = False
            
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
        main.logger.error(f"Error updating system: {str(e)}")
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
            'systems': systems,
            'current_dependencies': []  # This will be populated with actual dependencies
        })
    except Exception as e:
        main.logger.error(f"Error getting systems: {str(e)}")
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
        main.logger.error(f"Error updating application: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
