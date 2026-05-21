import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import psycopg2
import random
import string
from dotenv import load_dotenv

# Charger les variables d'environnement
load_dotenv()

# Configuration
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGDATABASE = os.getenv("PGDATABASE")

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Connexion à PostgreSQL
try:
    conn = psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        user=PGUSER,
        password=PGPASSWORD,
        database=PGDATABASE
    )
    cursor = conn.cursor()
    print("✅ Connexion à PostgreSQL réussie")
except Exception as e:
    print(f"❌ Erreur PostgreSQL: {e}")
    import sqlite3
    conn = sqlite3.connect('/tmp/luarmor.db')
    cursor = conn.cursor()
    print("⚠️ Utilisation de SQLite (fallback)")

# Initialiser la base de données
def init_db():
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS whitelist (
            discord_id TEXT PRIMARY KEY,
            username TEXT,
            key TEXT REFERENCES keys(key),
            date_added TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE
        )
    ''')
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
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS stats (
            id SERIAL PRIMARY KEY,
            project_name TEXT,
            action TEXT,
            user_id TEXT,
            timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

init_db()

# Fonctions utilitaires
def generate_key(length=16):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_script(key, project_name="FunHub"):
    return f'''-- Script Lua généré par {project_name}
local key = "{key}"
local function verifyKey()
    if key == "{key}" then
        print("✅ Clé valide pour {project_name}!")
    else
        print("❌ Clé invalide!")
    end
