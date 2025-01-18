from app import create_app, db
from app.models import Team, Application, ApplicationInstance

def init_db():
    app = create_app()
    with app.app_context():
        # Drop all tables
        db.drop_all()
        
        # Create tables
        db.create_all()
        
        # Create test teams
        team1 = Team(name='Team 1')
        team2 = Team(name='Team 2')
        db.session.add_all([team1, team2])
        db.session.commit()
        
        # Create test applications
        app1 = Application(name='App 1', team=team1)
        app2 = Application(name='App 2', team=team2)
        db.session.add_all([app1, app2])
        db.session.commit()
        
        # Create test instances
        instances = [
            ApplicationInstance(
                application=app1,
                host='host1.example.com',
                port=8080,
                webui_url='http://host1.example.com:8080',
                db_host='db1.example.com'
            ),
            ApplicationInstance(
                application=app1,
                host='host2.example.com',
                port=8081,
                webui_url='http://host2.example.com:8081',
                db_host='db2.example.com'
            ),
            ApplicationInstance(
                application=app2,
                host='host3.example.com',
                port=8082,
                webui_url='http://host3.example.com:8082',
                db_host='db3.example.com'
            )
        ]
        db.session.add_all(instances)
        db.session.commit()
        
        print("Database initialized with test data!")

if __name__ == '__main__':
    init_db()
