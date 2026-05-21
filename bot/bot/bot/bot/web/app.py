from flask import Flask, render_template, request, redirect, url_for, session
import psycopg2
from config import PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
import os

app = Flask(__name__)
app.secret_key = os.getenv("FLASK_SECRET_KEY", "ta_clé_secrète_ici")

def get_db_connection():
    conn = psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        user=PGUSER,
        password=PGPASSWORD,
        database=PGDATABASE
    )
    return conn

@app.route("/")
def home():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM projects")
    projects = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return render_template("index.html", projects=projects)

@app.route("/project/<project_name>")
def project(project_name):
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM whitelist WHERE key IN (SELECT key FROM keys WHERE project_name = %s)",
        (project_name,)
    )
    total_users = cursor.fetchone()[0]

    cursor.execute(
        "SELECT COUNT(*) FROM keys WHERE project_name = %s",
        (project_name,)
    )
    total_keys = cursor.fetchone()[0]

    cursor.close()
    conn.close()
    return render_template("project.html",
                          project_name=project_name,
                          total_users=total_users,
                          total_keys=total_keys)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if request.method == "POST":
        project_name = request.form.get("project_name")
        action = request.form.get("action")

        conn = get_db_connection()
        cursor = conn.cursor()

        if action == "create_project":
            cursor.execute(
                "INSERT INTO projects (name, owner_discord_id) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING",
                (project_name, "admin")  # À améliorer avec un système de login
            )
            for _ in range(10):
                key = generate_key()
                cursor.execute(
                    "INSERT INTO keys (key, project_name) VALUES (%s, %s)",
                    (key, project_name)
                )
            conn.commit()

        elif action == "generate_key":
            key = generate_key()
            cursor.execute(
                "INSERT INTO keys (key, project_name) VALUES (%s, %s)",
                (key, project_name)
            )
            conn.commit()

        cursor.close()
        conn.close()
        return redirect(url_for("admin"))

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM projects")
    projects = [row[0] for row in cursor.fetchall()]
    cursor.close()
    conn.close()
    return render_template("admin.html", projects=projects)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