end
verifyKey()
'''

def log_stat(project_name, action, user_id):
    cursor.execute(
        "INSERT INTO stats (project_name, action, user_id) VALUES (%s, %s, %s)",
        (project_name, action, user_id)
    )
    conn.commit()

# Panneau de contrôle Luarmor
class LuarmorPanel(View):
    def __init__(self, project_name="FunHub"):
        super().__init__(timeout=None)
        self.project_name = project_name
        self.add_item(Button(label="🔑 Redeem Key", style=discord.ButtonStyle.success, custom_id="redeem_key"))
        self.add_item(Button(label="📜 Get Script", style=discord.ButtonStyle.primary, custom_id="get_script"))
        self.add_item(Button(label="👑 Get Role", style=discord.ButtonStyle.secondary, custom_id="get_role"))
        self.add_item(Button(label="🔄 Reset HWID", style=discord.ButtonStyle.danger, custom_id="reset_hwid"))
        self.add_item(Button(label="📊 Get Stats", style=discord.ButtonStyle.secondary, custom_id="get_stats"))

    async def interaction_check(self, interaction: discord.Interaction):
        cursor.execute(
            "SELECT 1 FROM whitelist WHERE discord_id = %s AND key IN (SELECT key FROM keys WHERE project_name = %s)",
            (str(interaction.user.id), self.project_name)
        )
        if not cursor.fetchone() and interaction.data["custom_id"] != "redeem_key":
            await interaction.response.send_message("❌ Tu n'es pas autorisé. Utilise `/redeem` d'abord.", ephemeral=True)
            return False
        return True

# Modal pour Redeem Key
class RedeemModal(Modal, title="Lier une clé"):
    key = TextInput(label="Clé", placeholder="Entrez votre clé ici...", custom_id="key_input", required=True)

    async def on_submit(self, interaction: discord.Interaction):
        cursor.execute("SELECT owner_discord_id, project_name FROM keys WHERE key = %s", (self.key.value,))
        key_data = cursor.fetchone()
        if not key_data:
            await interaction.response.send_message("❌ Clé invalide.", ephemeral=True)
            return
        owner_discord_id, project_name = key_data
        if owner_discord_id:
            await interaction.response.send_message("❌ Clé déjà liée.", ephemeral=True)
            return
        cursor.execute("UPDATE keys SET owner_discord_id = %s WHERE key = %s", (str(interaction.user.id), self.key.value))
        cursor.execute(
            "INSERT INTO whitelist (discord_id, username, key) VALUES (%s, %s, %s) ON CONFLICT (discord_id) DO UPDATE SET key = EXCLUDED.key",
            (str(interaction.user.id), interaction.user.name, self.key.value)
        )
        conn.commit()
        log_stat(project_name, "redeem", str(interaction.user.id))
        await interaction.response.send_message(f"✅ Clé **{self.key.value}** liée à ton compte pour **{project_name}**!", ephemeral=True)

# Commandes Slash
@bot.tree.command(name="panel", description="Panneau de contrôle Luarmor")
@app_commands.describe(project="Nom du projet")
async def panel(interaction: discord.Interaction, project: str = "FunHub"):
    cursor.execute("SELECT 1 FROM projects WHERE name = %s", (project,))
    if not cursor.fetchone():
        await interaction.response.send_message(f"❌ Projet **{project}** introuvable.", ephemeral=True)
        return
    embed = discord.Embed(title=f"🛡️ Panneau - {project}", description="Clique sur les boutons ci-dessous.", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=LuarmorPanel(project))

@bot.tree.command(name="create_project", description="Créer un projet (Admin)")
async def create_project(interaction: discord.Interaction, name: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    cursor.execute("INSERT INTO projects (name, owner_discord_id) VALUES (%s, %s) ON CONFLICT (name) DO NOTHING", (name, str(interaction.user.id)))
    for _ in range(10):
        key = generate_key()
        cursor.execute("INSERT INTO keys (key, project_name) VALUES (%s, %s)", (key, name))
    conn.commit()
    await interaction.response.send_message(f"✅ Projet **{name}** créé avec 10 clés!", ephemeral=True)

@bot.tree.command(name="add_key", description="Ajouter une clé (Admin)")
async def add_key(interaction: discord.Interaction, project: str, user: discord.User = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message("❌ Permission refusée.", ephemeral=True)
        return
    cursor.execute("SELECT 1 FROM projects WHERE name = %s", (project,))
    if not cursor.fetchone():
        await interaction.response.send_message(f"❌ Projet **{project}** introuvable.", ephemeral=True)
        return
    key = generate_key()
    cursor.execute("INSERT INTO keys (key, project_name, owner_discord_id) VALUES (%s, %s, %s)", (key, project, str(user.id) if user else None))
    if user:
        cursor.execute("INSERT INTO whitelist (discord_id, username, key) VALUES (%s, %s, %s) ON CONFLICT (discord_id) DO UPDATE SET key = EXCLUDED.key", (str(user.id), user.name, key))
    conn.commit()
    await interaction.response.send_message(f"✅ Clé **{key}** ajoutée pour {user.mention if user else 'le projet'}!", ephemeral=True)

# Gestion des boutons
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        if interaction.data["custom_id"] == "redeem_key":
            await interaction.response.send_modal(RedeemModal())
        elif interaction.data["custom_id"] == "get_script":
            cursor.execute("SELECT key, project_name FROM whitelist w JOIN keys k ON w.key = k.key WHERE w.discord_id = %s", (str(interaction.user.id),))
            result = cursor.fetchone()
            if not result:
                await interaction.response.send_message("❌ Aucune clé associée.", ephemeral=True)
                return
            key, project_name = result
            script = generate_script(key, project_name)
            await interaction.response.send_message(f"📜 Script pour **{project_name}** :\n```lua\n{script}\n```", ephemeral=True)
            log_stat(project_name, "get_script", str(interaction.user.id))
        elif interaction.data["custom_id"] == "get_role":
            role_name = f"{interaction.guild.name} - {project_name}"
            role = discord.utils.get(interaction.guild.roles, name=role_name)
            if not role:
                role = await interaction.guild.create_role(name=role_name)
            await interaction.user.add_roles(role)
            await interaction.response.send_message(f"✅ Rôle **{role.name}** ajouté !", ephemeral=True)
        elif interaction.data["custom_id"] == "reset_hwid":
            cursor.execute("SELECT key, project_name FROM whitelist w JOIN keys k ON w.key = k.key WHERE w.discord_id = %s", (str(interaction.user.id),))
            result = cursor.fetchone()
            if not result:
                await interaction.response.send_message("❌ Aucune clé associée.", ephemeral=True)
                return
            key, project_name = result
            cursor.execute("UPDATE keys SET hwid = NULL WHERE key = %s", (key,))
            conn.commit()
            await interaction.response.send_message("✅ HWID réinitialisé !", ephemeral=True)
            log_stat(project_name, "reset_hwid", str(interaction.user.id))
        elif interaction.data["custom_id"] == "get_stats":
            project_name = "FunHub"
            cursor.execute("SELECT action, COUNT(*) FROM stats WHERE project_name = %s GROUP BY action", (project_name,))
            stats = cursor.fetchall()
            cursor.execute("SELECT COUNT(*) FROM whitelist WHERE key IN (SELECT key FROM keys WHERE project_name = %s)", (project_name,))
            total_users = cursor.fetchone()[0]
            cursor.execute("SELECT COUNT(*) FROM keys WHERE project_name = %s", (project_name,))
            total_keys = cursor.fetchone()[0]
            if not stats:
                await interaction.response.send_message("❌ Aucune statistique.", ephemeral=True)
                return
            stats_text = "\n".join([f"{action}: {count}" for action, count in stats])
            embed = discord.Embed(title=f"📊 Stats pour {project_name}", description=f"**Utilisateurs**: {total_users}\n**Clés**: {total_keys}\n\n**Actions**:\n{stats_text}", color=discord.Color.green())
            await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()
    print(f"✅ Bot connecté: {bot.user}")

if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
