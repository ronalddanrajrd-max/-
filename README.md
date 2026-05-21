# Luarmor Bot - Clone
Un bot Discord inspiré de [Luarmor](https://luarmor.net/) pour gérer des whitelists Lua.

## 🚀 Déploiement
1. **Créer un bot Discord** :
   - Va sur [Discord Developer Portal](https://discord.com/developers/applications) et crée une application.
   - Ajoute un bot et copie son **token**.

2. **Configurer Railway** :
   - Ajoute les variables d'environnement :
     - `DISCORD_TOKEN` : Token de ton bot Discord.
     - `PGHOST`, `PGPORT`, `PGUSER`, `PGPASSWORD`, `PGDATABASE` : Informations de ta base de données PostgreSQL (automatiquement générées si tu ajoutes un service PostgreSQL sur Railway).

3. **Déployer** :
   - Railway détectera automatiquement le projet Python et installera les dépendances.

## 📌 Commandes
   Commande          | Description                          |
 |-------------------|--------------------------------------|
 | `/getscript`      | Reçoit son script Lua avec sa clé.   |
 | `/redeem <clé>`   | Lie une clé à son Discord ID.        |
 | `/resethwid`      | Réinitialise son HWID.               |
 | `/whitelist add`  | Ajoute un utilisateur à la whitelist.|
 | `/whitelist list` | Liste les utilisateurs whitelistés. |
 | `/panel`          | Affiche le panneau de contrôle.      |

## 🔧 Technos
- Python 3.10+
- Discord.py
- PostgreSQL (Railway)
