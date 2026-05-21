import os
import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
import psycopg2
import random
import string
from dotenv import load_dotenv

# Charger les variables d'environnement (pour les tests locaux)
load_dotenv()

# Récupérer les variables Railway/PostgreSQL
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGDATABASE = os.getenv("PGDATABASE")

# Initialisation du bot Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# Connexion à PostgreSQL (obligatoire sur Railway)
try:
    conn = psycopg2.connect(
        host=PGHOST,
        port=PGPORT,
        user=PGUSER,
        password=PGPASSWORD,
        database=PGDATABASE
    )
    cursor = conn.cursor()
    print("✅ Connexion à PostgreSQL réussie !")
except Exception as e:
    print(f"❌ Erreur PostgreSQL: {e}")
    raise  # Arrête le bot si PostgreSQL ne fonctionne pas

# Initialiser la base de données
def init_db():
    # Table des clés Lua
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

    # Table des projets
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS projects (
            name TEXT PRIMARY KEY,
            owner_discord_id TEXT,
            script_content TEXT,
            date_created TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            total_keys INTEGER DEFAULT 0
        )
    ''')

    # Table des statistiques
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
    print("✅ Tables PostgreSQL créées avec succès !")

init_db()

# --- FONCTIONS UTILITAIRES ---
def generate_key(length=16):
    """Génère une clé aléatoire."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_script(key, project_name="FunHub"):
    """Génère un script Lua avec la clé intégrée."""
    return f'''-- Script Lua généré par {project_name} (Luarmor Clone)
local key = "{key}"
local project = "{project_name}"

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
    """Enregistre une action dans les stats."""
    cursor.execute(
        "INSERT INTO stats (project_name, action, user_id) VALUES (%s, %s, %s)",
        (project_name, action, user_id)
    )
    conn.commit()

# --- PANNEAU DE CONTRÔLE (BOUTONS) ---
class LuarmorPanel(View):
    def __init__(self, project_name="FunHub"):
        super().__init__(timeout=None)
        self.project_name = project_name

        # Ajouter les boutons (comme sur Luarmor)
        self.add_item(Button(
            label="🔑 Redeem Key",
            style=discord.ButtonStyle.success,
            custom_id="redeem_key"
        ))
        self.add_item(Button(
            label="📜 Get Script",
            style=discord.ButtonStyle.primary,
            custom_id="get_script"
        ))
        self.add_item(Button(
            label="👑 Get Role",
            style=discord.ButtonStyle.secondary,
            custom_id="get_role"
        ))
        self.add_item(Button(
            label="🔄 Reset HWID",
            style=discord.ButtonStyle.danger,
            custom_id="reset_hwid"
        ))
        self.add_item(Button(
            label="📊 Get Stats",
            style=discord.ButtonStyle.secondary,
            custom_id="get_stats"
        ))

    async def interaction_check(self, interaction: discord.Interaction):
        """Vérifie si l'utilisateur a le droit d'utiliser les boutons."""
        cursor.execute(
            "SELECT 1 FROM whitelist WHERE discord_id = %s AND key IN (SELECT key FROM keys WHERE project_name = %s)",
            (str(interaction.user.id), self.project_name)
        )
        is_whitelisted = cursor.fetchone() is not None

        # Autoriser "Redeem Key" même si l'utilisateur n'est pas whitelisté
        if not is_whitelisted and interaction.data["custom_id"] != "redeem_key":
            await interaction.response.send_message(
                "❌ Tu n'es pas autorisé à utiliser ce projet. Utilise d'abord **Redeem Key** !",
                ephemeral=True
            )
            return False
        return True

