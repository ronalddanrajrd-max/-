import os
import discord
from discord.ext import commands
import psycopg2

# 1. Affiche TOUTES les variables d'environnement (pour débogage)
print("\n--- VARIABLES D'ENVIRONNEMENT ---")
for key, value in os.environ.items():
    if key.startswith("PG") or key == "DISCORD_TOKEN":
        print(f"{key}: {value}")
print("--------------------------------\n")

# 2. Récupère les variables Railway
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGDATABASE = os.getenv("PGDATABASE")

# 3. Vérifie que PGHOST n'est PAS "localhost"
if PGHOST == "localhost" or PGHOST is None:
    raise ValueError(
        "❌ ERREUR: PGHOST est 'localhost' ou vide ! "
        "Vérifie que tu as bien ajouté un service PostgreSQL dans Railway."
    )

# 4. Connexion à PostgreSQL
try:
    conn = psycopg2.connect(
        host=PGHOST,  # ⚠️ DOIT être l'hôte Railway (ex: containers-us-west-123.railway.app)
        port=PGPORT,
        user=PGUSER,
        password=PGPASSWORD,
        database=PGDATABASE
    )
    print("✅ Connexion à PostgreSQL réussie !")
except Exception as e:
    print(f"❌ ERREUR PostgreSQL: {e}")
    exit(1)  # Arrête le bot si la connexion échoue

# 5. Initialise Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

@bot.event
async def on_ready():
    print(f"✅ Bot connecté: {bot.user}")

bot.run(DISCORD_TOKEN)
