import os
import discord
from discord.ext import commands
import psycopg2

# 1. Récupérer les variables Railway
DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
PGHOST = os.getenv("PGHOST")
PGPORT = os.getenv("PGPORT")
PGUSER = os.getenv("PGUSER")
PGPASSWORD = os.getenv("PGPASSWORD")
PGDATABASE = os.getenv("PGDATABASE")

# 2. Vérifier que les variables existent
print("--- Variables Railway ---")
print(f"PGHOST: {PGHOST}")
print(f"PGPORT: {PGPORT}")
print(f"PGUSER: {PGUSER}")
print(f"PGDATABASE: {PGDATABASE}")
print("--------------------------")

# 3. Connexion à PostgreSQL
try:
    conn = psycopg2.connect(
        host=PGHOST,  # ⚠️ PAS "localhost" !
        port=PGPORT,
        user=PGUSER,
        password=PGPASSWORD,
        database=PGDATABASE
    )
    print("✅ Connexion à PostgreSQL réussie !")
except Exception as e:
    print(f"❌ ERREUR PostgreSQL: {e}")
    print("Le bot va s'arrêter.")
    exit(1)  # Arrête le bot si PostgreSQL échoue

# 4. Initialiser Discord
intents = discord.Intents.default()
intents.message_content = True
bot = commands.Bot(command_prefix="!", intents=intents)

# 5. Commande de test
@bot.command()
async def test(ctx):
    await ctx.send("✅ Bot fonctionnel !")

# 6. Démarrer le bot
@bot.event
async def on_ready():
    print(f"Bot connecté: {bot.user}")
    await bot.tree.sync()

bot.run(DISCORD_TOKEN)
