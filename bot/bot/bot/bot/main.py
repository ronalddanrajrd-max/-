import discord
from discord import app_commands
from discord.ext import commands
from discord.ui import Button, View, Modal, TextInput
from database import get_db_connection
from config import DISCORD_TOKEN, WEB_URL
import random
import string
import aiohttp

# Initialisation du bot
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# --- FONCTIONS UTILITAIRES ---
def generate_key(length=16):
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(length))

def generate_script(key, project_name="FunHub"):
    return f'''-- Script Lua généré par {project_name} (Luarmor Clone)
local key = "{key}"
local project = "{project_name}"

-- Fonction de vérification
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO stats (project_name, action, user_id) VALUES (%s, %s, %s)",
        (project_name, action, user_id)
    )
    conn.commit()
    cursor.close()
    conn.close()

# --- BOUTONS DU PANNEAU LUARMOR ---
class LuarmorPanel(View):
    def __init__(self, project_name="FunHub"):
        super().__init__(timeout=None)
        self.project_name = project_name

        # Bouton Redeem Key
        self.add_item(Button(
            label="🔑 Redeem Key",
            style=discord.ButtonStyle.success,
            custom_id="redeem_key",
            emoji="🔑"
        ))

        # Bouton Get Script
        self.add_item(Button(
            label="📜 Get Script",
            style=discord.ButtonStyle.primary,
            custom_id="get_script",
            emoji="📜"
        ))

        # Bouton Get Role
        self.add_item(Button(
            label="👑 Get Role",
            style=discord.ButtonStyle.secondary,
            custom_id="get_role",
            emoji="👑"
        ))

        # Bouton Reset HWID
        self.add_item(Button(
            label="🔄 Reset HWID",
            style=discord.ButtonStyle.danger,
            custom_id="reset_hwid",
            emoji="🔄"
        ))

        # Bouton Get Stats
        self.add_item(Button(
            label="📊 Get Stats",
            style=discord.ButtonStyle.secondary,
            custom_id="get_stats",
            emoji="📊"
        ))

    async def interaction_check(self, interaction: discord.Interaction):
        # Vérifier que l'utilisateur est dans la whitelist pour ce projet
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT 1 FROM whitelist WHERE discord_id = %s AND key IN (SELECT key FROM keys WHERE project_name = %s)",
            (str(interaction.user.id), self.project_name)
        )
        is_whitelisted = cursor.fetchone() is not None
        cursor.close()
        conn.close()

        if not is_whitelisted and interaction.data["custom_id"] != "redeem_key":
            await interaction.response.send_message(
                "❌ Tu n'es pas autorisé à utiliser ce projet. Utilise `/redeem` d'abord.",
                ephemeral=True
            )
            return False
        return True

# --- MODALS ---
class RedeemModal(Modal, title="🔑 Lier une clé"):
    key = TextInput(
        label="Clé",
        placeholder="Entrez votre clé ici...",
        custom_id="key_input",
        required=True
    )

    async def on_submit(self, interaction: discord.Interaction):
        conn = get_db_connection()
        cursor = conn.cursor()

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
            "INSERT INTO whitelist (discord_id, username, key) VALUES (%s, %s, %s) "
            "ON CONFLICT (discord_id) DO UPDATE SET key = EXCLUDED.key",
            (str(interaction.user.id), interaction.user.name, self.key.value)
        )
        conn.commit()

        # Log de l'action
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
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT 1 FROM projects WHERE name = %s",
        (project,)
    )
    project_exists = cursor.fetchone() is not None
    cursor.close()
    conn.close()

    if not project_exists:
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
        view=LuarmorPanel(project),
        ephemeral=False
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

    conn = get_db_connection()
    cursor = conn.cursor()

    # Créer le projet
    cursor.execute(
        "INSERT INTO projects (name, owner_discord_id, script_content) VALUES (%s, %s, %s) "
        "ON CONFLICT (name) DO NOTHING",
        (name, str(interaction.user.id), script)
    )

    # Générer 10 clés par défaut pour le projet
    for _ in range(10):
        key = generate_key()
        cursor.execute(
            "INSERT INTO keys (key, project_name) VALUES (%s, %s)",
            (key, name)
        )

    conn.commit()
    cursor.close()
    conn.close()

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

    conn = get_db_connection()
    cursor = conn.cursor()

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
        "INSERT INTO keys (key, project_name, owner_discord_id) VALUES (%s, %s, %s)",
        (key, project, str(user.id) if user else None)
    )

    if user:
        cursor.execute(
            "INSERT INTO whitelist (discord_id, username, key) VALUES (%s, %s, %s) "
            "ON CONFLICT (discord_id) DO UPDATE SET key = EXCLUDED.key",
            (str(user.id), user.name, key)
        )

    conn.commit()
    cursor.close()
    conn.close()

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
        if interaction.data["custom_id"] == "redeem_key":
            await interaction.response.send_modal(RedeemModal())

        elif interaction.data["custom_id"] == "get_script":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, project_name FROM whitelist w JOIN keys k ON w.key = k.key "
                "WHERE w.discord_id = %s",
                (str(interaction.user.id),)
            )
            result = cursor.fetchone()
            cursor.close()
            conn.close()

            if not result:
                await interaction.response.send_message(
                    "❌ Tu n'as pas de clé associée. Utilise le bouton **Redeem Key** d'abord.",
                    ephemeral=True
                )
                return

            key, project_name = result
            script = generate_script(key, project_name)

            await interaction.response.send_message(
                f"📜 Voici ton script pour **{project_name}** :\n```lua\n{script}\n```",
                ephemeral=True
            )

            # Log de l'action
            log_stat(project_name, "get_script", str(interaction.user.id))

        elif interaction.data["custom_id"] == "get_role":
            # Exemple : Donner un rôle Discord à l'utilisateur
            role_name = f"{interaction.guild.name} - {interaction.data.get('project', 'FunHub')}"
            role = discord.utils.get(interaction.guild.roles, name=role_name)

            if not role:
                role = await interaction.guild.create_role(name=role_name)

            await interaction.user.add_roles(role)
            await interaction.response.send_message(
                f"✅ Rôle **{role.name}** ajouté !",
                ephemeral=True
            )

        elif interaction.data["custom_id"] == "reset_hwid":
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(
                "SELECT key, project_name FROM whitelist w JOIN keys k ON w.key = k.key "
                "WHERE w.discord_id = %s",
                (str(interaction.user.id),)
            )
            result = cursor.fetchone()

            if not result:
                await interaction.response.send_message(
                    "❌ Tu n'as pas de clé associée.",
                    ephemeral=True
                )
                return

            key, project_name = result
            cursor.execute(
                "UPDATE keys SET hwid = NULL WHERE key = %s",
                (key,)
            )
            conn.commit()
            cursor.close()
            conn.close()

            await interaction.response.send_message(
                "✅ Ton HWID a été réinitialisé !",
                ephemeral=True
            )

            # Log de l'action
            log_stat(project_name, "reset_hwid", str(interaction.user.id))

        elif interaction.data["custom_id"] == "get_stats":
            project_name = interaction.data.get("project", "FunHub")
            conn = get_db_connection()
            cursor = conn.cursor()

            # Récupérer les stats
            cursor.execute(
                "SELECT action, COUNT(*) FROM stats WHERE project_name = %s GROUP BY action",
                (project_name,)
            )
            stats = cursor.fetchall()

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
            await interaction.response.send_message(embed=embed, ephemeral=True)

@bot.event
async def on_ready():
    await bot.tree.sync()  # Synchroniser les commandes slash
    print(f"✅ Bot connecté en tant que {bot.user} (ID: {bot.user.id})")

# --- LANCEMENT DU BOT ---
if __name__ == "__main__":
    bot.run(DISCORD_TOKEN)
