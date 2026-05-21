import os
import discord
from discord import app_commands
from discord.ext import commands
import psycopg2
import random
import string
from discord.ui import Button, View, Modal, TextInput

# Récupérer les variables d'environnement (Railway)
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

# Connexion à PostgreSQL (Railway)
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
    print(f"❌ Erreur de connexion à PostgreSQL : {e}")
    # Si PostgreSQL échoue, utiliser SQLite en fallback (pour les tests locaux)
    import sqlite3
    conn = sqlite3.connect('/tmp/luarmor.db')
    cursor = conn.cursor()
    print("⚠️ Utilisation de SQLite (fallback)")

# Créer les tables si elles n'existent pas
def init_db():
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS keys (
            key TEXT PRIMARY KEY,
            owner_discord_id TEXT,
            hwid TEXT,
            date_created TEXT DEFAULT CURRENT_TIMESTAMP,
            is_active BOOLEAN DEFAULT TRUE,
            script_content TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS whitelist (
            discord_id TEXT PRIMARY KEY,
            username TEXT,
            date_added TEXT DEFAULT CURRENT_TIMESTAMP,
            is_banned BOOLEAN DEFAULT FALSE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS logs (
            id SERIAL PRIMARY KEY,
            action TEXT,
            user_id TEXT,
            target_id TEXT,
            details TEXT,
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()

init_db()

# --- FONCTIONS UTILITAIRES ---
def generate_key(length=16):
    """Génère une clé aléatoire."""
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_script(key):
    """Génère un script Lua de base avec la clé intégrée."""
    return f'''-- Script Lua généré par Luarmor Bot
local key = "{key}"
-- Votre code ici...
print("Clé valide : " .. key)
'''

# --- COMMANDES SLASH ---
@bot.tree.command(name="getscript", description="Reçoit ton script Lua avec ta clé")
async def get_script(interaction: discord.Interaction):
    cursor.execute("SELECT key FROM whitelist WHERE discord_id=%s", (str(interaction.user.id),))
    result = cursor.fetchone()

    if not result:
        await interaction.response.send_message(
            "❌ Tu n'es pas whitelisté. Contacte un administrateur.",
            ephemeral=True
        )
        return

    key = result[0]
    script = generate_script(key)

    # Envoyer le script dans un fichier
    await interaction.response.send_message(
        f"📜 Voici ton script Lua avec ta clé :\n```lua\n{script}\n```",
        ephemeral=True
    )

@bot.tree.command(name="redeem", description="Lie une clé à ton Discord ID")
async def redeem_key(interaction: discord.Interaction, key: str):
    cursor.execute("SELECT * FROM keys WHERE key=%s", (key,))
    key_data = cursor.fetchone()

    if not key_data:
        await interaction.response.send_message(
            "❌ Cette clé n'existe pas.",
            ephemeral=True
        )
        return

    if key_data[1]:  # Si la clé a déjà un propriétaire
        await interaction.response.send_message(
            "❌ Cette clé est déjà liée à un autre utilisateur.",
            ephemeral=True
        )
        return

    # Lier la clé à l'utilisateur
    cursor.execute(
        "UPDATE keys SET owner_discord_id=%s WHERE key=%s",
        (str(interaction.user.id), key)
    )
    cursor.execute(
        "INSERT INTO whitelist (discord_id, username) VALUES (%s, %s) ON CONFLICT (discord_id) DO NOTHING",
        (str(interaction.user.id), interaction.user.name)
    )
    conn.commit()

    await interaction.response.send_message(
        f"✅ Clé **{key}** liée à ton compte Discord !",
        ephemeral=True
    )

@bot.tree.command(name="resethwid", description="Réinitialise ton HWID pour ta clé")
async def reset_hwid(interaction: discord.Interaction):
    cursor.execute("SELECT key FROM whitelist WHERE discord_id=%s", (str(interaction.user.id),))
    result = cursor.fetchone()

    if not result:
        await interaction.response.send_message(
            "❌ Tu n'as pas de clé associée.",
            ephemeral=True
        )
        return

    key = result[0]
    cursor.execute(
        "UPDATE keys SET hwid=NULL WHERE key=%s",
        (key,)
    )
    conn.commit()

    await interaction.response.send_message(
        "✅ Ton HWID a été réinitialisé pour ta clé.",
        ephemeral=True
    )

@bot.tree.command(name="whitelist", description="Gère la whitelist des utilisateurs")
@app_commands.describe(
    action="add/remove/list",
    user="Mention ou ID de l'utilisateur"
)
async def whitelist(interaction: discord.Interaction, action: str, user: discord.User = None):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Tu n'as pas la permission d'utiliser cette commande.",
            ephemeral=True
        )
        return

    if action == "add":
        if user is None:
            await interaction.response.send_message(
                "❌ Veuillez spécifier un utilisateur.",
                ephemeral=True
            )
            return

        # Générer une clé pour l'utilisateur
        key = generate_key()
        script = generate_script(key)

        cursor.execute(
            "INSERT INTO whitelist (discord_id, username) VALUES (%s, %s) ON CONFLICT (discord_id) DO NOTHING",
            (str(user.id), user.name)
        )
        cursor.execute(
            "INSERT INTO keys (key, owner_discord_id, script_content) VALUES (%s, %s, %s)",
            (key, str(user.id), script)
        )
        conn.commit()

        await interaction.response.send_message(
            f"✅ {user.mention} a été ajouté à la whitelist avec la clé : **{key}**"
        )

    elif action == "remove":
        if user is None:
            await interaction.response.send_message(
                "❌ Veuillez spécifier un utilisateur.",
                ephemeral=True
            )
            return

        cursor.execute(
            "DELETE FROM whitelist WHERE discord_id=%s",
            (str(user.id),)
        )
        cursor.execute(
            "UPDATE keys SET owner_discord_id=NULL WHERE owner_discord_id=%s",
            (str(user.id),)
        )
        conn.commit()

        await interaction.response.send_message(
            f"✅ {user.mention} a été retiré de la whitelist."
        )

    elif action == "list":
        cursor.execute("SELECT discord_id, username FROM whitelist")
        users = cursor.fetchall()

        if not users:
            await interaction.response.send_message("❌ Aucune personne dans la whitelist.")
            return

        user_list = "\n".join([f"<@{user[0]}> ({user[1]})" for user in users])
        await interaction.response.send_message(
            f"📋 **Whitelist** ({len(users)} utilisateurs) :\n{user_list}"
        )

    else:
        await interaction.response.send_message(
            "❌ Action invalide. Utilise : add/remove/list",
            ephemeral=True
        )

@bot.tree.command(name="setlogs", description="Configure un webhook pour les logs")
async def set_logs(interaction: discord.Interaction, webhook_url: str):
    if not interaction.user.guild_permissions.administrator:
        await interaction.response.send_message(
            "❌ Tu n'as pas la permission d'utiliser cette commande.",
            ephemeral=True
        )
        return

    # Stocker l'URL du webhook en base de données
    cursor.execute(
        "INSERT INTO logs (action, user_id, target_id, details) VALUES (%s, %s, %s, %s)",
        ("set_webhook", str(interaction.user.id), "global", webhook_url)
    )
    conn.commit()

    await interaction.response.send_message(
        f"✅ Webhook configuré : {webhook_url}"
    )

# --- PANNEAU DE CONTRÔLE AVEC BOUTONS ---
class ScriptView(View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="📜 Get Script", style=discord.ButtonStyle.primary, custom_id="get_script")
    async def get_script(self, interaction: discord.Interaction, button: Button):
        cursor.execute("SELECT key FROM whitelist WHERE discord_id=%s", (str(interaction.user.id),))
        result = cursor.fetchone()

        if not result:
            await interaction.response.send_message(
                "❌ Tu n'es pas whitelisté.",
                ephemeral=True
            )
            return

        key = result[0]
        script = generate_script(key)

        await interaction.response.send_message(
            f"📜 Voici ton script Lua :\n```lua\n{script}\n```",
            ephemeral=True
        )

    @discord.ui.button(label="🔑 Redeem Key", style=discord.ButtonStyle.success, custom_id="redeem_key")
    async def redeem_key(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RedeemModal())

class RedeemModal(Modal, title="Lier une clé"):
    key = TextInput(label="Clé", placeholder="Entrez votre clé ici", custom_id="key_input")

    async def on_submit(self, interaction: discord.Interaction):
        cursor.execute("SELECT * FROM keys WHERE key=%s", (self.key.value,))
        key_data = cursor.fetchone()

        if not key_data:
            await interaction.response.send_message(
                "❌ Cette clé n'existe pas.",
                ephemeral=True
            )
            return

        if key_data[1]:
            await interaction.response.send_message(
                "❌ Cette clé est déjà liée à un autre utilisateur.",
                ephemeral=True
            )
            return

        cursor.execute(
            "UPDATE keys SET owner_discord_id=%s WHERE key=%s",
            (str(interaction.user.id), self.key.value)
        )
        cursor.execute(
            "INSERT INTO whitelist (discord_id, username) VALUES (%s, %s) ON CONFLICT (discord_id) DO NOTHING",
            (str(interaction.user.id), interaction.user.name)
        )
        conn.commit()

        await interaction.response.send_message(
            f"✅ Clé **{self.key.value}** liée à ton compte !",
            ephemeral=True
        )

@bot.tree.command(name="panel", description="Affiche le panneau de contrôle Luarmor")
async def panel(interaction: discord.Interaction):
    await interaction.response.send_message(
        "🎮 **Panneau Luarmor**\nClique sur les boutons ci-dessous :",
        view=ScriptView(),
        ephemeral=True
    )

# --- ÉVÉNEMENTS ---
@bot.event
async def on_ready():
    await bot.tree.sync()  # Synchroniser les commandes slash
    print(f"✅ Bot connecté en tant que {bot.user} (ID: {bot.user.id})")

# --- LANCEMENT DU BOT ---
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
