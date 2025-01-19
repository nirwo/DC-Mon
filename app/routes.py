from datetime import datetime
import json
from flask import Blueprint, render_template, jsonify, request, current_app
from app.models import Team, Application, ApplicationInstance, System
from app.database import get_db
import csv
import requests
import logging
import os
from bson import ObjectId
from io import StringIO

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

main = Blueprint('main', __name__)

def check_host_status(host):
    try:
        response = os.system(f"ping -c 1 -W 1 {host} > /dev/null 2>&1")
        return response == 0
    except:
        return False

@main.route('/')
def index():
    db = get_db()
    teams_data = list(db.teams.find())
    teams = []
    applications = []
    
    # Get teams with applications and systems
    for team_data in teams_data:
        team = Team.from_dict(team_data)
        team_dict = team.to_dict()
        
        # Get applications for this team
        team_apps = list(db.applications.find({"team_id": ObjectId(str(team._id))}))
        team_dict['applications'] = len(team_apps)
        
        # Get systems for team's applications
        systems = []
        for app in team_apps:
            app_systems = list(db.systems.find({"application_id": str(app['_id'])}))
            systems.extend(app_systems)
        team_dict['systems'] = len(systems)
        
        teams.append(team_dict)
    
    # Get applications with team info and state
    for app_data in db.applications.find():
        app = Application.from_dict(app_data)
        app_dict = app.to_dict()
        
        # Get team info
        if app.team_id:
            team = db.teams.find_one({"_id": ObjectId(str(app.team_id))})
            if team:
                app_dict['team'] = {'name': team['name']}
            else:
                app_dict['team'] = {'name': 'No Team'}
        else:
            app_dict['team'] = {'name': 'No Team'}
            
        # Get systems
        systems = []
        for system_data in db.systems.find({'application_id': str(app._id)}):
            system = System.from_dict(system_data)
            systems.append({
                'id': str(system._id),
                'name': system.name,
                'status': system.status,
                'last_checked': system.last_checked,
                'port': system.port,
                'webui_url': system.webui_url
            })
        app_dict['systems'] = systems
        
        applications.append(app_dict)
    
    return render_template('index.html', teams=teams, applications=applications)

@main.route('/teams')
def teams():
    db = get_db()
    teams = [Team.from_dict(team) for team in db.teams.find()]
    return render_template('teams.html', teams=teams)

@main.route('/systems')
def systems():
    db = get_db()
    pipeline = [
        {
            '$lookup': {
                'from': 'applications',
                'localField': 'application_id',
                'foreignField': '_id',
                'as': 'application'
            }
        },
        {
            '$unwind': '$application'
        },
        {
            '$lookup': {
                'from': 'teams',
                'localField': 'application.team_id',
                'foreignField': '_id',
                'as': 'team'
            }
        },
        {
            '$unwind': '$team'
        },
        {
            '$sort': {
                'team.name': 1,
                'application.name': 1
            }
        }
    ]
    instances = [ApplicationInstance.from_dict(inst) for inst in db.application_instances.aggregate(pipeline)]
    return render_template('systems.html', instances=instances)

