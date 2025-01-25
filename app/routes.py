from flask import Blueprint, jsonify, request, render_template
from .models import db, Team, Application, System

main = Blueprint('main', __name__)

@main.route('/')
def index():
    return render_template('index.html')

@main.route('/api/teams', methods=['GET'])
def get_teams():
    teams = Team.query.all()
    return jsonify([team.to_dict() for team in teams])

@main.route('/api/teams', methods=['POST'])
def create_team():
    data = request.get_json()
    team = Team(name=data['name'])
    db.session.add(team)
    db.session.commit()
    return jsonify(team.to_dict())

@main.route('/api/teams/<int:team_id>', methods=['DELETE'])
def delete_team(team_id):
    team = Team.query.get_or_404(team_id)
    db.session.delete(team)
    db.session.commit()
    return '', 204

@main.route('/api/applications', methods=['GET'])
def get_applications():
    apps = Application.query.all()
    return jsonify([app.to_dict() for app in apps])

@main.route('/api/applications', methods=['POST'])
def create_application():
    data = request.get_json()
    
    # Create application
    app = Application(
        name=data['name'],
        team_id=data['team_id'],
        description=data.get('description', ''),
        webui_url=data.get('webui_url', '')
    )
    db.session.add(app)
    db.session.flush()
    
    # Create and link system
    system = System(
        name=f"{data['name']}-system",
        host=data['host'],
        port=data.get('port', 80),
        status='running'
    )
    db.session.add(system)
    db.session.flush()
    
    app.systems.append(system)
    db.session.commit()
    
    return jsonify(app.to_dict())

@main.route('/api/applications/<int:app_id>', methods=['DELETE'])
def delete_application(app_id):
    app = Application.query.get_or_404(app_id)
    db.session.delete(app)
    db.session.commit()
    return '', 204

@main.route('/api/applications/<int:app_id>', methods=['PUT'])
def update_application(app_id):
    app = Application.query.get_or_404(app_id)
    data = request.get_json()
    app.name = data.get('name', app.name)
    if 'team_id' in data:
        app.team_id = data['team_id']
    if 'description' in data:
        app.description = data['description']
    if 'webui_url' in data:
        app.webui_url = data['webui_url']
    db.session.commit()
    return jsonify({'message': 'Application updated successfully'})

@main.route('/api/applications/<int:app_id>/systems', methods=['GET'])
def get_application_systems(app_id):
    app = Application.query.get_or_404(app_id)
    return jsonify([system.to_dict() for system in app.systems])

@main.route('/api/systems', methods=['GET'])
def get_systems():
    systems = System.query.all()
    return jsonify([system.to_dict() for system in systems])

@main.route('/api/systems', methods=['POST'])
def create_system():
    data = request.get_json()
    system = System(
        name=data['name'],
        host=data['host'],
        port=data.get('port', 80),
        status=data.get('status', 'unknown')
    )
    db.session.add(system)
    db.session.commit()
    return jsonify(system.to_dict())

@main.route('/api/systems/<int:system_id>', methods=['DELETE'])
def delete_system(system_id):
    system = System.query.get_or_404(system_id)
    db.session.delete(system)
    db.session.commit()
    return jsonify({'message': 'System deleted successfully'})

@main.route('/preview_csv', methods=['POST'])
def preview_csv():
    if 'file' not in request.files:
        return jsonify({"error": "No file provided"}), 400
    
    file = request.files['file']
    if not file.filename.endswith('.csv'):
        return jsonify({"error": "Invalid file format. Please upload a CSV file"}), 400
    
    # Create a temporary file to store the uploaded content
    with tempfile.NamedTemporaryFile(mode='wb', delete=False) as temp_file:
        file.save(temp_file.name)
        
        # Read CSV headers and preview data
        with open(temp_file.name, 'r') as csvfile:
            reader = csv.DictReader(csvfile)
            headers = reader.fieldnames
            preview = []
            for i, row in enumerate(reader):
                if i >= 5:  # Only show first 5 rows
                    break
                preview.append(row)
        
        os.unlink(temp_file.name)
        
        required_fields = ['name', 'team', 'host', 'port']
        optional_fields = ['webui_url', 'db_host', 'description']
        
        return jsonify({
            "headers": headers,
            "preview": preview,
            "required_fields": required_fields,
            "optional_fields": optional_fields
        })

