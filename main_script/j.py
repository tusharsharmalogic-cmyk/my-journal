from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import os, json, subprocess, threading, webbrowser
from datetime import datetime

app = Flask(__name__, static_folder='.')
CORS(app)

# ============================================================
#  CONFIG — Yahan apna path badlo
# ============================================================
JOURNAL_DIR = "/storage/emulated/0/Journal"        # Local save folder
RCLONE_REMOTE = "gdrive:Journal"                   # rclone remote:folder
RCLONE_ENABLED = True                              # False karo agar rclone nahi chahiye
# ============================================================

os.makedirs(JOURNAL_DIR, exist_ok=True)

def open_browser():
    try:
        subprocess.Popen(['am', 'start', '-a', 'android.intent.action.VIEW', '-d', 'http://localhost:5001'])
    except:
        try: webbrowser.open('http://localhost:5001')
        except: pass

def rclone_sync(filepath, filename):
    """rclone se ek file Google Drive par upload karo"""
    if not RCLONE_ENABLED:
        return {'status': 'skipped', 'msg': 'rclone disabled'}
    try:
        result = subprocess.run(
            ['rclone', 'copy', filepath, RCLONE_REMOTE],
            capture_output=True, text=True, timeout=60
        )
        if result.returncode == 0:
            return {'status': 'success', 'msg': f'{filename} Drive par upload ho gaya!'}
        else:
            return {'status': 'error', 'msg': result.stderr.strip() or 'rclone error'}
    except FileNotFoundError:
        return {'status': 'error', 'msg': 'rclone install nahi hai! Termux mein: pkg install rclone'}
    except subprocess.TimeoutExpired:
        return {'status': 'error', 'msg': 'rclone timeout — internet check karo'}
    except Exception as e:
        return {'status': 'error', 'msg': str(e)}