# --- MODAL POUR REDEEM KEY ---
class RedeemModal(Modal, title="🔑 Lier une clé"):
    key = TextInput(
        label="Clé",
        placeholder="Entrez votre clé ici...",
        custom_id="key_input",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        # Vérifier si la clé existe et n'est pas déjà liée
        cursor.execute(
            "SELECT owner_discord_id, project_name FROM keys WHERE key = %s",
            (self.key.value,)
        )
        key_data = cursor.fetchone()

        if not key_data:
            await interaction.response.send_message(
                "❌ Cette clé n'existe pas.",
                ephemeral=True
            )
            return

        owner_discord_id, project_name = key_data
        if owner_discord_id:
            await interaction.response.send_message(
                "❌ Cette clé est déjà liée à un autre utilisateur.",
                ephemeral=True
            )
            return

        # Lier la clé à l'utilisateur
        cursor.execute(
            "UPDATE keys SET owner_discord_id = %s WHERE key = %s",
            (str(interaction.user.id), self.key.value)
        )
        cursor.execute(
            "INSERT INTO whitelist (discord_id, username, key) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (discord_id) DO UPDATE SET key = EXCLUDED.key",
            (str(interaction.user.id), interaction.user.name, self.key.value)
        )
        conn.commit()
        log_stat(project_name, "redeem", str(interaction.user.id))

        await interaction.response.send_message(
            f"✅ Clé **{self.key.value}** liée à ton compte pour le projet **{project_name}** !",
            ephemeral=True
        )

# --- COMMANDES SLASH ---
@bot.tree.command(name="panel", description="Affiche le panneau de contrôle Luarmor")
@app_commands.describe(project="Nom du projet (ex: FunHub)")
async def luarmor_panel(interaction: discord.Interaction, project: str = "FunHub"):
    # Vérifier que le projet existe
    cursor.execute(
        "SELECT 1 FROM projects WHERE name = %s",
        (project,)
    )
    if not cursor.fetchone():
        await interaction.response.send_message(
            f"❌ Le projet **{project}** n'existe pas.",
            ephemeral=True
        )
        return

    embed = discord.Embed(
        title=f"🛡️ Panneau de contrôle - {project}",
        description="Clique sur les boutons ci-dessous pour gérer ton script.",
        color=discord.Color.blue()
    )
    await interaction.response.send_message(
        embed=embed,
        view=LuarmorPanel(project)
    )

@bot.tree.command(name="create_project", description="Crée un nouveau projet (Admin)")
@app_commands.describe(
    name="Nom du projet",
    script="Contenu du script Lua (optionnel)"
)
async def create_project(interaction: discord.Interaction, name: str, script: str = ""):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Tu n'as pas la permission de créer un projet.",
            ephemeral=True
        )
        return

    # Créer le projet
    cursor.execute(
        "INSERT INTO projects (name, owner_discord_id, script_content) "
        "VALUES (%s, %s, %s) ON CONFLICT (name) DO NOTHING",
        (name, str(interaction.user.id), script)
    )

    # Générer 10 clés par défaut
    for _ in range(10):
        key = generate_key()
        cursor.execute(
            "INSERT INTO keys (key, project_name) VALUES (%s, %s)",
            (key, name)
        )

    conn.commit()
    await interaction.response.send_message(
        f"✅ Projet **{name}** créé avec 10 clés par défaut !",
        ephemeral=True
    )

@bot.tree.command(name="add_key", description="Ajoute une clé à un projet (Admin)")
@app_commands.describe(
    project="Nom du projet",
    user="Utilisateur à whitelister (optionnel)"
)
async def add_key(interaction: discord.Interaction, project: str, user: discord.User = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Tu n'as pas la permission d'ajouter une clé.",
            ephemeral=True
        )
        return

    # Vérifier que le projet existe
    cursor.execute(
        "SELECT 1 FROM projects WHERE name = %s",
        (project,)
    )
    if not cursor.fetchone():
        await interaction.response.send_message(
            f"❌ Le projet **{project}** n'existe pas.",
            ephemeral=True
        )
        return

    # Générer une clé
    key = generate_key()
    cursor.execute(
        "INSERT INTO keys (key, project_name, owner_discord_id) "
        "VALUES (%s, %s, %s)",
        (key, project, str(user.id) if user else None)
    )

    # Whitelister l'utilisateur si spécifié
    if user:
        cursor.execute(
            "INSERT INTO whitelist (discord_id, username, key) "
            "VALUES (%s, %s, %s) "
            "ON CONFLICT (discord_id) DO UPDATE SET key = EXCLUDED.key",
            (str(user.id), user.name, key)
        )

    conn.commit()

    if user:
        await interaction.response.send_message(
            f"✅ Clé **{key}** ajoutée pour {user.mention} dans le projet **{project}** !",
            ephemeral=True
        )
    else:
        await interaction.response.send_message(
            f"✅ Nouvelle clé pour **{project}** : **{key}**",
            ephemeral=True
        )

