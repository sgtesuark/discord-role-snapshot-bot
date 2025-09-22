# snapshot_role_bot.py
# Bot functionality:
#   - Slash command /snapshot
#   - Creates a CSV snapshot of all members of a given role
#   - CSV columns: (localized headers) Timestamp; Username; Discord-ID
#   - Uploads the CSV into a target channel (parameter > DEFAULT_CHANNEL_ID from .env > current channel)
#
# .env configuration:
#   DISCORD_TOKEN=...
#   DEFAULT_CHANNEL_ID=123...
#   BOT_LANG=de|en
#   BOT_TZ=Europe/Berlin|UTC|...
#   BOT_DATEFMT=%d.%m.%Y %H:%M:%S   (optional; overrides language defaults)

import os
import io
import csv
import json
from datetime import datetime
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import discord
from discord import app_commands, AllowedMentions
from discord.ext import commands
from dotenv import load_dotenv

# =========================
# Configuration / Setup
# =========================
load_dotenv()

TOKEN = os.getenv("DISCORD_TOKEN")
DEFAULT_CHANNEL_ID_ENV = os.getenv("DEFAULT_CHANNEL_ID")  # Optional fallback channel
FORCED_LANG = (os.getenv("BOT_LANG") or "").strip().lower()  # 'de' | 'en'
LANG_FILE = os.getenv("LANG_FILE") or "lang.json"
BOT_TZ = (os.getenv("BOT_TZ") or "UTC").strip()  # Default: UTC
BOT_DATEFMT = os.getenv("BOT_DATEFMT")  # Optional → overrides language-based format

# Validate timezone at startup
try:
    CONFIG_TZ = ZoneInfo(BOT_TZ)
    TZ_VALID = True
except (ZoneInfoNotFoundError, Exception):
    CONFIG_TZ = ZoneInfo("UTC")
    TZ_VALID = False
    print(f"[WARN] Invalid BOT_TZ '{BOT_TZ}' in .env. Falling back to UTC.")

intents = discord.Intents.default()
intents.guilds = True
intents.members = True  # Privileged intent (must be enabled in Dev Portal)

bot = commands.Bot(command_prefix="!", intents=intents)
tree = bot.tree

# =========================
# Localization
# =========================
_LANG_CACHE: dict = {}

def load_lang():
    """Load lang.json into cache, with built-in fallback if missing."""
    global _LANG_CACHE
    try:
        with open(LANG_FILE, "r", encoding="utf-8") as f:
            _LANG_CACHE = json.load(f)
    except FileNotFoundError:
        _LANG_CACHE = {
            "de": {
                "cmd.description": "CSV-Snapshot aller Mitglieder mit einer Rolle; Upload in einen Kanal.",
                "arg.role": "Rolle, deren Mitglieder erfasst werden",
                "arg.channel": "(Optional) Zielkanal für die CSV (sonst Default- oder aktueller Kanal)",
                "err.need_manage_guild": "❌ Du benötigst die Berechtigung **Server verwalten**.",
                "err.guild_only": "❌ Dieser Befehl kann nur in einem Server genutzt werden.",
                "err.no_target_channel": "❌ Konnte keinen Zielkanal ermitteln.",
                "err.missing_perms": "❌ Fehlende Rechte in {channel} (Nachrichten senden / Dateien anhängen / Kanal ansehen).",
                "err.send_forbidden": "❌ Keine Berechtigung, in {channel} zu posten.",
                "err.unexpected_send": "❌ Unerwarteter Fehler beim Senden der Datei: `{error}`",
                "warn.invalid_tz": "⚠️ Ungültige Zeitzone in .env: '{tz}'. Es wird **UTC** verwendet. "
                                   "Setze `BOT_TZ` auf eine gültige IANA-Zeitzone (z. B. Europe/Berlin).",
                "ok.posted": "✅ Snapshot erstellt und in {channel} gepostet.",
                "post.header": "📸 Snapshot für Rolle <@&{role_id}> – {count} Nutzer",
                "post.timestamp": "🕒 Erstellt am: {timestamp}",
                "csv.header.timestamp": "Zeitstempel",
                "csv.header.username": "Username",
                "csv.header.discord_id": "Discord-ID"
            },
            "en": {
                "cmd.description": "CSV snapshot of members with a role; uploads to a channel.",
                "arg.role": "Role whose members to snapshot",
                "arg.channel": "(Optional) Target channel for the CSV (else default/current)",
                "err.need_manage_guild": "❌ You need the **Manage Server** permission.",
                "err.guild_only": "❌ This command can only be used in a server.",
                "err.no_target_channel": "❌ Could not determine a target channel.",
                "err.missing_perms": "❌ Missing permissions in {channel} (Send Messages / Attach Files / View Channel).",
                "err.send_forbidden": "❌ No permission to post in {channel}.",
                "err.unexpected_send": "❌ Unexpected error while sending the file: `{error}`",
                "warn.invalid_tz": "⚠️ Invalid timezone in .env: '{tz}'. Using **UTC**. "
                                   "Set `BOT_TZ` to a valid IANA zone (e.g., Europe/Berlin).",
                "ok.posted": "✅ Snapshot created and posted in {channel}.",
                "post.header": "📸 Snapshot for role <@&{role_id}> – {count} members",
                "post.timestamp": "🕒 Created at: {timestamp}",
                "csv.header.timestamp": "Timestamp",
                "csv.header.username": "Username",
                "csv.header.discord_id": "Discord ID"
            }
        }