@main.route('/check_all_status')
def check_all_status():
    try:
        logger.info("Starting check_all_status")
        db = get_db()
        
        instances = db.application_instances.find()
        for instance_data in instances:
            try:
                instance = ApplicationInstance.from_dict(instance_data)
                instance.status = 'checking'
                instance.details = 'Status check initiated'
                instance.last_checked = datetime.utcnow()
                
                db.application_instances.update_one(
                    {'_id': instance._id},
                    {'$set': instance.to_dict()}
                )
                logger.info(f"Updated instance {instance._id} status to checking")
            except Exception as e:
                logger.error(f"Error updating instance {instance._id}: {str(e)}")
                continue
        
        return jsonify({'status': 'success', 'message': 'Status check initiated for all instances'})
    except Exception as e:
        logger.error(f"Error in check_all_status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

@main.route('/check_status/<int:instance_id>')
def check_status(instance_id):
    try:
        logger.info(f"Starting check_status for instance {instance_id}")
        db = get_db()
        
        instance_data = db.application_instances.find_one({'_id': ObjectId(instance_id)})
        if not instance_data:
            return jsonify({'status': 'error', 'message': 'Instance not found'}), 404
        
        instance = ApplicationInstance.from_dict(instance_data)
        instance.status = 'checking'
        instance.details = 'Status check initiated'
        instance.last_checked = datetime.utcnow()
        
        db.application_instances.update_one(
            {'_id': instance._id},
            {'$set': instance.to_dict()}
        )
        logger.info(f"Updated instance {instance_id} status to checking")
        
        return jsonify({'status': 'success', 'message': 'Status check initiated'})
    except Exception as e:
        logger.error(f"Error in check_status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

@main.route('/import', methods=['POST'])
def import_data():
    try:
        logger.info("Starting import process")
        if 'file' not in request.files:
            logger.error("No file in request.files")
            return jsonify({'success': False, 'error': 'No file provided'})
            
        file = request.files['file']
        if not file or not file.filename:
            logger.error("Empty file or no filename")
            return jsonify({'success': False, 'error': 'No file selected'})
            
        logger.info(f"Received file: {file.filename}")
        
        if not file.filename.endswith('.csv'):
            logger.error("File is not a CSV")
            return jsonify({'success': False, 'error': 'Only CSV files are supported'})
            
        content = file.read().decode('utf-8')
        logger.info(f"File content length: {len(content)}")
        
        # Check if file is empty
        if len(content.strip()) == 0:
            logger.error("CSV file is empty")
            return jsonify({'success': False, 'error': 'CSV file is empty'})
            
        csv_reader = csv.DictReader(StringIO(content))
        field_names = csv_reader.fieldnames
        logger.info(f"CSV fields: {field_names}")
        
        # Validate required fields
        required_fields = ['team_name', 'application_name', 'host']
        missing_fields = [field for field in required_fields if field not in field_names]
        if missing_fields:
            error_msg = f"CSV is missing required columns: {', '.join(missing_fields)}"
            logger.error(error_msg)
            return jsonify({'success': False, 'error': error_msg})
        
        db = get_db()
        errors = []
        success_count = 0
        
        for row_num, row in enumerate(csv_reader, 1):
            try:
                logger.info(f"Processing row {row_num}: {row}")
                
                # Check for empty required fields
                empty_fields = [field for field in required_fields if not row.get(field, '').strip()]
                if empty_fields:
                    error_msg = f"Row {row_num}: Missing values for required fields: {', '.join(empty_fields)}"
                    logger.error(error_msg)
                    errors.append(error_msg)
                    continue
                
                # Create or get team
                team_result = db.teams.find_one_and_update(
                    {'name': row['team_name'].strip()},
                    {'$setOnInsert': {
                        'name': row['team_name'].strip(),
                        'description': row.get('team_description', '').strip()
                    }},
                    upsert=True,
                    return_document=True
                )
                logger.info(f"Team created/updated: {team_result}")
                
                # Create or get application
                app_result = db.applications.find_one_and_update(
                    {
                        'name': row['application_name'].strip(),
                        'team_id': str(team_result['_id'])
                    },
                    {
                        '$set': {
                            'name': row['application_name'].strip(),
                            'team_id': str(team_result['_id']),
                            'shutdown_order': int(row.get('shutdown_order', 0)),
                            'description': row.get('application_description', '').strip()
                        }
                    },
                    upsert=True,
                    return_document=True
                )
                logger.info(f"Application created/updated: {app_result}")
                
                # Create or update system
                system_data = {
                    'name': row['host'].strip(),
                    'host': row['host'].strip(),
                    'application_id': str(app_result['_id']),
                    'port': int(row['port']) if row.get('port', '').strip().isdigit() else None,
                    'webui_url': row.get('webui_url', '').strip() or None,
                    'status': 'unknown',
                    'last_checked': datetime.utcnow()
                }
                
                system_result = db.systems.find_one_and_update(
                    {'host': row['host'].strip(), 'application_id': str(app_result['_id'])},
                    {'$set': system_data},
                    upsert=True,
                    return_document=True
                )
                logger.info(f"System created/updated: {system_result}")
                
                success_count += 1
                logger.info(f"Successfully processed row {row_num}")
                
            except Exception as e:
                error_msg = f"Row {row_num}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
                continue
        
        if success_count == 0:
            logger.error("No rows were successfully imported")
            return jsonify({
                'success': False,
                'error': 'No rows were successfully imported',
                'errors': errors
            })
        
        response = {
            'success': True,
            'message': f"{success_count} items successfully imported",
            'errors': errors if errors else None
        }
        logger.info(f"Import completed. Response: {response}")
        return jsonify(response)
        
    except Exception as e:
        error_msg = f"Import error: {str(e)}"
        logger.error(error_msg)
        return jsonify({'success': False, 'error': error_msg})

@main.route('/api/systems/<system_id>/status', methods=['GET'])
def get_system_status(system_id):
    try:
        db = get_db()
        system = db.systems.find_one({'_id': ObjectId(system_id)})
        if not system:
            return jsonify({'success': False, 'error': 'System not found'})
            
        is_running = check_host_status(system['host'])
        status = 'running' if is_running else 'stopped'
        
        # Update system status in database
        db.systems.update_one(
            {'_id': ObjectId(system_id)},
            {'$set': {
                'status': status,
                'last_checked': datetime.utcnow()
            }}
        )
        
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        logger.error(f"Get system status error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/import_data', methods=['POST'])
def process_import_data(data=None):
    try:
        if data is None:
            data = request.get_json()
        db = get_db()
        
        # First, process teams
        team_map = {}  # Map old team IDs to new team IDs
        for team_data in data.get('teams', []):
            # Check if team already exists
            existing_team = db.teams.find_one({'name': team_data['name']})
            if existing_team:
                team_map[team_data['_id']] = str(existing_team['_id'])
            else:
                team = Team(name=team_data['name'])
                result = db.teams.insert_one(team.to_dict())
                team_map[team_data['_id']] = str(result.inserted_id)
        
        # Process applications
        app_map = {}  # Map old app IDs to new app IDs
        for app_data in data.get('applications', []):
            try:
                # Map team ID if it exists
                if app_data.get('team_id'):
                    app_data['team_id'] = team_map.get(app_data['team_id'])
                
                # Check if application already exists
                existing_app = db.applications.find_one({'name': app_data['name']})
                if existing_app:
                    app_map[app_data['_id']] = str(existing_app['_id'])
                    continue
                
                app = Application(
                    name=app_data['name'],
                    team_id=app_data.get('team_id')
                )
                app_dict = app.to_dict()
                app_dict['_id'] = ObjectId()  # Explicitly set ObjectId
                result = db.applications.insert_one(app_dict)
                app_map[app_data['_id']] = str(result.inserted_id)
                
            except Exception as e:
                logger.error(f"Error importing application {app_data.get('name')}: {str(e)}")
                continue
        
        # Process instances
        for instance_data in data.get('instances', []):
            try:
                # Map application ID
                new_app_id = app_map.get(instance_data['application_id'])
                if not new_app_id:
                    continue
                
                # Check if instance already exists
                existing_instance = db.application_instances.find_one({
                    'application_id': new_app_id,
                    'host': instance_data['host']
                })
                if existing_instance:
                    continue
                
                instance = ApplicationInstance(
                    application_id=new_app_id,
                    host=instance_data['host'],
                    port=instance_data.get('port'),
                    webui_url=instance_data.get('webui_url'),
                    db_host=instance_data.get('db_host')
                )
                db.application_instances.insert_one(instance.to_dict())
                
            except Exception as e:
                logger.error(f"Error importing instance {instance_data.get('host')}: {str(e)}")
                continue
        
        return jsonify({"message": "Import completed successfully"}), 200
        
    except Exception as e:
        logger.error(f"Import error: {str(e)}")
        return jsonify({"error": str(e)}), 400

@main.route('/delete_instance/<int:instance_id>', methods=['POST'])
def delete_instance(instance_id):
    try:
        db = get_db()
        instance = db.application_instances.find_one({'_id': ObjectId(instance_id)})
        if not instance:
            return jsonify({'status': 'error', 'message': 'Instance not found'}), 404
        
        db.application_instances.delete_one({'_id': instance['_id']})
        
        # Check if this was the last instance
        remaining_instances = db.application_instances.find({'application_id': instance['application_id']}).count()
        if remaining_instances == 0:
            # If no instances left, delete the application too
            app = db.applications.find_one({'_id': instance['application_id']})
            if app:
                db.applications.delete_one({'_id': app['_id']})
        
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in delete_instance: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/applications/<app_id>', methods=['DELETE'])
def delete_application_api(app_id):
    try:
        db = get_db()
        
        # Delete all systems belonging to this application
        db.systems.delete_many({'application_id': str(app_id)})
        
        # Delete the application
        db.applications.delete_one({'_id': ObjectId(app_id)})
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Delete application error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main.route('/update_instance_url/<int:instance_id>', methods=['POST'])
def update_instance_url(instance_id):
    try:
        db = get_db()
        instance = db.application_instances.find_one({'_id': ObjectId(instance_id)})
        if not instance:
            return jsonify({'status': 'error', 'message': 'Instance not found'}), 404
        
        data = request.get_json()
        db.application_instances.update_one(
            {'_id': instance['_id']},
            {'$set': {'webui_url': data.get('url', '')}}
        )
        return jsonify({
            'status': 'success',
            'message': 'URL updated successfully',
            'instance': {
                'id': instance['_id'],
                'url': instance['webui_url'],
                'host': instance['host'],
                'application_id': instance['application_id']
            }
        })
    except Exception as e:
        logger.error(f"Error in update_instance_url: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/update_system_info', methods=['POST'])
def update_system():
    try:
        db = get_db()
        data = request.get_json()
        system_id = data.get('id')
        new_name = data.get('name')
        new_team = data.get('team')
        
        instance = db.application_instances.find_one({'_id': ObjectId(system_id)})
        if not instance:
            return jsonify({'status': 'error', 'message': 'Instance not found'}), 404
        
        db.application_instances.update_one(
            {'_id': instance['_id']},
            {'$set': {'host': new_name}}
        )
        
        # Update team if it exists, create if it doesn't
        team = db.teams.find_one({'name': new_team})
        if not team:
            team = {'name': new_team}
            db.teams.insert_one(team)
        
        application = db.applications.find_one({'_id': instance['application_id']})
        if application:
            db.applications.update_one(
                {'_id': application['_id']},
                {'$set': {'team_id': team['_id']}}
            )
        
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in update_system: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/get_all_systems')
def get_all_systems():
    try:
        db = get_db()
        
        pipeline = [
            {
                '$lookup': {
                    'from': 'applications',
                    'localField': 'application_id',
                    'foreignField': '_id',
                    'as': 'application'
                }
            },
            {
                '$unwind': '$application'
            },
            {
                '$lookup': {
                    'from': 'teams',
                    'localField': 'application.team_id',
                    'foreignField': '_id',
                    'as': 'team'
                }
            },
            {
                '$unwind': '$team'
            },
            {
                '$sort': {
                    'team.name': 1,
                    'application.name': 1
                }
            }
        ]
        
        instances = list(db.application_instances.aggregate(pipeline))
        
        # Format the response
        systems = [{
            'id': instance['_id'],
            'name': instance['host'],
            'team': instance['team']['name'],
            'application_id': instance['application_id']
        } for instance in instances]
        
        return jsonify({
            'status': 'success',
            'systems': systems
        })
    except Exception as e:
        logger.error(f"Error in get_all_systems: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/update_application', methods=['POST'])
def update_application():
    try:
        db = get_db()
        data = request.get_json()
        app_id = data.get('id')
        new_name = data.get('name')
        new_team = data.get('team')
        instances = data.get('instances', [])
        
        # Get application
        application = db.applications.find_one({'_id': ObjectId(app_id)})
        if not application:
            return jsonify({'status': 'error', 'message': 'Application not found'}), 404
        
        # Update team if it exists, create if it doesn't
        team = db.teams.find_one({'name': new_team})
        if not team:
            team = {'name': new_team}
            db.teams.insert_one(team)
        
        # Update application
        db.applications.update_one(
            {'_id': application['_id']},
            {'$set': {'name': new_name, 'team_id': team['_id']}}
        )
        
        # Update instances if provided
        if instances:
            # Delete removed instances
            current_instance_ids = [i.get('id') for i in instances if i.get('id')]
            db.application_instances.delete_many({
                'application_id': application['_id'],
                '_id': {'$not': {'$in': [ObjectId(i) for i in current_instance_ids]}}
            })
            
            # Update/create instances
            for instance_data in instances:
                instance_id = instance_data.get('id')
                if instance_id:
                    instance = db.application_instances.find_one({'_id': ObjectId(instance_id)})
                    if instance:
                        db.application_instances.update_one(
                            {'_id': instance['_id']},
                            {'$set': instance_data}
                        )
                else:
                    instance = {
                        'application_id': application['_id'],
                        'host': instance_data.get('host'),
                        'port': instance_data.get('port'),
                        'webui_url': instance_data.get('webui_url'),
                        'db_host': instance_data.get('db_host')
                    }
                    db.application_instances.insert_one(instance)
        
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in update_application: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/applications/<app_id>', methods=['GET'])
def get_application(app_id):
    try:
        db = get_db()
        app = db.applications.find_one({"_id": ObjectId(app_id)})
        if app:
            return jsonify(Application.from_dict(app).to_dict())
        return jsonify({"error": "Application not found"}), 404
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/applications/<app_id>/run-tests', methods=['POST'])
def run_application_tests(app_id):
    db = get_db()
    try:
        app = db.applications.find_one({'_id': ObjectId(app_id)})
        if not app:
            return jsonify({'error': 'Application not found'}), 404
            
        # Queue test job in test runner container
        test_job = {
            'app_id': str(app_id),
            'status': 'pending',
            'created_at': datetime.utcnow()
        }
        db.test_jobs.insert_one(test_job)
        
        return jsonify({'status': 'success', 'message': 'Test job queued'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications/<app_id>/test-results')
def get_test_results(app_id):
    db = get_db()
    try:
        results = list(db.test_results.find({'app_id': str(app_id)}).sort('created_at', -1).limit(1))
        if not results:
            return jsonify({'results': []})
            
        return jsonify({'results': results[0].get('results', [])})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/systems')
def get_systems():
    try:
        db = get_db()
        systems = []
        for system in db.systems.find():
            app = db.applications.find_one({'_id': ObjectId(system['application_id'])})
            if app:
                team = db.teams.find_one({'_id': ObjectId(app['team_id'])})
                systems.append({
                    'id': str(system['_id']),
                    'name': system.get('name', system['host']),
                    'host': system['host'],
                    'status': system.get('status', 'unknown'),
                    'last_checked': system.get('last_checked', datetime.utcnow()),
                    'port': system.get('port'),
                    'webui_url': system.get('webui_url'),
                    'application': {
                        'id': str(app['_id']),
                        'name': app['name']
                    },
                    'team': {
                        'id': str(team['_id']) if team else None,
                        'name': team['name'] if team else 'Unknown'
                    } if team else None
                })
        return jsonify(systems)
    except Exception as e:
        logger.error(f"Error getting systems: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/api/systems/<system_id>/status', methods=['POST'])
def update_system_status(system_id):
    try:
        data = request.get_json()
        status = data.get('status')
        if status not in ['running', 'stopped']:
            return jsonify({'status': 'error', 'message': 'Invalid status'}), 400
            
        db = get_db()
        result = db.systems.update_one(
            {'_id': ObjectId(system_id)},
            {'$set': {
                'status': status,
                'last_checked': datetime.utcnow()
            }}
        )
        
        if result.modified_count == 0:
            return jsonify({'status': 'error', 'message': 'System not found'}), 404
            
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Update system status error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

@main.route('/api/applications/<app_id>/state', methods=['POST'])
def update_application_state(app_id):
    db = get_db()
    data = request.get_json()
    new_state = data.get('state')
    
    try:
        if new_state not in ['notStarted', 'inProgress', 'completed']:
            return jsonify({'error': 'Invalid state'}), 400
            
        # Update application state
        result = db.applications.update_one(
            {'_id': ObjectId(app_id)},
            {'$set': {
                'state': new_state,
                'updated_at': datetime.utcnow()
            }}
        )
        
        if result.modified_count == 0:
            return jsonify({'error': 'Application not found'}), 404
            
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in update_application_state: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications/<app_id>/toggle', methods=['POST'])
def toggle_application(app_id):
    db = get_db()
    data = request.get_json()
    enabled = data.get('enabled', False)
    
    try:
        # Update application
        result = db.applications.update_one(
            {'_id': ObjectId(app_id)},
            {'$set': {
                'enabled': enabled,
                'updated_at': datetime.utcnow()
            }}
        )
        
        if result.modified_count == 0:
            return jsonify({'error': 'Application not found'}), 404
        
        # Update all associated systems
        status = 'running' if enabled else 'stopped'
        db.systems.update_many(
            {'application_id': str(app_id)},
            {'$set': {
                'status': status,
                'last_checked': datetime.utcnow()
            }}
        )
        
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in toggle_application: {str(e)}")
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications/states')
def get_application_states():
    db = get_db()
    applications = []
    for app in db.applications.find():
        applications.append({
            '_id': str(app['_id']),
            'state': app.get('state', 'notStarted')
        })
    return jsonify(applications)

@main.route('/api/applications/<app_id>/instances', methods=['POST'])
def add_instance(app_id):
    try:
        data = request.get_json()
        db = get_db()
        
        # Verify application exists
        app = db.applications.find_one({'_id': ObjectId(app_id)})
        if not app:
            return jsonify({"error": "Application not found"}), 404
        
        instance = ApplicationInstance(
            application_id=str(app['_id']),  # Convert ObjectId to string
            host=data['host'],
            port=data.get('port'),
            webui_url=data.get('webui_url'),
            db_host=data.get('db_host')
        )
        
        result = db.application_instances.insert_one(instance.to_dict())
        return jsonify({"message": "Instance added successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        logger.error(f"Error adding instance: {str(e)}")
        return jsonify({"error": str(e)}), 400

@main.route('/api/applications/<app_id>/instances', methods=['GET'])
def list_instances(app_id):
    try:
        db = get_db()
        instances = list(db.application_instances.find({"application_id": app_id}))
        return jsonify([ApplicationInstance.from_dict(inst).to_dict() for inst in instances])
    except Exception as e:
        logger.error(f"Error listing instances: {str(e)}")
        return jsonify({"error": str(e)}), 500

@main.route('/api/applications', methods=['GET'])
def list_applications():
    try:
        db = get_db()
        applications = [Application.from_dict(app) for app in db.applications.find()]
        return jsonify([app.to_dict() for app in applications])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/teams', methods=['GET'])
def list_teams():
    try:
        db = get_db()
        teams = [Team.from_dict(team) for team in db.teams.find()]
        return jsonify([team.to_dict() for team in teams])
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/teams', methods=['POST'])
def create_team():
    try:
        data = request.json
        if not data or 'name' not in data:
            return jsonify({'success': False, 'error': 'Team name is required'})
            
        db = get_db()
        team = db.teams.find_one_and_update(
            {'name': data['name']},
            {'$set': {'name': data['name']}},
            upsert=True,
            return_document=True
        )
        
        return jsonify({'success': True, 'team': {'id': str(team['_id']), 'name': team['name']}})
    except Exception as e:
        logger.error(f"Create team error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/applications', methods=['POST'])
def create_application():
    try:
        data = request.json
        if not data or 'name' not in data or 'team_id' not in data:
            return jsonify({'success': False, 'error': 'Application name and team ID are required'})
            
        db = get_db()
        app_data = {
            'name': data['name'],
            'team_id': data['team_id'],
            'shutdown_order': int(data.get('shutdown_order', 0)),
            'dependencies': data.get('dependencies', [])
        }
        
        app = db.applications.find_one_and_update(
            {'name': data['name'], 'team_id': data['team_id']},
            {'$set': app_data},
            upsert=True,
            return_document=True
        )
        
        return jsonify({'success': True, 'application': {
            'id': str(app['_id']),
            'name': app['name'],
            'team_id': app['team_id'],
            'shutdown_order': app['shutdown_order'],
            'dependencies': app['dependencies']
        }})
    except Exception as e:
        logger.error(f"Create application error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/systems', methods=['POST'])
def create_system():
    try:
        data = request.json
        if not data or 'host' not in data or 'application_id' not in data:
            return jsonify({'success': False, 'error': 'Host and application ID are required'})
            
        db = get_db()
        system_data = {
            'name': data.get('name', data['host']),  # Use host as name if not provided
            'application_id': data['application_id'],
            'host': data['host'],
            'port': int(data['port']) if data.get('port') else None,
            'webui_url': data.get('webui_url'),
            'status': 'unknown',
            'last_checked': datetime.utcnow()
        }
        
        system = db.systems.find_one_and_update(
            {'host': data['host']},
            {'$set': system_data},
            upsert=True,
            return_document=True
        )
        
        return jsonify({'success': True, 'system': {
            'id': str(system['_id']),
            'name': system['name'],
            'application_id': system['application_id'],
            'host': system['host'],
            'port': system['port'],
            'webui_url': system.get('webui_url'),
            'status': system['status']
        }})
    except Exception as e:
        logger.error(f"Create system error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/teams/<team_id>', methods=['DELETE'])
def delete_team_api(team_id):
    try:
        db = get_db()
        
        # Get all applications for this team
        applications = list(db.applications.find({'team_id': str(team_id)}))
        app_ids = [str(app['_id']) for app in applications]
        
        # Delete all systems belonging to these applications
        db.systems.delete_many({'application_id': {'$in': app_ids}})
        
        # Delete all applications
        db.applications.delete_many({'team_id': str(team_id)})
        
        # Delete the team
        db.teams.delete_one({'_id': ObjectId(team_id)})
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Delete team error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@main.route('/api/systems/<system_id>', methods=['DELETE'])
def delete_system_api(system_id):
    try:
        db = get_db()
        db.systems.delete_one({'_id': ObjectId(system_id)})
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Delete system error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})
