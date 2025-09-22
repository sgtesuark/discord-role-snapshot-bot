# discord-role-snapshot-bot

> Discord bot to export role members as CSV snapshots into a chosen channel.

## ✨ Features
- Slash command `/snapshot`  
- Exports all members of a selected role to **CSV**  
- CSV includes:  
  - Timestamp (format configurable via `.env`)  
  - Username (server display name)  
  - Discord ID  
- CSV is **Excel-friendly** (UTF-8 BOM, semicolon `;`, text qualifiers, CRLF line endings)  
- Uploads the file to a chosen channel (or fallback to default/current channel)  
- Role is referenced in the message without pinging  
- Multi-language support (currently **de** and **en**)  
- Timezone and date format fully configurable  

## 🛠️ Requirements
- Python **3.10+** (tested with 3.12)  
- `discord.py`
- `python-dotenv` 

Install dependencies:
```bash
pip install -U discord.py python-dotenv
```

## ⚙️ Setup
1. Create a bot in the Discord Developer Portal.
2. Under Bot → Privileged Gateway Intents, enable SERVER MEMBERS INTENT.
3. Invite the bot with scopes `bot` and `applications.commands`.
   - Permissions needed: Send Messages, Attach Files, View Channels.
4. Clone this repository and create a `.env` file:
   
        # === Required ===
        DISCORD_TOKEN=your_bot_token_here
        
        # === Optional ===
        # Default channel (if no channel is passed to /snapshot)
        DEFAULT_CHANNEL_ID=123456789012345678
        
        # Language for bot messages
        # Supported: de, en
        BOT_LANG=en
        
        # Timezone for timestamp formatting
        # Must be a valid IANA timezone, e.g. Europe/Berlin, UTC, America/New_York
        BOT_TZ=Europe/Berlin
        
        # Custom date format (overrides BOT_LANG defaults)
        # Examples:
        #   BOT_DATEFMT=%d.%m.%Y %H:%M:%S
        #   BOT_DATEFMT=%Y-%m-%d %H:%M:%S
        #   BOT_DATEFMT=%d.%m.%Y %H:%M:%S
        BOT_DATEFMT=%d.%m.%Y %H:%M:%S
6. Run the bot:
   python snapshot_role_bot.py

## ▶️ Usage
In your Discord server, use the slash command:
```bash
/snapshot role:@MemberRole [channel:#target-channel]
```
- role – required, choose the role you want to snapshot
- channel – optional, choose a channel to post the CSV
  (falls back to DEFAULT_CHANNEL_ID or the current channel)

## Example output in Discord
```bash
📸 Snapshot for role 🔑 Member - 710 members
🕒 Created at: 21.09.2025 04:20:33
```
…and a CSV file is attached.

## 📂 CSV Format
"Timestamp";"Username";"Discord-ID"
"21.09.2025 16:45:12";"Alice";"123456789012345678"
"21.09.2025 16:45:12";"Bob";"234567890123456789"

⚠️ Depending on your .env settings, the timestamp format will change, e.g.:

- German default: 22.09.2025 04:20:33
- English default: 2025-09-22 04:20:33
- Custom via BOT_DATEFMT: whatever format you specify

## 📜 License
MIT
