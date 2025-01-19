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
    applications = [Application.from_dict(app) for app in db.applications.find()]
    teams = [Team.from_dict(team) for team in db.teams.find()]
    return render_template('applications.html', applications=applications, teams=teams)

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
    instances = [ApplicationInstance.from_dict(inst) for inst in db.instances.aggregate(pipeline)]
    return render_template('systems.html', instances=instances)

@main.route('/check_all_status')
def check_all_status():
    try:
        logger.info("Starting check_all_status")
        db = get_db()
        
        instances = db.instances.find()
        for instance_data in instances:
            try:
                instance = ApplicationInstance.from_dict(instance_data)
                instance.status = 'checking'
                instance.details = 'Status check initiated'
                instance.last_checked = datetime.utcnow()
                
                db.instances.update_one(
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
        
        instance_data = db.instances.find_one({'_id': ObjectId(instance_id)})
        if not instance_data:
            return jsonify({'status': 'error', 'message': 'Instance not found'}), 404
        
        instance = ApplicationInstance.from_dict(instance_data)
        instance.status = 'checking'
        instance.details = 'Status check initiated'
        instance.last_checked = datetime.utcnow()
        
        db.instances.update_one(
            {'_id': instance._id},
            {'$set': instance.to_dict()}
        )
        logger.info(f"Updated instance {instance_id} status to checking")
        
        return jsonify({'status': 'success', 'message': 'Status check initiated'})
    except Exception as e:
        logger.error(f"Error in check_status: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)})

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
        
        db = get_db()
        
        # First create teams
        for team_data in data.get('teams', []):
            if not isinstance(team_data, dict) or 'name' not in team_data:
                continue
                
            team = db.teams.find_one({'name': team_data['name']})
            if not team:
                db.teams.insert_one(team_data)
        
        # Then create applications and instances
        for app_data in data.get('applications', []):
            if not isinstance(app_data, dict) or 'name' not in app_data or 'team' not in app_data:
                continue
                
            team = db.teams.find_one({'name': app_data['team']})
            if not team:
                continue
                
            app = db.applications.find_one({'name': app_data['name'], 'team_id': team['_id']})
            if not app:
                app = {
                    'name': app_data['name'],
                    'team_id': team['_id']
                }
                db.applications.insert_one(app)
            
            for instance_data in app_data.get('instances', []):
                if not isinstance(instance_data, dict) or 'host' not in instance_data:
                    continue
                    
                instance = db.instances.find_one({
                    'application_id': app['_id'],
                    'host': instance_data['host']
                })
                
                if not instance:
                    instance = {
                        'application_id': app['_id'],
                        'host': instance_data['host'],
                        'port': instance_data.get('port'),
                        'webui_url': instance_data.get('webui_url'),
                        'db_host': instance_data.get('db_host'),
                        'status': 'unknown'
                    }
                    db.instances.insert_one(instance)
                else:
                    db.instances.update_one(
                        {'_id': instance['_id']},
                        {'$set': instance_data}
                    )
        
        return jsonify({'status': 'success', 'message': 'Data imported successfully'})
        
    except Exception as e:
        logger.error(f"Error in import_data: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': f'Import failed: {str(e)}'
        }), 500

@main.route('/delete_instance/<int:instance_id>', methods=['POST'])
def delete_instance(instance_id):
    try:
        db = get_db()
        instance = db.instances.find_one({'_id': ObjectId(instance_id)})
        if not instance:
            return jsonify({'status': 'error', 'message': 'Instance not found'}), 404
        
        db.instances.delete_one({'_id': instance['_id']})
        
        # Check if this was the last instance
        remaining_instances = db.instances.find({'application_id': instance['application_id']}).count()
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
        db.instances.delete_many({'application_id': app['_id']})
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
        instance = db.instances.find_one({'_id': ObjectId(instance_id)})
        if not instance:
            return jsonify({'status': 'error', 'message': 'Instance not found'}), 404
        
        data = request.get_json()
        db.instances.update_one(
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
        
        instance = db.instances.find_one({'_id': ObjectId(system_id)})
        if not instance:
            return jsonify({'status': 'error', 'message': 'Instance not found'}), 404
        
        db.instances.update_one(
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
        
        instances = list(db.instances.aggregate(pipeline))
        
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
            db.instances.delete_many({
                'application_id': application['_id'],
                '_id': {'$not': {'$in': [ObjectId(i) for i in current_instance_ids]}}
            })
            
            # Update/create instances
            for instance_data in instances:
                instance_id = instance_data.get('id')
                if instance_id:
                    instance = db.instances.find_one({'_id': ObjectId(instance_id)})
                    if instance:
                        db.instances.update_one(
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
                    db.instances.insert_one(instance)
        
        return jsonify({'status': 'success'})
    except Exception as e:
        logger.error(f"Error in update_application: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500
