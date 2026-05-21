import psycopg2
from config import PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE

def get_db_connection():
    conn = psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        user=PGUSER,
        password=PGPASSWORD,
        database=PGDATABASE
    )
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()

    # Table des clés
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            owner_discord_id TEXT,
            hwid TEXT,
            project_name TEXT DEFAULT 'FunHub',
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            uses INTEGER DEFAULT 0
        )
    ''')

    # Table des utilisateurs whitelistés
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS whitelist (
            discord_id TEXT PRIMARY KEY,
            username TEXT,
            key TEXT REFERENCES keys(key),
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE
        )
    ''')

    # Table des projets (pour plusieurs scripts)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            name TEXT PRIMARY KEY,
            owner_discord_id TEXT,
            script_content TEXT,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_keys INTEGER DEFAULT 0,
            active_keys INTEGER DEFAULT 0
        )
    ''')

    # Table des statistiques
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            id SERIAL PRIMARY KEY,
            project_name TEXT,
            action TEXT,  -- "redeem", "get_script", "reset_hwid"
            user_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    cursor.close()
    conn.close()

# Appeler cette fonction au démarrage du bot
init_db()
