import os
import pytest
import tempfile
from app import create_app, db
from app.models import Application, Team, ApplicationInstance

@pytest.fixture
def client():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.drop_all()

def test_index(client):
    """Test the index page loads"""
    rv = client.get('/')
    assert rv.status_code == 200
    assert b'Applications' in rv.data

def test_import_apps(client):
    """Test importing applications from CSV"""
    # Create a test team
    team = Team(name='Test Team')
    db.session.add(team)
    db.session.commit()
    
    # Create test CSV content
    csv_content = 'name,team,host,port,webui_url,db_host\n'
    csv_content += 'TestApp,Test Team,localhost,8080,http://localhost:8080,db.local\n'
    
    # Create temporary file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False) as f:
        f.write(csv_content)
        f.flush()
        
        # Test file upload
        with open(f.name, 'rb') as test_file:
            rv = client.post('/import_apps', 
                           data={'file': (test_file, 'test.csv')},
                           content_type='multipart/form-data')
            
        # Clean up temp file
        os.unlink(f.name)
    
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['imported'] == 1
    assert data['skipped'] == 0
    
    # Verify database state
    app = Application.query.filter_by(name='TestApp').first()
    assert app is not None
    assert app.team.name == 'Test Team'
    assert len(app.instances) == 1
    
    instance = app.instances[0]
    assert instance.host == 'localhost'
    assert instance.port == 8080
    assert instance.webui_url == 'http://localhost:8080'
    assert instance.db_host == 'db.local'

def test_check_status(client):
    """Test checking application status"""
    # Create test data
    team = Team(name='Test Team')
    db.session.add(team)
    db.session.commit()
    
    app = Application(name='TestApp', team_id=team.id)
    db.session.add(app)
    db.session.commit()
    
    instance = ApplicationInstance(
        application_id=app.id,
        host='localhost',
        port=8080
    )
    db.session.add(instance)
    db.session.commit()
    
    # Test status check
    rv = client.get(f'/check_status/{app.id}')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['status'] == 'success'
    assert len(data['results']) == 1
    assert 'status' in data['results'][0]

def test_update_application(client):
    """Test updating application details"""
    # Create test data
    team1 = Team(name='Team 1')
    team2 = Team(name='Team 2')
    db.session.add_all([team1, team2])
    db.session.commit()
    
    app = Application(name='TestApp', team_id=team1.id)
    db.session.add(app)
    db.session.commit()
    
    instance = ApplicationInstance(
        application_id=app.id,
        host='localhost',
        port=8080
    )
    db.session.add(instance)
    db.session.commit()
    
    # Test update
    update_data = {
        'name': 'UpdatedApp',
        'team_id': team2.id,
        'instances': [{
            'id': instance.id,
            'host': 'newhost',
            'port': 9090,
            'webui_url': 'http://newhost:9090',
            'db_host': 'newdb.local'
        }]
    }
    
    rv = client.post(f'/update_application/{app.id}',
                    json=update_data,
                    content_type='application/json')
    
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['status'] == 'success'
    
    # Verify database state
    app = Application.query.get(app.id)
    assert app.name == 'UpdatedApp'
    assert app.team_id == team2.id
    assert len(app.instances) == 1
    
    instance = app.instances[0]
    assert instance.host == 'newhost'
    assert instance.port == 9090
    assert instance.webui_url == 'http://newhost:9090'
    assert instance.db_host == 'newdb.local'

def test_shutdown_app(client):
    """Test shutting down an application"""
    # Create test data
    team = Team(name='Test Team')
    db.session.add(team)
    db.session.commit()
    
    app = Application(name='TestApp', team_id=team.id)
    db.session.add(app)
    db.session.commit()
    
    instance = ApplicationInstance(
        application_id=app.id,
        host='localhost',
        port=8080
    )
    db.session.add(instance)
    db.session.commit()
    
    # Test shutdown
    rv = client.post(f'/shutdown_app/{app.id}')
    assert rv.status_code == 200
    data = rv.get_json()
    assert data['status'] == 'success'
    
    # Verify instance status
    instance = ApplicationInstance.query.get(instance.id)
    assert instance.status == 'in_progress'