def pick_lang(interaction: discord.Interaction) -> str:
    """Determine language: .env BOT_LANG > interaction/guild locale > fallback."""
    if FORCED_LANG and FORCED_LANG in _LANG_CACHE:
        return FORCED_LANG

    def _to_locale_code(x) -> str:
        if x is None:
            return ""
        v = getattr(x, "value", None)
        return v if isinstance(v, str) else str(x)

    raw = _to_locale_code(getattr(interaction, "locale", None)) or _to_locale_code(getattr(interaction, "guild_locale", None))
    cand = raw.lower()
    if cand.startswith("de") and "de" in _LANG_CACHE:
        return "de"
    if cand.startswith("en") and "en" in _LANG_CACHE:
        return "en"
    return "de" if "de" in _LANG_CACHE else "en"

def t(lang: str, key: str, **kwargs) -> str:
    """Translation helper with placeholder replacement."""
    text = _LANG_CACHE.get(lang, {}).get(key) or _LANG_CACHE.get("en", {}).get(key) or _LANG_CACHE.get("de", {}).get(key) or key
    try:
        return text.format_map(kwargs)
    except Exception:
        return text

load_lang()

# =========================
# Helper functions
# =========================
def format_timestamp(dt: datetime, lang: str) -> str:
    """
    Format timestamp:
      - If BOT_DATEFMT is set: use exactly this format
      - Else: use language defaults ('de' -> dd.mm.yyyy HH:MM:SS, 'en' -> yyyy-mm-dd HH:MM:SS)
    Timezone comes from validated CONFIG_TZ (fallback UTC).
    """
    if BOT_DATEFMT:
        fmt = BOT_DATEFMT
    elif lang == "de":
        fmt = "%d.%m.%Y %H:%M:%S"
    else:
        fmt = "%Y-%m-%d %H:%M:%S"
    return dt.astimezone(CONFIG_TZ).strftime(fmt)