@main.route('/import_apps', methods=['POST'])
def import_apps():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
    
    file = request.files['file']
    if not file or not file.filename.endswith('.csv'):
        return jsonify({'error': 'Invalid file format. Please upload a CSV file'}), 400

    try:
        content = file.stream.read().decode("UTF8")
        if not content.strip():
            return jsonify({'error': 'CSV file is empty'}), 400
            
        stream = StringIO(content)
        csv_input = csv.DictReader(stream)
        
        if not csv_input.fieldnames:
            return jsonify({'error': 'CSV file has no headers'}), 400
        
        required_fields = ['name', 'team_name', 'host']
        missing_headers = [field for field in required_fields if field not in csv_input.fieldnames]
        if missing_headers:
            return jsonify({
                'error': f'Missing required columns: {", ".join(missing_headers)}',
                'required': required_fields
            }), 400
        
        # Clean existing data
        try:
            ApplicationInstance.query.delete()
            Application.query.delete()
            Team.query.delete()
            db.session.commit()
        except Exception as e:
            db.session.rollback()
            return jsonify({'error': f'Failed to clean existing data: {str(e)}'}), 500
        
        imported = 0
        skipped = 0
        errors = []
        
        for row_num, row in enumerate(csv_input, start=2):
            try:
                # Validate required fields
                missing_fields = [field for field in required_fields if not row.get(field, '').strip()]
                if missing_fields:
                    errors.append(f"Row {row_num}: Missing values for {', '.join(missing_fields)}")
                    skipped += 1
                    continue

                # Find or create team
                team_name = row['team_name'].strip()
                team = Team.query.filter_by(name=team_name).first()
                if not team:
                    team = Team(name=team_name)
                    db.session.add(team)
                    db.session.flush()

                # Create application
                app = Application(
                    name=row['name'].strip(),
                    team_id=team.id
                )
                db.session.add(app)
                db.session.flush()

                # Create instance with validation
                port = row.get('port', '').strip()
                instance = ApplicationInstance(
                    application_id=app.id,
                    host=row['host'].strip(),
                    port=int(port) if port.isdigit() else None,
                    webui_url=row.get('webui_url', '').strip() or None,
                    db_host=row.get('db_host', '').strip() or None,
                    status='unknown'  # Default to unknown, will be updated by monitoring
                )
                db.session.add(instance)
                imported += 1

            except ValueError as ve:
                errors.append(f"Row {row_num}: Invalid value - {str(ve)}")
                skipped += 1
            except Exception as e:
                errors.append(f"Row {row_num}: {str(e)}")
                skipped += 1
                continue

        if imported > 0:
            db.session.commit()
        else:
            db.session.rollback()
            return jsonify({'error': 'No valid records to import', 'errors': errors}), 400
        
        return jsonify({
            'imported': imported,
            'skipped': skipped,
            'message': f'Successfully imported {imported} applications',
            'errors': errors if errors else None
        })

    except UnicodeDecodeError:
        return jsonify({'error': 'Invalid file encoding. Please use UTF-8'}), 400
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@main.route('/shutdown_app/<int:app_id>', methods=['POST'])
def shutdown_app(app_id):
    try:
        app = Application.query.get_or_404(app_id)
        instances = ApplicationInstance.query.filter_by(application_id=app_id).all()
        
        for instance in instances:
            instance.status = 'in_progress'
            db.session.add(instance)
        
        app.state = 'completed'
        db.session.add(app)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Application shutdown in progress'
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500