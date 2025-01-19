from datetime import datetime
import json
from flask import Blueprint, render_template, jsonify, request, current_app
from app.models import Team, Application, ApplicationInstance
from app.database import get_db
import csv
import requests
import logging
from bson import ObjectId

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

main = Blueprint('main', __name__)

@main.route('/')
def index():
    db = get_db()
    teams_data = list(db.teams.find())
    teams = []
    applications = []
    
    # Count applications per team
    for team_data in teams_data:
        team = Team.from_dict(team_data)
        app_count = db.applications.count_documents({"team_id": ObjectId(str(team._id))})
        team_dict = team.to_dict()
        team_dict['applications'] = app_count
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
        for system in db.systems.find({'application_id': str(app._id)}):
            systems.append({
                'id': str(system['_id']),
                'name': system['name'],
                'status': system.get('status', 'unknown'),
                'last_checked': system.get('last_checked')
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

@main.route('/import_data', methods=['POST'])
def import_data_file():
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
            data = {'teams': [], 'applications': [], 'instances': []}
            app_instances = {}
            
            for row in reader:
                team_name = row['team'].strip()
                app_name = row['name'].strip()
                key = f"{team_name}:{app_name}"
                
                if team_name not in [t['name'] for t in data['teams']]:
                    data['teams'].append({'_id': str(ObjectId()), 'name': team_name})
                
                if key not in app_instances:
                    app_instances[key] = {
                        '_id': str(ObjectId()),
                        'name': app_name,
                        'team_id': next(t['_id'] for t in data['teams'] if t['name'] == team_name)
                    }
                    data['applications'].append(app_instances[key])
                
                instance = {
                    'application_id': app_instances[key]['_id'],
                    'host': row['host'].strip(),
                    'port': int(row['port']) if 'port' in row and row['port'] else None,
                    'webui_url': row['webui_url'].strip() if 'webui_url' in row else None,
                    'db_host': row['db_host'].strip() if 'db_host' in row else None
                }
                data['instances'].append(instance)
            
        elif file.filename.endswith('.json'):
            # Handle JSON import
            content = file.read().decode('utf-8')
            data = json.loads(content)
            
        else:
            return jsonify({
                'status': 'error',
                'message': 'Invalid file format. Please upload a CSV or JSON file.'
            }), 400

        # Process the data using the API endpoint
        response = process_import_data(data)
        if response[1] == 200:  # Check if import was successful
            return jsonify({'status': 'success', 'message': 'Data imported successfully'})
        else:
            return jsonify({'status': 'error', 'message': response[0].get_json()['error']}), response[1]
        
    except Exception as e:
        logger.error(f"Error in import_data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Import failed: {str(e)}'
        }), 500

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

@main.route('/delete_application/<int:app_id>', methods=['POST'])
def delete_application(app_id):
    try:
        db = get_db()
        app = db.applications.find_one({'_id': ObjectId(app_id)})
        if not app:
            return jsonify({'status': 'error', 'message': 'Application not found'}), 404
        
        # Delete all instances first
        db.application_instances.delete_many({'application_id': app['_id']})
        # Then delete the application
        db.applications.delete_one({'_id': app['_id']})
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in delete_application: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

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

@main.route('/api/applications', methods=['POST'])
def create_application():
    try:
        data = request.get_json()
        db = get_db()
        
        app = Application(
            name=data['name'],
            team_id=data.get('team_id')
        )
        
        app_dict = app.to_dict()
        app_dict['_id'] = ObjectId()  # Explicitly set ObjectId
        
        result = db.applications.insert_one(app_dict)
        
        # Create instance if host is provided
        if 'host' in data:
            instance = ApplicationInstance(
                application_id=str(result.inserted_id),
                host=data['host'],
                port=data.get('port'),
                webui_url=data.get('webui_url'),
                db_host=data.get('db_host')
            )
            db.application_instances.insert_one(instance.to_dict())
        
        return jsonify({"message": "Application created successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

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
        data = request.get_json()
        db = get_db()
        
        team = Team(name=data['name'])
        result = db.teams.insert_one(team.to_dict())
        team._id = result.inserted_id
        
        return jsonify({"message": "Team created successfully", "id": str(result.inserted_id)}), 201
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@main.route('/api/teams/<team_id>', methods=['DELETE'])
def delete_team(team_id):
    try:
        db = get_db()
        
        # Check if team exists
        team = db.teams.find_one({'_id': ObjectId(team_id)})
        if not team:
            return jsonify({"error": "Team not found"}), 404
            
        # Check if team has applications
        if db.applications.find_one({'team_id': ObjectId(team_id)}):
            return jsonify({"error": "Cannot delete team with existing applications"}), 400
            
        db.teams.delete_one({'_id': ObjectId(team_id)})
        return jsonify({"message": "Team deleted successfully"}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@main.route('/api/applications/<app_id>/state', methods=['POST'])
def update_application_state(app_id):
    db = get_db()
    data = request.get_json()
    state = data.get('state')
    
    if state not in ['notStarted', 'inProgress', 'completed']:
        return jsonify({'error': 'Invalid state'}), 400
        
    try:
        db.applications.update_one(
            {'_id': ObjectId(app_id)},
            {'$set': {'state': state}}
        )
        return jsonify({'status': 'success'})
    except Exception as e:
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

@main.route('/api/applications/<app_id>/toggle', methods=['POST'])
def toggle_application(app_id):
    db = get_db()
    data = request.get_json()
    enabled = data.get('enabled', False)
    
    try:
        db.applications.update_one(
            {'_id': ObjectId(app_id)},
            {'$set': {'enabled': enabled}}
        )
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/applications/<app_id>/status')
def get_application_status(app_id):
    db = get_db()
    try:
        app = db.applications.find_one({'_id': ObjectId(app_id)})
        if not app:
            return jsonify({'error': 'Application not found'}), 404
            
        enabled = app.get('enabled', False)
        systems = []
        
        # Get associated systems
        for system in db.systems.find({'application_id': str(app_id)}):
            systems.append({
                'id': str(system['_id']),
                'name': system['name'],
                'status': system.get('status', 'unknown'),
                'last_checked': system.get('last_checked')
            })
        
        return jsonify({
            'status': 'running' if enabled else 'stopped',
            'systems': systems
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

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
    db = get_db()
    systems = []
    try:
        for system in db.systems.find():
            systems.append({
                'id': str(system['_id']),
                'name': system['name'],
                'status': system.get('status', 'unknown'),
                'last_checked': system.get('last_checked'),
                'application_id': str(system['application_id'])
            })
        return jsonify(systems)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@main.route('/api/systems/<system_id>/status', methods=['POST'])
def update_system_status(system_id):
    db = get_db()
    data = request.get_json()
    status = data.get('status')
    
    try:
        db.systems.update_one(
            {'_id': ObjectId(system_id)},
            {'$set': {
                'status': status,
                'last_checked': datetime.utcnow()
            }}
        )
        return jsonify({'status': 'success'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500