def make_filename(role_name: str) -> str:
    """Generate a safe filename from role name + current timestamp (always in Europe/Berlin for local consistency)."""
    now = datetime.now(ZoneInfo("Europe/Berlin")).strftime("%Y-%m-%d_%H-%M-%S")
    safe_role = "".join(c for c in role_name if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_")
    return f"snapshot_{safe_role}_{now}.csv"

async def ensure_full_member_cache(guild: discord.Guild) -> None:
    """Try to fully load all members into the cache."""
    try:
        await guild.chunk()
    except Exception:
        pass
    try:
        async for _ in guild.fetch_members(limit=None):
            pass
    except Exception:
        pass

def user_has_manage_guild(interaction: discord.Interaction) -> bool:
    """Check if the invoking user has 'Manage Server' permission."""
    return interaction.user.guild_permissions.manage_guild

def resolve_default_channel(guild: discord.Guild):
    """Resolve DEFAULT_CHANNEL_ID from .env, return channel or None."""
    if not DEFAULT_CHANNEL_ID_ENV:
        return None
    try:
        cid = int(DEFAULT_CHANNEL_ID_ENV)
        return guild.get_channel(cid)
    except Exception:
        return None

# =========================
# Slash command
# =========================
@tree.command(
    name="snapshot",
    description="CSV snapshot of all members of a role; upload to a channel."
)
@app_commands.describe(
    role="Role whose members will be included",
    channel="(Optional) Target channel for the CSV (else default/current)"
)
async def snapshot(
    interaction: discord.Interaction,
    role: discord.Role,
    channel: discord.TextChannel | None = None
):
    lang = pick_lang(interaction)

    # Ephemeral warning if timezone is invalid
    if not TZ_VALID and not interaction.response.is_done():
        await interaction.response.send_message(
            t(lang, "warn.invalid_tz", tz=BOT_TZ),
            ephemeral=True
        )

    # Permission check
    if not user_has_manage_guild(interaction):
        if interaction.response.is_done():
            return await interaction.followup.send(t(lang, "err.need_manage_guild"), ephemeral=True)
        else:
            return await interaction.response.send_message(t(lang, "err.need_manage_guild"), ephemeral=True)

    if not interaction.response.is_done():
        await interaction.response.defer(thinking=True, ephemeral=True)

    guild = interaction.guild
    if guild is None:
        return await interaction.followup.send(t(lang, "err.guild_only"), ephemeral=True)

    target_channel: discord.TextChannel | None = channel or resolve_default_channel(guild) or interaction.channel  # type: ignore
    if target_channel is None:
        return await interaction.followup.send(t(lang, "err.no_target_channel"), ephemeral=True)

    await ensure_full_member_cache(guild)

    snapshot_time = format_timestamp(datetime.now(), lang)

    members = list(role.members)
    members.sort(key=lambda m: (m.display_name or m.name).lower())

    # Build CSV (Excel-friendly)
    buf = io.StringIO()
    writer = csv.writer(
        buf,
        delimiter=';',
        lineterminator='\r\n',
        quoting=csv.QUOTE_ALL,
        quotechar='"',
        escapechar='\\'
    )
    writer.writerow([
        t(lang, "csv.header.timestamp"),
        t(lang, "csv.header.username"),
        t(lang, "csv.header.discord_id")
    ])
    for m in members:
        username = (m.display_name or m.name).replace("\r", " ").replace("\n", " ").strip()
        writer.writerow([snapshot_time, username, str(m.id)])

    csv_bytes = buf.getvalue().encode("utf-8-sig")
    buf.close()

    filename = make_filename(role.name)
    file = discord.File(io.BytesIO(csv_bytes), filename=filename)

    # Channel permission checks
    try:
        perms = target_channel.permissions_for(guild.me)  # type: ignore
        if not (perms.send_messages and perms.attach_files and perms.view_channel):
            return await interaction.followup.send(
                t(lang, "err.missing_perms", channel=getattr(target_channel, "mention", "#channel")),
                ephemeral=True
            )
    except Exception:
        pass

    # Send message + file
    try:
        await target_channel.send(
            content=(
                f"{t(lang, 'post.header', role_id=role.id, count=len(members))}\n"
                f"{t(lang, 'post.timestamp', timestamp=snapshot_time)}"
            ),
            file=file,
            allowed_mentions=AllowedMentions.none()
        )
    except discord.Forbidden:
        return await interaction.followup.send(
            t(lang, "err.send_forbidden", channel=getattr(target_channel, "mention", "#channel")),
            ephemeral=True
        )
    except Exception as e:
        return await interaction.followup.send(
            t(lang, "err.unexpected_send", error=str(e)),
            ephemeral=True
        )

    await interaction.followup.send(
        t(lang, "ok.posted", channel=getattr(target_channel, "mention", "#channel")),
        ephemeral=True
    )

# =========================
# Bot lifecycle
# =========================
@bot.event
async def on_ready():
    try:
        await tree.sync()
        tz_key = getattr(CONFIG_TZ, "key", str(CONFIG_TZ))
        print(f"Logged in as {bot.user} | Slash commands synced. (BOT_TZ='{BOT_TZ}', valid={TZ_VALID}, using='{tz_key}')")
        if not TZ_VALID:
            print(f"[WARN] Invalid BOT_TZ '{BOT_TZ}'. Using UTC. Set BOT_TZ to a valid IANA zone (e.g., Europe/Berlin).")
    except Exception as e:
        print(f"Error while syncing commands: {e}")

if __name__ == "__main__":
    if not TOKEN:
        raise RuntimeError("DISCORD_TOKEN missing. Please set it in .env.")
    bot.run(TOKEN)
