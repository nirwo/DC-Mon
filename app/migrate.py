import psycopg2
from pymongo import MongoClient
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def migrate_data():
    try:
        # Connect to PostgreSQL
        pg_conn = psycopg2.connect(
            dbname=os.environ.get('POSTGRES_DB', 'dcmon'),
            user=os.environ.get('POSTGRES_USER', 'postgres'),
            password=os.environ.get('POSTGRES_PASSWORD', 'postgres'),
            host=os.environ.get('POSTGRES_HOST', 'localhost')
        )
        pg_cur = pg_conn.cursor()

        # Connect to MongoDB
        mongo_uri = os.environ.get('MONGODB_URI', 'mongodb://mongo:27017/shutdown_manager')
        mongo_client = MongoClient(mongo_uri)
        mongo_db = mongo_client.get_database()

        # Migrate teams
        logger.info("Migrating teams...")
        pg_cur.execute("SELECT id, name FROM teams")
        teams = pg_cur.fetchall()
        for team_id, team_name in teams:
            try:
                mongo_db.teams.insert_one({
                    '_id': str(team_id),
                    'name': team_name
                })
                logger.info(f"Migrated team: {team_name}")
            except Exception as e:
                logger.warning(f"Team already exists or error: {e}")

        # Migrate applications
        logger.info("Migrating applications...")
        pg_cur.execute("SELECT id, name, team_id FROM applications")
        apps = pg_cur.fetchall()
        for app_id, app_name, team_id in apps:
            try:
                mongo_db.applications.insert_one({
                    '_id': str(app_id),
                    'name': app_name,
                    'team_id': str(team_id) if team_id else None
                })
                logger.info(f"Migrated application: {app_name}")
            except Exception as e:
                logger.warning(f"Application already exists or error: {e}")

        # Migrate application instances
        logger.info("Migrating application instances...")
        pg_cur.execute("SELECT id, application_id, host, port, webui_url, db_host FROM application_instances")
        instances = pg_cur.fetchall()
        for instance_id, app_id, host, port, webui_url, db_host in instances:
            try:
                mongo_db.application_instances.insert_one({
                    '_id': str(instance_id),
                    'application_id': str(app_id),
                    'host': host,
                    'port': port,
                    'webui_url': webui_url,
                    'db_host': db_host
                })
                logger.info(f"Migrated instance: {host}:{port}")
            except Exception as e:
                logger.warning(f"Instance already exists or error: {e}")

        logger.info("Migration completed successfully")
        
    except Exception as e:
        logger.error(f"Migration failed: {e}")
        raise
    finally:
        if 'pg_cur' in locals():
            pg_cur.close()
        if 'pg_conn' in locals():
            pg_conn.close()
        if 'mongo_client' in locals():
            mongo_client.close()

if __name__ == '__main__':
    migrate_data()