def rclone_sync_all():
    """Puri journal directory sync karo"""
    if not RCLONE_ENABLED:
        return {'status': 'skipped', 'msg': 'rclone disabled'}
    try:
        result = subprocess.run(
            ['rclone', 'sync', JOURNAL_DIR, RCLONE_REMOTE],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return {'status': 'success', 'msg': 'Sari entries Drive par sync ho gayi!'}
        else:
            return {'status': 'error', 'msg': result.stderr.strip() or 'rclone sync error'}
    except FileNotFoundError:
        return {'status': 'error', 'msg': 'rclone install nahi hai! pkg install rclone'}
    except Exception as e:
        return {'status': 'error', 'msg': str(e)}

@app.route('/')
def index():
    return send_from_directory('.', 'journal.html')

@app.route('/config', methods=['GET'])
def get_config():
    """Frontend ko current config bhejo"""
    return jsonify({
        'journal_dir': JOURNAL_DIR,
        'rclone_remote': RCLONE_REMOTE,
        'rclone_enabled': RCLONE_ENABLED
    })

@app.route('/config', methods=['POST'])
def update_config():
    """Config update karo runtime mein"""
    global JOURNAL_DIR, RCLONE_REMOTE, RCLONE_ENABLED
    data = request.json
    if 'journal_dir' in data:
        JOURNAL_DIR = data['journal_dir']
        os.makedirs(JOURNAL_DIR, exist_ok=True)
    if 'rclone_remote' in data:
        RCLONE_REMOTE = data['rclone_remote']
    if 'rclone_enabled' in data:
        RCLONE_ENABLED = bool(data['rclone_enabled'])
    return jsonify({'status': 'ok', 'journal_dir': JOURNAL_DIR, 'rclone_remote': RCLONE_REMOTE})

@app.route('/save', methods=['POST'])
def save_entry():
    """Entry save karo — local + optional rclone sync"""
    data = request.json
    entry = data.get('entry')
    fmt = data.get('fmt', 'json')         # 'json' or 'txt'
    auto_sync = data.get('auto_sync', True)

    if not entry:
        return jsonify({'error': 'Entry data nahi mila!'}), 400

    # Filename banana
    title = entry.get('title', 'entry')
    slug = ''.join(c if c.isalnum() else '_' for c in title).lower()[:40]
    date_str = entry.get('date', datetime.now().isoformat())[:10]
    entry_id = entry.get('id', 'unknown')[:8]
    filename = f"{date_str}_{slug}_{entry_id}.{fmt}"
    filepath = os.path.join(JOURNAL_DIR, filename)

    # File content banana
    if fmt == 'json':
        content = json.dumps(entry, indent=2, ensure_ascii=False)
    else:
        content = entry_to_txt(entry)

    # Local save
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        return jsonify({'error': f'Local save fail: {str(e)}'}), 500

    # rclone sync (background mein)
    rclone_result = {'status': 'pending'}
    if auto_sync and RCLONE_ENABLED:
        def bg_sync():
            pass  # background thread result store karega
        result = rclone_sync(filepath, filename)
        rclone_result = result

    return jsonify({
        'status': 'ok',
        'filepath': filepath,
        'filename': filename,
        'rclone': rclone_result
    })

@app.route('/save_all', methods=['POST'])
def save_all():
    """Sari entries ek JSON file mein save karo + sync"""
    data = request.json
    entries = data.get('entries', [])
    if not entries:
        return jsonify({'error': 'Entries nahi mili!'}), 400

    date_str = datetime.now().strftime('%Y-%m-%d_%H-%M')
    filename = f"journal_all_{date_str}.json"
    filepath = os.path.join(JOURNAL_DIR, filename)

    content = json.dumps(entries, indent=2, ensure_ascii=False)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

    rclone_result = rclone_sync(filepath, filename) if RCLONE_ENABLED else {'status': 'skipped'}

    return jsonify({
        'status': 'ok',
        'filepath': filepath,
        'filename': filename,
        'count': len(entries),
        'rclone': rclone_result
    })

@app.route('/sync', methods=['POST'])
def manual_sync():
    """Manual rclone sync — puri directory"""
    data = request.json or {}
    entry_id = data.get('entry_id')
    filename = data.get('filename')

    if filename:
        # Specific file sync
        filepath = os.path.join(JOURNAL_DIR, filename)
        if not os.path.exists(filepath):
            return jsonify({'error': f'{filename} nahi mila local mein!'}), 404
        result = rclone_sync(filepath, filename)
    else:
        # Full directory sync
        result = rclone_sync_all()

    return jsonify(result)

@app.route('/list', methods=['GET'])
def list_entries():
    """Local saved files ki list"""
    try:
        files = []
        for f in sorted(os.listdir(JOURNAL_DIR), reverse=True):
            if f.endswith('.json') or f.endswith('.txt'):
                path = os.path.join(JOURNAL_DIR, f)
                size = os.path.getsize(path)
                mtime = os.path.getmtime(path)
                files.append({
                    'filename': f,
                    'size': size,
                    'modified': datetime.fromtimestamp(mtime).isoformat()
                })
        return jsonify({'files': files, 'dir': JOURNAL_DIR})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/eras', methods=['GET'])
def get_eras():
    """Device se eras load karo"""
    filepath = os.path.join(JOURNAL_DIR, 'eras.json')
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify({'status': 'ok', 'eras': data})
        else:
            return jsonify({'status': 'ok', 'eras': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/eras', methods=['POST'])
def save_eras():
    """Eras device par save karo"""
    data = request.json
    eras = data.get('eras', [])
    filepath = os.path.join(JOURNAL_DIR, 'eras.json')
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(eras, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    rclone_result = rclone_sync(filepath, 'eras.json') if RCLONE_ENABLED else {'status': 'skipped'}
    return jsonify({'status': 'ok', 'rclone': rclone_result})

@app.route('/draft', methods=['GET'])
def get_draft():
    """Device se draft load karo"""
    filepath = os.path.join(JOURNAL_DIR, 'draft.json')
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify({'status': 'ok', 'draft': data})
        else:
            return jsonify({'status': 'ok', 'draft': None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/draft', methods=['POST'])
def save_draft():
    """Draft device par save karo"""
    data = request.json
    draft = data.get('draft')
    filepath = os.path.join(JOURNAL_DIR, 'draft.json')
    if draft is None:
        # Draft delete karo (clear)
        if os.path.exists(filepath):
            os.remove(filepath)
        return jsonify({'status': 'ok'})
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(draft, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'status': 'ok'})

@app.route('/settings', methods=['GET'])
def get_settings():
    """Device se settings load karo"""
    filepath = os.path.join(JOURNAL_DIR, 'settings.json')
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify({'status': 'ok', 'settings': data})
        else:
            return jsonify({'status': 'ok', 'settings': None})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/settings', methods=['POST'])
def save_settings():
    """Settings device par save karo"""
    data = request.json
    settings = data.get('settings', {})
    filepath = os.path.join(JOURNAL_DIR, 'settings.json')
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(settings, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'status': 'ok'})

@app.route('/entries', methods=['GET'])
def get_all_entries():
    """Device se saari entries load karo"""
    filepath = os.path.join(JOURNAL_DIR, 'entries.json')
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify({'status': 'ok', 'entries': data})
        else:
            return jsonify({'status': 'ok', 'entries': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/entries', methods=['POST'])
def save_all_entries():
    """Saari entries ek file mein device par save karo (sirf local backup — Drive sync nahi)"""
    data = request.json
    entries = data.get('entries', [])
    filepath = os.path.join(JOURNAL_DIR, 'entries.json')
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entries, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    # NOTE: rclone sync intentionally nahi hai yahan — yeh sirf local state backup hai.
    # Drive sync sirf /save route se hoti hai (individual entry files ke liye).
    return jsonify({'status': 'ok', 'count': len(entries)})

@app.route('/drive_status', methods=['GET'])
def drive_status():
    """Google Drive pe konsi files hain — rclone lsf se check karo"""
    if not RCLONE_ENABLED:
        return jsonify({'status': 'disabled', 'files': []})
    try:
        # lsf with --format p (just filenames, no size/date)
        result = subprocess.run(
            ['rclone', 'lsf', RCLONE_REMOTE, '--format', 'p'],
            capture_output=True, text=True, timeout=30
        )
        if result.returncode != 0:
            # fallback: try simple lsf
            result2 = subprocess.run(
                ['rclone', 'lsf', RCLONE_REMOTE],
                capture_output=True, text=True, timeout=30
            )
            if result2.returncode != 0:
                return jsonify({'status': 'error', 'msg': result2.stderr.strip() or result.stderr.strip(), 'files': []})
            files = [f.strip() for f in result2.stdout.strip().split('\n') if f.strip() and f.endswith('.json')]
        else:
            files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip() and f.endswith('.json')]

        return jsonify({'status': 'ok', 'files': files, 'count': len(files)})
    except FileNotFoundError:
        return jsonify({'status': 'error', 'msg': 'rclone nahi mila', 'files': []})
    except subprocess.TimeoutExpired:
        return jsonify({'status': 'error', 'msg': 'Timeout — internet check karo', 'files': []})
    except Exception as e:
        return jsonify({'status': 'error', 'msg': str(e), 'files': []})

@app.route('/upload_entry', methods=['POST'])
def upload_entry():
    """Ek specific entry ko Drive par upload karo"""
    data = request.json
    entry = data.get('entry')
    if not entry:
        return jsonify({'error': 'Entry nahi mili!'}), 400

    title = entry.get('title', 'entry')
    slug = ''.join(c if c.isalnum() else '_' for c in title).lower()[:40]
    date_str = entry.get('date', datetime.now().isoformat())[:10]
    entry_id = entry.get('id', 'unknown')[:8]
    filename = f"{date_str}_{slug}_{entry_id}.json"
    filepath = os.path.join(JOURNAL_DIR, filename)

    # Pehle local save karo
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(entry, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({'status': 'error', 'msg': f'Local save fail: {str(e)}'}), 500

    # Drive par upload
    result = rclone_sync(filepath, filename)
    return jsonify({
        'status': result['status'],
        'msg': result.get('msg', ''),
        'filename': filename,
        'entry_id': entry.get('id')
    })

@app.route('/upload_bulk', methods=['POST'])
def upload_bulk():
    """Multiple entries ek ek karke upload karo — progress track ke liye"""
    data = request.json
    entries = data.get('entries', [])
    if not entries:
        return jsonify({'error': 'Entries nahi mili!'}), 400

    results = []
    for entry in entries:
        title = entry.get('title', 'entry')
        slug = ''.join(c if c.isalnum() else '_' for c in title).lower()[:40]
        date_str = entry.get('date', datetime.now().isoformat())[:10]
        entry_id = entry.get('id', 'unknown')[:8]
        filename = f"{date_str}_{slug}_{entry_id}.json"
        filepath = os.path.join(JOURNAL_DIR, filename)

        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(entry, f, indent=2, ensure_ascii=False)
            rr = rclone_sync(filepath, filename)
            results.append({
                'entry_id': entry.get('id'),
                'filename': filename,
                'status': rr['status'],
                'msg': rr.get('msg', '')
            })
        except Exception as e:
            results.append({
                'entry_id': entry.get('id'),
                'filename': filename,
                'status': 'error',
                'msg': str(e)
            })

    success = sum(1 for r in results if r['status'] == 'success')
    return jsonify({'status': 'ok', 'results': results, 'success': success, 'total': len(entries)})

# ============================================================
#  OTHER MODULES — Custom HTML files
# ============================================================
MODULES_SUBDIR = "modules"  # JOURNAL_DIR ke andar ek subfolder

def get_modules_dir():
    d = os.path.join(JOURNAL_DIR, MODULES_SUBDIR)
    os.makedirs(d, exist_ok=True)
    return d

@app.route('/modules/list', methods=['GET'])
def list_modules():
    """Saved HTML modules ki list do"""
    d = get_modules_dir()
    files = []
    for f in sorted(os.listdir(d)):
        if f.endswith('.html'):
            path = os.path.join(d, f)
            files.append({
                'filename': f,
                'name': f[:-5],  # .html hata do
                'size': os.path.getsize(path),
                'modified': datetime.fromtimestamp(os.path.getmtime(path)).isoformat()
            })
    return jsonify({'status': 'ok', 'files': files, 'dir': d})

@app.route('/modules/save', methods=['POST'])
def save_module():
    """Ek HTML module save karo"""
    data = request.json
    filename = data.get('filename', '').strip()
    content = data.get('content', '')
    if not filename:
        return jsonify({'error': 'Filename nahi diya!'}), 400
    if not filename.endswith('.html'):
        filename += '.html'
    # Safe filename
    filename = ''.join(c if (c.isalnum() or c in '._- ') else '_' for c in filename)
    filepath = os.path.join(get_modules_dir(), filename)
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    rclone_result = rclone_sync(filepath, filename) if RCLONE_ENABLED else {'status': 'skipped'}
    return jsonify({'status': 'ok', 'filename': filename, 'filepath': filepath, 'rclone': rclone_result})

@app.route('/modules/meta', methods=['GET'])
def get_modules_meta():
    """Modules ka meta (icon, last_opened) do"""
    meta_path = os.path.join(get_modules_dir(), 'modules_meta.json')
    try:
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                return jsonify({'status': 'ok', 'meta': json.load(f)})
        return jsonify({'status': 'ok', 'meta': {}})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/modules/meta', methods=['POST'])
def save_modules_meta():
    """Module ka icon/meta update karo"""
    data = request.json
    key = data.get('key', '').strip()
    if not key:
        return jsonify({'error': 'key nahi diya'}), 400
    meta_path = os.path.join(get_modules_dir(), 'modules_meta.json')
    try:
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
        if key not in meta:
            meta[key] = {}
        for field in ['icon', 'color', 'desc']:
            if field in data:
                meta[key][field] = data[field]
        with open(meta_path, 'w', encoding='utf-8') as f:
            json.dump(meta, f, ensure_ascii=False)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/modules/rename', methods=['POST'])
def rename_module():
    """Module rename karo"""
    data = request.json
    old_name = data.get('old', '').strip()
    new_name = data.get('new', '').strip()
    if not old_name or not new_name:
        return jsonify({'error': 'old/new naam chahiye'}), 400
    d = get_modules_dir()
    old_path = os.path.join(d, old_name if old_name.endswith('.html') else old_name + '.html')
    new_filename = (new_name if new_name.endswith('.html') else new_name + '.html')
    new_filename = ''.join(c if (c.isalnum() or c in '._- ') else '_' for c in new_filename)
    new_path = os.path.join(d, new_filename)
    if not os.path.exists(old_path):
        return jsonify({'error': 'File nahi mili'}), 404
    if os.path.exists(new_path):
        return jsonify({'error': 'Yeh naam pehle se exist karta hai'}), 400
    os.rename(old_path, new_path)
    # meta bhi update karo
    meta_path = os.path.join(d, 'modules_meta.json')
    try:
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as f:
                meta = json.load(f)
            old_key = old_name[:-5] if old_name.endswith('.html') else old_name
            new_key = new_filename[:-5]
            if old_key in meta:
                meta[new_key] = meta.pop(old_key)
                with open(meta_path, 'w', encoding='utf-8') as f:
                    json.dump(meta, f, ensure_ascii=False)
    except: pass
    return jsonify({'status': 'ok', 'new_filename': new_filename})


@app.route('/modules/delete', methods=['POST'])
def delete_module():
    """Ek module delete karo"""
    data = request.json
    filename = data.get('filename', '').strip()
    if not filename or '/' in filename or '..' in filename:
        return jsonify({'error': 'Invalid filename'}), 400
    filepath = os.path.join(get_modules_dir(), filename)
    if not os.path.exists(filepath):
        return jsonify({'error': 'File nahi mili!'}), 404
    os.remove(filepath)
    return jsonify({'status': 'ok', 'deleted': filename})

@app.route('/modules/file/<path:filename>', methods=['GET'])
def serve_module(filename):
    """HTML module serve karo — upar back bar inject karo"""
    filepath = os.path.join(get_modules_dir(), filename)
    if not os.path.exists(filepath):
        return "File not found", 404
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    display_name = filename[:-5] if filename.endswith('.html') else filename

    # Update last_opened in meta
    meta_path = os.path.join(get_modules_dir(), 'modules_meta.json')
    try:
        meta = {}
        if os.path.exists(meta_path):
            with open(meta_path, 'r', encoding='utf-8') as mf:
                meta = json.load(mf)
        key = filename[:-5] if filename.endswith('.html') else filename
        if key not in meta:
            meta[key] = {}
        meta[key]['last_opened'] = datetime.now().isoformat()
        with open(meta_path, 'w', encoding='utf-8') as mf:
            json.dump(meta, mf, ensure_ascii=False)
    except:
        pass

    from flask import Response
    return Response(content, mimetype='text/html')

@app.route('/check_rclone', methods=['GET'])
def check_rclone():
    """rclone available hai ya nahi check karo"""
    result = subprocess.run(['which', 'rclone'], capture_output=True, text=True)
    available = bool(result.stdout.strip())
    remotes = []
    if available:
        try:
            r = subprocess.run(['rclone', 'listremotes'], capture_output=True, text=True, timeout=5)
            remotes = [x.strip() for x in r.stdout.strip().split('\n') if x.strip()]
        except: pass
    return jsonify({'available': available, 'remotes': remotes})

def format_time(seconds):
    seconds = int(seconds or 0)
    m, s = divmod(seconds, 60)
    return f"{m:02d}:{s:02d}"

def entry_to_txt(entry):
    """HTML ke entryToTxt se exactly match karta hai — import compatible"""
    from datetime import datetime
    try:
        date = datetime.fromisoformat(entry.get('date','').replace('Z','+00:00')).strftime('%A, %B %d, %Y at %I:%M:%S %p')
    except:
        date = entry.get('date', '')

    tags = entry.get('tags', [])
    tags_str = ' '.join('#' + t for t in tags) if tags else 'None'

    out = f"TITLE: {entry.get('title', 'Untitled')}\n"
    out += f"DATE: {date}\n"
    out += f"DATE_ISO: {entry.get('date', datetime.now().isoformat())}\n"
    out += f"MOOD: {entry.get('mood', 'Not set') or 'Not set'}\n"
    out += f"CATEGORY: {entry.get('category', 'None') or 'None'}\n"
    out += f"TAGS: {tags_str}\n"
    out += f"WORDS: {entry.get('wordCount', 0)}\n"
    out += f"WRITING TIME: {format_time(entry.get('writingTime', 0))}\n"

    cq = entry.get('cqAnswers', {})
    if cq:
        out += '\n--- CUSTOM QUESTIONS ---\n'
        for q, a in cq.items():
            if a:
                out += f'Q: {q}\nA: {a}\n'

    out += '\n--- ENTRY ---\n'
    out += (entry.get('text', '') or '') + '\n'
    out += '\n' + '=' * 60 + '\n'
    return out

@app.route('/braindump', methods=['GET'])
def get_braindump():
    """Brain Dump items device se load karo"""
    filepath = os.path.join(JOURNAL_DIR, 'braindump.json')
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify({'status': 'ok', 'items': data})
        else:
            return jsonify({'status': 'ok', 'items': []})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/braindump', methods=['POST'])
def save_braindump():
    """Brain Dump items device par save karo"""
    data = request.json
    items = data.get('items', [])
    filepath = os.path.join(JOURNAL_DIR, 'braindump.json')
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(items, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    rclone_result = rclone_sync(filepath, 'braindump.json') if RCLONE_ENABLED else {'status': 'skipped'}
    return jsonify({'status': 'ok', 'count': len(items), 'rclone': rclone_result})

@app.route('/braindump_categories', methods=['GET'])
def get_braindump_categories():
    """Custom Brain Dump categories load karo"""
    filepath = os.path.join(JOURNAL_DIR, 'braindump_categories.json')
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
            return jsonify({'status': 'ok', 'categories': data})
        else:
            # Default categories
            defaults = [
                {'id': 'video', 'label': '📹 Video dekhni hai'},
                {'id': 'idea', 'label': '💡 Idea'},
                {'id': 'kaam', 'label': '✅ Kaam karna hai'},
                {'id': 'padhai', 'label': '📚 Padhai related'},
                {'id': 'baad', 'label': '⏳ Exam ke baad'},
                {'id': 'other', 'label': '🗂 Other'}
            ]
            return jsonify({'status': 'ok', 'categories': defaults})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/braindump_categories', methods=['POST'])
def save_braindump_categories():
    """Custom Brain Dump categories save karo"""
    data = request.json
    categories = data.get('categories', [])
    filepath = os.path.join(JOURNAL_DIR, 'braindump_categories.json')
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(categories, f, indent=2, ensure_ascii=False)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    return jsonify({'status': 'ok', 'count': len(categories)})

# ============================================================
#  KV STORE — localStorage jaisa, device storage mein
#  GET  /kv/<app>/<key>        → value lo
#  POST /kv/<app>/<key>        → value save karo  {value: ...}
#  DELETE /kv/<app>/<key>      → key delete karo
#  GET  /kv/<app>              → app ki saari keys lo
# ============================================================

def get_kv_dir():
    d = os.path.join(JOURNAL_DIR, 'kv_store')
    os.makedirs(d, exist_ok=True)
    return d

def kv_filepath(app, key):
    # Safe names
    app = ''.join(c if (c.isalnum() or c in '-_') else '_' for c in app)
    key = ''.join(c if (c.isalnum() or c in '-_') else '_' for c in key)
    app_dir = os.path.join(get_kv_dir(), app)
    os.makedirs(app_dir, exist_ok=True)
    return os.path.join(app_dir, key + '.json')

@app.route('/kv/<app>/<key>', methods=['GET'])
def kv_get(app, key):
    """Ek key ki value lo"""
    fp = kv_filepath(app, key)
    if not os.path.exists(fp):
        return jsonify({'status': 'ok', 'value': None})
    try:
        with open(fp, 'r', encoding='utf-8') as f:
            data = json.load(f)
        return jsonify({'status': 'ok', 'value': data.get('value')})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/kv/<app>/<key>', methods=['POST'])
def kv_set(app, key):
    """Ek key ki value save karo"""
    data = request.json
    if data is None or 'value' not in data:
        return jsonify({'error': 'value nahi mila!'}), 400
    fp = kv_filepath(app, key)
    try:
        with open(fp, 'w', encoding='utf-8') as f:
            json.dump({
                'app': app,
                'key': key,
                'value': data['value'],
                'updated': datetime.now().isoformat()
            }, f, ensure_ascii=False, indent=2)
        return jsonify({'status': 'ok'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/kv/<app>/<key>', methods=['DELETE'])
def kv_delete(app, key):
    """Ek key delete karo"""
    fp = kv_filepath(app, key)
    if os.path.exists(fp):
        os.remove(fp)
    return jsonify({'status': 'ok'})

@app.route('/kv/<app>', methods=['GET'])
def kv_list(app, key=None):
    """App ki saari keys aur values lo"""
    app_safe = ''.join(c if (c.isalnum() or c in '-_') else '_' for c in app)
    app_dir = os.path.join(get_kv_dir(), app_safe)
    if not os.path.exists(app_dir):
        return jsonify({'status': 'ok', 'data': {}})
    result = {}
    for fname in os.listdir(app_dir):
        if fname.endswith('.json'):
            fp = os.path.join(app_dir, fname)
            try:
                with open(fp, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                result[d.get('key', fname[:-5])] = d.get('value')
            except:
                pass
    return jsonify({'status': 'ok', 'data': result})

if __name__ == '__main__':
    print("📓 Journal Server chal raha hai: http://localhost:5001")
    print(f"📁 Entries save hongi: {JOURNAL_DIR}")
    print(f"☁️  rclone remote: {RCLONE_REMOTE}")
    threading.Timer(1.5, open_browser).start()
    app.run(host='0.0.0.0', port=5001, debug=False)
