# Cerlen

A Discord book club bot for one server. Python 3.11+ and discord.py.

This is an early build. Working now: `/book`, `/profile`, `/config` (personal details, favorites and admin settings) and `/help`. Club reads, reviews, deadlines and stats come in later steps.

## One-time Discord setup

1. Go to the Discord Developer Portal, create an application, and open **Bot**.
2. Click **Reset Token** and copy it. Keep it private.
3. On the same page, switch on **Server Members Intent**.
4. Open **OAuth2 > URL Generator**, tick `bot` and `applications.commands`, give it permission to view channels, send messages, embed links, create public threads and send messages in threads, then open the link to invite Cerlen.
5. In Discord, enable Developer Mode (Settings > Advanced), right-click your server icon and choose **Copy Server ID**.

## Run on Windows (development)

```bat
py -3 -m venv .venv
.venv\Scripts\pip install -r requirements-dev.txt
copy .env.example .env
```

Open `.env` and fill in `DISCORD_TOKEN` and `GUILD_ID`. Then:

```bat
.venv\Scripts\python -m pytest
run.bat
```

Commands appear in your server within a few seconds of starting.

## Cerlen's lines

Copy `voice.example.json` to `data/voice.json` and edit it. Any line you do not write uses a plain default. A list of lines means Cerlen picks one at random. Restart the bot after changes.

## Move to the Linux server

Nothing in the code is Windows-specific: paths use `pathlib`, the timezone database comes from the `tzdata` package, and the files use LF line endings.

```bash
sudo useradd --system --home /opt/cerlen cerlen
sudo mkdir -p /opt/cerlen && sudo chown cerlen: /opt/cerlen
# copy the project here (without .venv, .env or data/), then as the cerlen user:
cd /opt/cerlen
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env && nano .env      # token and server ID
sudo cp deploy/cerlen.service /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now cerlen
journalctl -u cerlen -f                 # watch the logs
```

To bring your data across, copy `cerlen.db` (and `voice.json`) from the Windows `data` folder into `/var/lib/cerlen` while the bot is stopped.

## Notes

- Admins are people with **Manage Server**, or the role set with `/config admin-role`.
- Book data comes from Open Library and Google Books. Goodreads and StoryGraph are links only; their ratings are typed in by an admin.
- The database has no per-server column on most tables, because Cerlen serves one server.
