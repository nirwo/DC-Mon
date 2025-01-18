import pytest
from app import create_app, db
from app.models import Team, Application, ApplicationInstance
import io
import csv

@pytest.fixture
def app():
    app = create_app()
    app.config['TESTING'] = True
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    return app

@pytest.fixture
def client(app):
    with app.test_client() as client:
        with app.app_context():
            db.create_all()
            yield client
            db.session.remove()
            db.drop_all()

def create_test_csv():
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['name', 'team', 'host', 'port', 'webui_url', 'db_host', 'shutdown_order', 'dependencies'])
    writer.writerow(['App1', 'Team1', 'host1', '8080', 'http://host1:8080', 'db1', '1', ''])
    writer.writerow(['App2', 'Team1', 'host2', '8081', 'http://host2:8081', 'db2', '2', 'App1'])
    return output.getvalue()

def test_import_apps(client):
    # Create test CSV file
    csv_data = create_test_csv()
    data = {
        'file': (io.BytesIO(csv_data.encode()), 'test.csv'),
        'merge_mode': 'replace'
    }
    
    # Test file upload
    response = client.post('/import_apps', data=data, content_type='multipart/form-data')
    assert response.status_code == 200
    
    # Verify response
    json_data = response.get_json()
    assert json_data['imported'] == 2
    assert json_data['updated'] == 0
    assert json_data['skipped'] == 0
    
    # Verify database state
    apps = Application.query.all()
    assert len(apps) == 2
    
    app1 = Application.query.filter_by(name='App1').first()
    assert app1 is not None
    assert app1.team.name == 'Team1'
    assert len(app1.instances) == 1
    assert app1.instances[0].host == 'host1'
    assert app1.instances[0].port == '8080'
    
    app2 = Application.query.filter_by(name='App2').first()
    assert app2 is not None
    assert len(app2.instances) == 1
    assert app2.instances[0].host == 'host2'

def test_view_systems(client):
    # Create test data
    team = Team(name='Test Team')
    app = Application(name='Test App', team=team)
    instance = ApplicationInstance(
        host='test.host',
        port='8080',
        webui_url='http://test.host:8080',
        db_host='db.host'
    )
    app.instances.append(instance)
    
    with client.application.app_context():
        db.session.add(team)
        db.session.add(app)
        db.session.commit()
    
    # Test systems view
    response = client.get('/systems')
    assert response.status_code == 200
