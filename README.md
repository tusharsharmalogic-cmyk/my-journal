# My Journal

A self-hosted, privacy-first journaling app that runs on your Android device (Termux) — no cloud, no accounts, no subscriptions. Your notes live on your phone, optionally synced to your own Google Drive via `rclone`.

---

## Features

### Core journaling

- Rich entry editor with title, body, mood, category and tags
- Mood tracking with emoji per entry
- Categories (Life Analysis, Daily Log, etc.) with custom eras
- Freeform hashtags per entry
- Custom questions — attach Q&A prompts to each entry
- Live word count and writing-time stats
- Auto-save drafts — never lose what you typed
- Multiple export formats: JSON and plain TXT

### Life chapters (Eras)

- Define eras (life periods) to organise entries by chapter
- Attach entries to eras for a timeline view

### Brain Dump (inbox)

- Quick-capture thoughts, ideas, videos, tasks
- Custom categories — fully editable
- Promote brain-dump items into full journal entries

### Modules system

- Extend the app with custom HTML modules — mini-apps served inside the journal
- Built-in examples include Daily Planner, Sunday Planner, Fitness Tracker
- Per-module icons and last-opened tracking
- Each module can store its own state on the server

### Sync and backup

- Local-first: all data stays on device
- Google Drive sync via rclone — one-click or auto-sync on save
- Bulk upload to push all entries to Drive in one go
- Drive status view to see which files are already uploaded
- KV store API — localStorage-like server-side key/value store for modules

### UX

- Warm paper-like theme with dark mode
- Mobile-first, touch-friendly
- Fully offline-capable (except Drive sync)

---

## Project Structure

    Journal/
    ├── main_script/
    │   ├── j.py              Flask backend server
    │   └── journal.html      Main SPA frontend
    ├── modules/              Custom HTML mini-apps (empty by default)
    ├── entries.json          Bulk entries backup (local)
    ├── braindump.json        Brain dump items
    ├── braindump_categories.json
    ├── eras.json             Life chapters
    ├── draft.json            Auto-saved draft
    ├── requirements.txt      Python dependencies
    └── .gitignore            Ignores personal data

---

## Getting Started

### Requirements

- Android device with Termux (or any Linux with Python 3.8+)
- Flask and Flask-CORS
- rclone (optional, for Google Drive sync)

### Install

    # 1. Install Python dependencies
    pip install -r requirements.txt

    # 2. (Optional) Install rclone for Drive sync
    pkg install rclone
    rclone config        # set up a remote named "gdrive"

### Configure

Edit `main_script/j.py` and update:

    JOURNAL_DIR    = "/storage/emulated/0/Journal"   # where entries are saved
    RCLONE_REMOTE  = "gdrive:Journal"                # rclone remote:folder
    RCLONE_ENABLED = True                            # False to disable Drive sync

### Run

    cd main_script
    python j.py

Then open **http://localhost:5001** in your Android browser.

The server auto-opens the browser on Android via `am start`.

### Remote access (same Wi-Fi)

The server binds to `0.0.0.0:5001`. Find your phone's IP:

    ip addr | grep 192.168

Open `http://<phone-ip>:5001` from any device on the same network.

---

## API Reference

All endpoints return JSON. Base URL: `http://localhost:5001`.

### Entries and saving

| Method | Endpoint        | Purpose                                    |
|--------|-----------------|--------------------------------------------|
| POST   | `/save`         | Save one entry (local + Drive)             |
| POST   | `/save_all`     | Save all entries to a timestamped file     |
| POST   | `/upload_entry` | Upload one specific entry to Drive         |
| POST   | `/upload_bulk`  | Upload many entries one by one             |
| GET    | `/list`         | List locally saved files                   |
| GET    | `/entries`      | Get all entries from entries.json          |
| POST   | `/entries`      | Save all entries locally                   |

### Eras, drafts, settings

| Method   | Endpoint    | Purpose                |
|----------|-------------|------------------------|
| GET/POST | `/eras`     | Load / save life eras  |
| GET/POST | `/draft`    | Load / save draft      |
| GET/POST | `/settings` | Load / save settings   |

### Brain Dump

| Method   | Endpoint               | Purpose                    |
|----------|------------------------|----------------------------|
| GET/POST | `/braindump`           | Load / save brain dump     |
| GET/POST | `/braindump_categories`| Load / save BD categories  |

### Modules

| Method   | Endpoint                   | Purpose                        |
|----------|----------------------------|--------------------------------|
| GET      | `/modules/list`            | List saved modules             |
| POST     | `/modules/save`            | Save a custom HTML module      |
| GET/POST | `/modules/meta`            | Load / save module icons/meta  |
| POST     | `/modules/rename`          | Rename a module                |
| POST     | `/modules/delete`          | Delete a module                |
| GET      | `/modules/file/<filename>` | Serve a module's HTML          |

### Sync and config

| Method   | Endpoint        | Purpose                              |
|----------|-----------------|--------------------------------------|
| POST     | `/sync`         | Manual rclone sync (single or all)   |
| GET      | `/drive_status` | List files already on Drive          |
| GET      | `/check_rclone` | Check if rclone is available         |
| GET/POST | `/config`       | Get / update runtime config          |

### KV store (for modules)

| Method | Endpoint          | Purpose                 |
|--------|-------------------|-------------------------|
| GET    | `/kv/<app>/<key>` | Get a value             |
| POST   | `/kv/<app>/<key>` | Set a value             |
| DELETE | `/kv/<app>/<key>` | Delete a key            |
| GET    | `/kv/<app>`       | Get all keys for an app |

---

## How Modules Work

A "module" is a standalone HTML file placed in `modules/`. It gets served with a wrapper bar so you can return to the journal. Modules can:

- Store state on the server via `/kv/<app>/<key>`
- Be renamed, deleted, or given a custom icon
- Pull fresh data each time they open

To add a module: drop any `.html` file into `modules/` — it appears in the module hub on the next open.

---

## Google Drive Sync

Sync is optional and powered by rclone:

1. Install: `pkg install rclone`
2. Configure a Google Drive remote: `rclone config` (name it `gdrive`)
3. Set `RCLONE_REMOTE = "gdrive:Journal"` in `j.py`
4. Save an entry — it auto-uploads
5. Or use the Sync button in the UI for a full push

To disable entirely, set `RCLONE_ENABLED = False`.

---

## Privacy

- No cloud, no accounts, no telemetry — everything is local by default
- Drive sync goes to your own Google Drive via your own rclone config
- Personal data files (`settings.json`, `kv_store/`, `.nomedia`) are gitignored
- Safe to publish the code publicly

---

## Tech Stack

- Backend: Python, Flask, Flask-CORS, rclone
- Frontend: Vanilla JavaScript, HTML, CSS (no framework, no build step)
- Storage: Flat JSON files on device
- Theme: Custom paper-like design with dark mode

---

## Credits

Made with care by [@tusharsharmalogic-cmyk](https://github.com/tusharsharmalogic-cmyk)

Other projects: [COREX](https://github.com/tusharsharmalogic-cmyk/COREX) — 2D Phaser game