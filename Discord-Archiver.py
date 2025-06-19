import nextcord
from nextcord.ext import commands
import os
import asyncio
import re
from datetime import datetime
import aiohttp

intents = nextcord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True
intents.messages = True
intents.emojis_and_stickers = True

bot = commands.Bot(command_prefix="!", intents=intents)
has_run = False

def safe_filename(name):
    return re.sub(r'[\\/*?:"<>|]', "_", name)

def load_token_from_config():
    config_path = "config.txt"

    if not os.path.isfile(config_path):
        print("[INFO] config.txt not found. Creating one now...")
        with open(config_path, "w", encoding="utf-8") as f:
            f.write("Bot token: \n")
        print("[ACTION REQUIRED] Please open config.txt and paste your bot token after 'Bot token:'. Then rerun the script.")
        exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip().lower().startswith("bot token:"):
                token = line.split(":", 1)[1].strip()
                if token:
                    return token
                else:
                    print("[ERROR] Bot token line found but no token provided. Please fill in your token.")
                    exit(1)

    print("[ERROR] Bot token not found in config.txt. Please include a line like 'Bot token: YOUR_TOKEN_HERE'")
    exit(1)

BOT_TOKEN = load_token_from_config()

async def download_file(session, url, path, label):
    try:
        async with session.get(url) as response:
            if response.status == 200:
                with open(path, "wb") as f:
                    f.write(await response.read())
                print(f"[SUCCESS] Saved {label}: {os.path.basename(path)}")
            else:
                print(f"[WARNING] {label} not available (status {response.status})")
    except Exception as e:
        print(f"[ERROR] Failed to download {label}: {e}")

@bot.event
async def on_ready():
    global has_run
    if has_run:
        print("[INFO] Skipping extraction: already completed once.")
        return
    has_run = True

    print(f"[INFO] Logged in as {bot.user}")

    guild_id_input = input("[INPUT] Enter the Guild ID: ").strip()
    try:
        guild = nextcord.utils.get(bot.guilds, id=int(guild_id_input))
        if not guild:
            print("[ERROR] Bot is not in that guild or Guild ID is invalid.")
            return

        print(f"[INFO] Found guild: {guild.name} ({guild.id})")

        base_folder = f"./{guild.id}"
        output_folder = os.path.join(base_folder, "channels & messages")
        roles_folder = os.path.join(base_folder, "roles")
        emojis_folder = os.path.join(base_folder, "emojis")
        stickers_folder = os.path.join(base_folder, "stickers")

        for folder in [output_folder, roles_folder, emojis_folder, stickers_folder]:
            os.makedirs(folder, exist_ok=True)

        async with aiohttp.ClientSession() as session:
            if guild.icon:
                await download_file(session, guild.icon.url, os.path.join(base_folder, "icon.png"), "Guild Icon")

            banner_url = None
            if guild.banner:
                banner_url = guild.banner.url
                label = "Guild Banner"
            elif guild.splash:
                banner_url = guild.splash.url
                label = "Guild Splash"
            elif getattr(guild, "discovery_splash", None):
                banner_url = guild.discovery_splash.url
                label = "Discovery Splash"
            else:
                label = None

            if banner_url:
                await download_file(session, banner_url, os.path.join(base_folder, "invitebanner.png"), label)
            else:
                print("[INFO] No guild banner or splash available")

            info_path = os.path.join(base_folder, "info.txt")
            with open(info_path, "w", encoding="utf-8") as f:
                f.write(f"Guild ID: {guild.id}\n")
                f.write(f"Name: {guild.name}\n")
                f.write(f"Created: {guild.created_at}\n")
                f.write(f"Boosts: {guild.premium_subscription_count}\n")
                f.write(f"Boost Tier: {guild.premium_tier}\n")
                f.write(f"Member Count: {guild.member_count}\n")
                vanity = getattr(guild, "vanity_url_code", None)
                if vanity:
                    f.write(f"Vanity URL: https://discord.gg/{vanity}\n")
                f.write(f"Features: {', '.join(guild.features)}\n")

            members_path = os.path.join(base_folder, "members.txt")
            with open(members_path, "w", encoding="utf-8") as f:
                for member in guild.members:
                    f.write(f"{member.name}#{member.discriminator} ({member.id})\n")

            for role in guild.roles:
                path = os.path.join(roles_folder, f"{safe_filename(role.name)}.txt")
                with open(path, "w", encoding="utf-8") as f:
                    f.write(f"Name: {role.name}\n")
                    f.write(f"ID: {role.id}\n")
                    f.write(f"Color: {str(role.color)}\n")
                    f.write(f"Permissions: {role.permissions.value}\n")

            for emoji in guild.emojis:
                ext = "gif" if emoji.animated else "png"
                path = os.path.join(emojis_folder, f"{safe_filename(emoji.name)}.{ext}")
                await download_file(session, emoji.url, path, f"Emoji: {emoji.name}")

            for sticker in await guild.fetch_stickers():
                ext = "png" if sticker.format == nextcord.StickerFormatType.png else "json"
                path = os.path.join(stickers_folder, f"{safe_filename(sticker.name)}.{ext}")
                await download_file(session, sticker.url, path, f"Sticker: {sticker.name}")

        for channel in guild.channels:
            if isinstance(channel, nextcord.TextChannel):
                print(f"[INFO] Accessing text channel: #{channel.name}")
                try:
                    messages = []
                    seen_ids = set()
                    count = 0
                    last_msg = None

                    while True:
                        fetched_any = False
                        async for msg in channel.history(oldest_first=False, before=last_msg):
                            last_msg = msg
                            if msg.id in seen_ids:
                                continue
                            seen_ids.add(msg.id)

                            timestamp = msg.created_at.strftime("%H:%M %d/%m/%Y")
                            messages.insert(0, f"{timestamp} | {msg.author.name}: {msg.content}")
                            count += 1
                            if count % 50 == 0:
                                print(f"[DEBUG] Retrieved {count} messages from #{channel.name}...")

                            fetched_any = True

                        if not fetched_any:
                            break

                    filename = os.path.join(output_folder, f"{safe_filename(channel.name)}.txt")
                    with open(filename, "w", encoding="utf-8") as f:
                        f.write("\n".join(messages))

                    print(f"[SUCCESS] Saved {count} messages from #{channel.name}")
                    await asyncio.sleep(1)

                except Exception as e:
                    print(f"[ERROR] Could not read #{channel.name}: {e}")

            elif isinstance(channel, nextcord.VoiceChannel):
                filename = os.path.join(output_folder, f"{safe_filename(channel.name)}.txt")
                with open(filename, "w", encoding="utf-8") as f:
                    f.write(f"# {channel.name} (VOICE CHANNEL)\n")
                print(f"[INFO] Noted voice channel: #{channel.name}")

    except Exception as e:
        print(f"[FATAL] Exception during guild processing: {e}")

bot.run(BOT_TOKEN)