# --- GESTION DES BOUTONS ---
@bot.event
async def on_interaction(interaction: discord.Interaction):
    if interaction.type == discord.InteractionType.component:
        # Bouton Redeem Key
        if interaction.data["custom_id"] == "redeem_key":
            await interaction.response.send_modal(RedeemModal())

        # Bouton Get Script
        elif interaction.data["custom_id"] == "get_script":
            cursor.execute(
                "SELECT key, project_name FROM whitelist w "
                "JOIN keys k ON w.key = k.key "
                "WHERE w.discord_id = %s",
                (str(interaction.user.id),)
            )
            result = cursor.fetchone()

            if not result:
                await interaction.response.send_message(
                    "❌ Aucune clé associée à ton compte. Utilise d'abord **Redeem Key** !",
                    ephemeral=True
                )
                return

            key, project_name = result
            script = generate_script(key, project_name)
            await interaction.response.send_message(
                f"📜 Voici ton script pour **{project_name}** :\n```lua\n{script}\n```",
                ephemeral=True
            )
            log_stat(project_name, "get_script", str(interaction.user.id))

        # Bouton Get Role
        elif interaction.data["custom_id"] == "get_role":
            role_name = f"{interaction.guild.name} - {self.project_name if hasattr(interaction, 'view') else 'FunHub'}"
            role = discord.utils.get(interaction.guild.roles, name=role_name)

            if not role:
                role = await interaction.guild.create_role(name=role_name)

            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                f"✅ Rôle **{role.name}** ajouté !",
                ephemeral=True
            )

        # Bouton Reset HWID
        elif interaction.data["custom_id"] == "reset_hwid":
            cursor.execute(
                "SELECT key, project_name FROM whitelist w "
                "JOIN keys k ON w.key = k.key "
                "WHERE w.discord_id = %s",
                (str(interaction.user.id),)
            )
            result = cursor.fetchone()

            if not result:
                await interaction.response.send_message(
                    "❌ Aucune clé associée à ton compte.",
                    ephemeral=True
                )
                return

            key, project_name = result
            cursor.execute(
                "UPDATE keys SET hwid = NULL WHERE key = %s",
                (key,)
            )
            conn.commit()
            await interaction.response.send_message(
                "✅ Ton HWID a été réinitialisé !",
                ephemeral=True
            )
            log_stat(project_name, "reset_hwid", str(interaction.user.id))

        # Bouton Get Stats
        elif interaction.data["custom_id"] == "get_stats":
            project_name = "FunHub"  # Par défaut
            if hasattr(interaction, 'view') and hasattr(interaction.view, 'project_name'):
                project_name = interaction.view.project_name

            cursor.execute(
                "SELECT action, COUNT(*) FROM stats "
                "WHERE project_name = %s GROUP BY action",
                (project_name,)
            )
            stats = cursor.fetchall()

            cursor.execute(
                "SELECT COUNT(*) FROM whitelist "
                "WHERE key IN (SELECT key FROM keys WHERE project_name = %s)",
                (project_name,)
            )
            total_users = cursor.fetchone()[0]

            cursor.execute(
                "SELECT COUNT(*) FROM keys WHERE project_name = %s",
                (project_name,)
            )
            total_keys = cursor.fetchone()[0]

            if not stats:
                await interaction.response.send_message(
                    f"❌ Aucune statistique pour **{project_name}**.",
                    ephemeral=True
                )
                return

            stats_text = "\n".join([f"{action}: {count}" for action, count in stats])
            embed = discord.Embed(
                title=f"📊 Statistiques pour {project_name}",
                description=f"**Utilisateurs whitelistés** : {total_users}\n"
                           f"**Clés générées** : {total_keys}\n\n"
                           f"**Actions** :\n{stats_text}",
                color=discord.Color.green()
            )
            await interaction.response.send_message(
                embed=embed,
                ephemeral=True
            )

# --- ÉVÉNEMENT DE DÉMARRAGE ---
@bot.event
async def on_ready():
    await bot.tree.sync()  # Synchroniser les commandes slash
    print(f"✅ Bot connecté en tant que {bot.user} (ID: {bot.user.id})")

# --- LANCEMENT DU BOT ---
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
