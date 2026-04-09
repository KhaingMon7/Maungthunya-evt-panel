import os
import sys
import time
import subprocess
import threading
import uuid
import random
import datetime
import json
import logging
import warnings
import signal
import shutil
from datetime import date
from functools import wraps

# Third-party imports
from flask import Flask, request, render_template_string, redirect, url_for, flash, session, jsonify, send_file
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
import requests

# ============================================
# FIX: Clear Werkzeug environment variables
# ============================================
for env in ['WERKZEUG_SERVER_FD', 'WERKZEUG_RUN_MAIN', 'WERKZEUG_LOADED']:
    if env in os.environ:
        del os.environ[env]

os.environ['FLASK_ENV'] = 'production'
os.environ['FLASK_DEBUG'] = '0'

warnings.filterwarnings('ignore')

# Disable Flask/Werkzeug logs
log = logging.getLogger('werkzeug')
log.disabled = True
log.setLevel(logging.ERROR)

# ============================================
# AUTO PATH DETECTION
# ============================================

def get_script_info():
    if getattr(sys, 'frozen', False):
        script_path = sys.executable
    else:
        script_path = os.path.abspath(__file__)

    script_dir = os.path.dirname(script_path)

    return {
        'path': script_path,
        'dir': script_dir,
        'python': sys.executable
    }

SCRIPT_INFO = get_script_info()
BASE_DIR = SCRIPT_INFO['dir']

# ============================================
# FLASK APP INITIALIZATION
# ============================================

app = Flask(__name__)
app.secret_key = os.urandom(24).hex()

# Session configuration
app.config['SESSION_COOKIE_NAME'] = 'evt_session'
app.config['SESSION_COOKIE_HTTPONLY'] = True
app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
app.config['PERMANENT_SESSION_LIFETIME'] = datetime.timedelta(days=365)
app.config['REMEMBER_COOKIE_DURATION'] = datetime.timedelta(days=365)
app.config['REMEMBER_COOKIE_HTTPONLY'] = True
app.config['REMEMBER_COOKIE_SAMESITE'] = 'Lax'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'admin_login'
login_manager.remember_cookie_duration = datetime.timedelta(days=365)

# Database file paths
KEY_DB = os.path.join(BASE_DIR, "keys.json")
CONFIG_FILE = "/etc/evt_config"

# Admin Credentials
ADMIN_USER = "admin"
ADMIN_PASS = "admin123"

# Telegram Bot Token
TELEGRAM_BOT_TOKEN = "8759015117:AAHqedT8u_MGOCa4gVRE7GGZCkcaeykTblo"
TELEGRAM_ADMIN_ID = 7624981442

# GitHub License Check URL
GITHUB_IP_URL = "https://gist.githubusercontent.com/KhaingMon7/fc09897e8650c31c6bc736c21f29308f/raw/evt_whitelist."

# ============================================
# CLASSES
# ============================================

class Admin(UserMixin):
    def __init__(self, id): 
        self.id = id

# ============================================
# USER LOADER
# ============================================

@login_manager.user_loader
def load_user(user_id):
    if user_id == ADMIN_USER:
        return Admin(user_id)
    return None

# ============================================
# LICENSE CHECK SYSTEM
# ============================================

def get_vps_ip():
    try:
        response = requests.get('https://api.ipify.org', timeout=10)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    try:
        response = requests.get('https://icanhazip.com', timeout=10)
        if response.status_code == 200:
            return response.text.strip()
    except:
        pass
    return None

def check_license():
    current_ip = get_vps_ip()
    if not current_ip:
        return False
    try:
        response = requests.get(GITHUB_IP_URL, timeout=15)
        if response.status_code == 200:
            config = response.json()
            if "vps_list" in config:
                ips = [vps.get('vps_ip') for vps in config.get('vps_list', []) if vps.get('active', True)]
                if current_ip in ips:
                    return True
            elif "vps_ip" in config:
                if current_ip == config.get("vps_ip"):
                    return True
    except:
        pass
    return False

# ============================================
# CORE FUNCTIONS
# ============================================

def load_keys():
    if not os.path.exists(KEY_DB):
        return {}
    try:
        with open(KEY_DB, "r") as f:
            data = json.load(f)
            return data.get('keys', data) if isinstance(data, dict) else {}
    except:
        return {}

def save_keys(keys):
    with open(KEY_DB, "w") as f:
        json.dump({"keys": keys}, f, indent=4)

def get_evt_config():
    conf = {"DOMAIN": "Not Set", "NS_DOMAIN": "Not Set"}
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                for line in f:
                    if "=" in line:
                        k, v = line.strip().split("=", 1)
                        conf[k.strip().upper()] = v.strip().strip('"').strip("'")
        except:
            pass
    return conf

def get_slowdns_pubkey():
    key = "None"
    if os.path.exists("/etc/dnstt/server.pub"):
        key = subprocess.getoutput("cat /etc/dnstt/server.pub").strip()
    else:
        key = subprocess.getoutput("find /etc/dnstt -name '*.pub' 2>/dev/null | xargs cat 2>/dev/null | head -n 1").strip()
    return key if key and len(key) > 5 else "None"

def get_live_ports():
    try:
        ports = {}
        ssh = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -E 'sshd|ssh' | awk '{print $4}' | awk -F: '{print $NF}' | sort -u | tr '\\n' ' ' | xargs").strip()
        if ssh and ssh != "":
            ports["SSH"] = ssh
        else:
            ports["SSH"] = "22"
            
        ws = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -E 'python|node|ws|nginx|apache' | awk '{print $4}' | sed 's/.*://' | sort -u | tr '\\n' ' ' | xargs").strip()
        if ws and ws != "":
            ports["WS"] = ws
        else:
            ports["WS"] = "80, 443"
            
        stnl = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -E 'stunnel|stunnel4' | awk '{print $4}' | sed 's/.*://' | sort -u | tr '\\n' ' ' | xargs").strip()
        if stnl and stnl != "":
            ports["STNL"] = stnl
        else:
            ports["STNL"] = "Not Found"
            
        dropbear = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -i dropbear | awk '{print $4}' | sed 's/.*://' | sort -u | tr '\\n' ' ' | xargs").strip()
        if dropbear and dropbear != "":
            ports["DBEAR"] = dropbear
        else:
            ports["DBEAR"] = "Not Found"
            
        ovpn = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -E 'openvpn|ovpn' | awk '{print $4}' | sed 's/.*://' | sort -u | tr '\\n' ' ' | xargs").strip()
        if ovpn and ovpn != "":
            ports["OVPN"] = ovpn
        else:
            ports["OVPN"] = "Not Found"
            
        squid = subprocess.getoutput("netstat -tunlp 2>/dev/null | grep LISTEN | grep -i squid | awk '{print $4}' | sed 's/.*://' | sort -u | tr '\\n' ' ' | xargs").strip()
        if squid and squid != "":
            ports["SQUID"] = squid
        else:
            ports["SQUID"] = "Not Found"
            
        return ports
    except:
        return {"SSH": "22", "WS": "80, 443", "STNL": "Not Found", "DBEAR": "Not Found", "OVPN": "Not Found", "SQUID": "Not Found"}

def get_user_online_status(username):
    try:
        pids = subprocess.getoutput(f"pgrep -u {username} sshd 2>/dev/null").split()
        online_num = len(pids) if pids and pids[0] != "" else 0
        return online_num > 0, online_num
    except:
        return False, 0

def sync_user_to_system(username, password, expiry, limit):
    try:
        check_user = subprocess.run(["id", username], capture_output=True)
        if check_user.returncode == 0:
            subprocess.run(f"echo '{username}:{password}' | chpasswd", shell=True, capture_output=True)
        else:
            if expiry and expiry != "No Expiry":
                subprocess.run(["useradd", "-e", expiry, "-M", "-s", "/bin/false", username], capture_output=True)
            else:
                subprocess.run(["useradd", "-M", "-s", "/bin/false", username], capture_output=True)
            subprocess.run(f"echo '{username}:{password}' | chpasswd", shell=True, capture_output=True)
        subprocess.run(f"sed -i '/^{username} hard/d' /etc/security/limits.conf", shell=True, capture_output=True)
        subprocess.run(f"echo '{username} hard maxlogins {limit}' >> /etc/security/limits.conf", shell=True, capture_output=True)
        return True
    except:
        return False

def sync_all_users_to_system():
    keys = load_keys()
    synced_count = 0
    error_count = 0
    for key, user_data in keys.items():
        username = user_data.get('username')
        password = user_data.get('password')
        expiry = user_data.get('expiry')
        limit = user_data.get('limit', 1)
        if username and password:
            if sync_user_to_system(username, password, expiry, limit):
                synced_count += 1
            else:
                error_count += 1
    return synced_count, error_count

# ============================================
# AUTO KILL BACKGROUND THREAD
# ============================================

def auto_kill_background():
    while True:
        try:
            current_date_str = date.today().strftime("%Y-%m-%d")
            keys = load_keys()
            deleted_any = False
            keys_to_delete = []

            for k, v in keys.items():
                exp_date = v.get('expiry')
                if exp_date and exp_date != "No Expiry":
                    if exp_date < current_date_str:
                        user = v.get('username')
                        subprocess.run(["userdel", "-f", user], capture_output=True)
                        subprocess.run(f"sed -i '/^{user} hard/d' /etc/security/limits.conf", shell=True, capture_output=True)
                        keys_to_delete.append(k)
                        deleted_any = True

            for k in keys_to_delete:
                del keys[k]

            if deleted_any:
                save_keys(keys)

            for k, v in keys.items():
                user = v.get('username')
                if not user:
                    continue
                limit = int(v.get('limit', 1))
                pids_out = subprocess.getoutput(f"pgrep -u {user} sshd 2>/dev/null").strip()
                pids = pids_out.split() if pids_out else []
                if len(pids) > limit:
                    excess_pids = pids[limit:]
                    for pid in excess_pids:
                        subprocess.run(["kill", "-9", pid], capture_output=True)
        except:
            pass
        time.sleep(5)

threading.Thread(target=auto_kill_background, daemon=True).start()

# ============================================
# TELEGRAM BOT
# ============================================

def send_telegram_message(chat_id, text):
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        payload = {'chat_id': chat_id, 'text': text, 'parse_mode': 'Markdown'}
        requests.post(url, data=payload, timeout=10)
    except:
        pass

def check_telegram_updates():
    offset = 0
    while True:
        try:
            url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates"
            params = {'offset': offset, 'timeout': 30}
            response = requests.get(url, params=params, timeout=35)
            if response.status_code == 200:
                updates = response.json().get('result', [])
                for update in updates:
                    offset = update['update_id'] + 1
                    message = update.get('message')
                    if not message:
                        continue
                    chat_id = message['chat']['id']
                    text = message.get('text', '')
                    user_id = message['from']['id']
                    if user_id != TELEGRAM_ADMIN_ID:
                        send_telegram_message(chat_id, "❌ Unauthorized!")
                        continue
                    if text.startswith('/'):
                        parts = text.split()
                        command = parts[0].lower()
                        if command == '/start':
                            msg = """🤖 *EVT SSH Manager Bot*

📌 *Commands:*

/create username password days limit - Create new SSH user
/list - Show all users
/info username - Show user information
/delete username - Delete user
/ports - Show active ports

📝 *Examples:*
/create john pass123 30 2
/info john
/delete john"""
                            send_telegram_message(chat_id, msg)
                        elif command == '/create' and len(parts) >= 5:
                            try:
                                username = parts[1]
                                password = parts[2]
                                days = int(parts[3])
                                limit = int(parts[4])
                                if days < 1: days = 30
                                if limit < 1: limit = 1
                                keys = load_keys()
                                if any(v.get('username') == username for v in keys.values()):
                                    send_telegram_message(chat_id, f"❌ Username '{username}' already exists!")
                                    continue
                                expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
                                key = "EVT-" + str(uuid.uuid4()).upper()[:8]
                                keys[key] = {
                                    "username": username, "password": password, "expiry": expiry,
                                    "limit": limit, "created_by": "Telegram Bot",
                                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                                }
                                save_keys(keys)
                                sync_user_to_system(username, password, expiry, limit)
                                conf = get_evt_config()
                                pubkey = get_slowdns_pubkey()
                                msg = f"""✅ *SSH Account Created!*

🔑 Key: `{key}`
👤 Username: `{username}`
🔑 Password: `{password}`
📆 Expiry: `{expiry}`
📱 Limit: `{limit}`

🌐 Domain: {conf.get('DOMAIN')}
📡 NameServer: {conf.get('NS_DOMAIN')}
🔑 Public Key: `{pubkey}`

━━━━━━━━━━━━━━━
📡 *EVT SSH Manager*"""
                                send_telegram_message(chat_id, msg)
                            except:
                                pass
                        elif command == '/list':
                            keys = load_keys()
                            if not keys:
                                send_telegram_message(chat_id, "📭 No users found!")
                                continue
                            online_count = 0
                            user_list = []
                            for key, data in keys.items():
                                username = data['username']
                                is_online, _ = get_user_online_status(username)
                                if is_online:
                                    online_count += 1
                                status_icon = "🟢" if is_online else "⚫"
                                user_list.append(f"{status_icon} `{username}` | 📅 {data['expiry']} | 📱 {data['limit']}")
                            msg = f"📋 *Users List*\n━━━━━━━━━━━━━━━\nTotal: {len(keys)} | Online: {online_count}\n━━━━━━━━━━━━━━━\n"
                            msg += "\n".join(user_list[:50])
                            send_telegram_message(chat_id, msg)
                        elif command == '/info' and len(parts) >= 2:
                            username = parts[1]
                            keys = load_keys()
                            user_data = None
                            user_key = None
                            for key, data in keys.items():
                                if data.get('username') == username:
                                    user_data = data
                                    user_key = key
                                    break
                            if not user_data:
                                send_telegram_message(chat_id, f"❌ User '{username}' not found!")
                                continue
                            is_online, online_num = get_user_online_status(username)
                            status_text = "✅ Online" if is_online else "❌ Offline"
                            pubkey = get_slowdns_pubkey()
                            conf = get_evt_config()
                            msg = f"""🔐 *User Information*

🔑 Key: `{user_key}`
👤 Username: `{user_data['username']}`
🔑 Password: `{user_data['password']}`
📱 Limit: `{user_data['limit']}`
📆 Expiry: `{user_data['expiry']}`
📶 Status: {status_text}
📊 Online: `{online_num}/{user_data['limit']}` devices

🌐 Domain: {conf.get('DOMAIN')}
📡 NameServer: {conf.get('NS_DOMAIN')}
🔑 Public Key: `{pubkey}`"""
                            send_telegram_message(chat_id, msg)
                        elif command == '/delete' and len(parts) >= 2:
                            username = parts[1]
                            keys = load_keys()
                            found_key = None
                            for key, data in keys.items():
                                if data.get('username') == username:
                                    found_key = key
                                    break
                            if not found_key:
                                send_telegram_message(chat_id, f"❌ User '{username}' not found!")
                                continue
                            subprocess.run(["userdel", "-f", username], capture_output=True)
                            subprocess.run(f"sed -i '/^{username} hard/d' /etc/security/limits.conf", shell=True, capture_output=True)
                            del keys[found_key]
                            save_keys(keys)
                            send_telegram_message(chat_id, f"✅ User '{username}' deleted successfully!")
                        elif command == '/ports':
                            ports = get_live_ports()
                            msg = "🔌 *Active Ports*\n━━━━━━━━━━━━━━━\n"
                            for name, port in ports.items():
                                msg += f"• {name}: `{port}`\n"
                            send_telegram_message(chat_id, msg)
        except:
            pass
        time.sleep(1)

def run_telegram_bot():
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
        requests.get(url, timeout=5)
        check_telegram_updates()
    except:
        pass

# ============================================
# HTML TEMPLATES
# ============================================

LOGIN_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>EVT SSH Manager - Login</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --gold: #FFD700; --bg: #000; --card: #111; }
        body { background: var(--bg); color: #fff; font-family: 'Segoe UI', sans-serif; min-height: 100vh; display: flex; align-items: center; justify-content: center; }
        .neon-card { background: var(--card); border: 2px solid var(--gold); border-radius: 20px; padding: 40px; width: 420px; box-shadow: 0 0 30px rgba(255,215,0,0.2); }
        .btn-gold { background: var(--gold); color: #000; font-weight: bold; border-radius: 8px; border: none; padding: 12px; transition: 0.3s; width: 100%; }
        .btn-gold:hover { background: #fff; transform: scale(1.02); }
        .form-control-custom { background: #000 !important; border: 1px solid #444 !important; color: var(--gold) !important; padding: 12px; border-radius: 8px; width: 100%; }
        .form-control-custom:focus { border-color: var(--gold) !important; box-shadow: 0 0 10px rgba(255,215,0,0.3) !important; outline: none; }
        .text-gold { color: var(--gold) !important; }
        .alert { background: #2c2c2c; color: #ff6b6b; border: 1px solid #ff6b6b; transition: opacity 0.5s ease; }
        .form-check-input:checked { background-color: var(--gold); border-color: var(--gold); }
        .input-group-custom { display: flex; align-items: center; position: relative; width: 100%; }
        .input-group-custom input { padding-left: 45px; padding-right: 45px; width: 100%; }
        .input-group-prepend { position: absolute; left: 12px; top: 50%; transform: translateY(-50%); z-index: 10; color: var(--gold); }
        .toggle-password { position: absolute; right: 12px; top: 50%; transform: translateY(-50%); cursor: pointer; color: var(--gold); z-index: 10; background: transparent; border: none; font-size: 16px; }
        .toggle-password:hover { color: #fff; }
        .alert-container { min-height: 60px; margin-bottom: 15px; }
    </style>
</head>
<body>
    <div class="neon-card text-center">
        <img src="https://raw.githubusercontent.com/snaymyo/logo/refs/heads/main/evt.png" alt="EVT Logo" style="width: 80px; height: 80px; border-radius: 12px; margin-bottom: 20px;">
        <h3 class="text-gold fw-bold mb-2">EVT SSH MANAGER</h3>
        <p class="text-secondary small mb-4">Admin Login Panel</p>

        <div class="alert-container">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ category if category != 'message' else 'danger' }} py-2 small mb-2 flash-message">
                            <i class="fas fa-info-circle me-2"></i>{{ message }}
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
        </div>

        <form method="POST" id="loginForm" action="/login">
            <div class="mb-3">
                <div class="input-group-custom">
                    <span class="input-group-prepend"><i class="fas fa-user"></i></span>
                    <input type="text" name="username" id="username" class="form-control-custom" placeholder="Username" required autocomplete="username">
                </div>
            </div>
            <div class="mb-4">
                <div class="input-group-custom">
                    <span class="input-group-prepend"><i class="fas fa-lock"></i></span>
                    <input type="password" name="password" id="password" class="form-control-custom" placeholder="Password" required autocomplete="current-password">
                    <i class="fas fa-eye toggle-password" id="togglePassword"></i>
                </div>
            </div>
            <div class="form-check text-start mb-4">
                <input class="form-check-input" type="checkbox" name="remember" id="remember" checked>
                <label class="form-check-label text-secondary small" for="remember">Remember Me (Keep me logged in for 1 year)</label>
            </div>
            <button type="submit" class="btn-gold">LOGIN</button>
        </form>
        <div class="mt-4"><small class="text-secondary">© 2024 EVT SSH Manager</small></div>
    </div>
    <script>
        document.addEventListener('DOMContentLoaded', function() {
            const flashMessages = document.querySelectorAll('.flash-message');
            if (flashMessages.length > 0) {
                setTimeout(function() {
                    flashMessages.forEach(function(msg) {
                        msg.style.opacity = '0';
                        setTimeout(function() { if (msg.parentNode) msg.remove(); }, 500);
                    });
                }, 2000);
            }
        });
        const togglePassword = document.getElementById('togglePassword');
        const passwordInput = document.getElementById('password');
        if (togglePassword && passwordInput) {
            togglePassword.addEventListener('click', function() {
                const type = passwordInput.getAttribute('type') === 'password' ? 'text' : 'password';
                passwordInput.setAttribute('type', type);
                this.classList.toggle('fa-eye');
                this.classList.toggle('fa-eye-slash');
            });
        }
        const loginForm = document.getElementById('loginForm');
        const rememberCheckbox = document.getElementById('remember');
        const usernameInput = document.getElementById('username');
        function loadSavedUsername() {
            const cookies = document.cookie.split(';');
            for(let i = 0; i < cookies.length; i++) {
                let cookie = cookies[i].trim();
                if (cookie.startsWith('saved_username=')) {
                    let savedUsername = decodeURIComponent(cookie.substring('saved_username='.length));
                    if (usernameInput && savedUsername) usernameInput.value = savedUsername;
                    break;
                }
            }
        }
        function saveUsernameToCookie(username, remember) {
            if (remember) {
                let expiry = new Date();
                expiry.setFullYear(expiry.getFullYear() + 1);
                document.cookie = "saved_username=" + encodeURIComponent(username) + "; expires=" + expiry.toUTCString() + "; path=/";
            } else {
                document.cookie = "saved_username=; expires=Thu, 01 Jan 1970 00:00:00 UTC; path=/";
            }
        }
        if (loginForm) {
            loginForm.addEventListener('submit', function(e) {
                const username = usernameInput ? usernameInput.value : '';
                const remember = rememberCheckbox ? rememberCheckbox.checked : false;
                saveUsernameToCookie(username, remember);
            });
        }
        loadSavedUsername();
        if (loginForm) {
            loginForm.action = window.location.href;
            if (passwordInput) passwordInput.setAttribute('autocomplete', 'current-password');
            if (usernameInput) usernameInput.setAttribute('autocomplete', 'username');
        }
    </script>
</body>
</html>
"""

DASHBOARD_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <meta http-equiv="refresh" content="60">
    <title>EVT SSH Manager - Dashboard</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css">
    <style>
        :root { --gold: #FFD700; --bg: #000; --card: #111; }
        body { background: var(--bg); color: #fff; font-family: 'Segoe UI', sans-serif; }
        
        .logo-center { text-align: center; margin-bottom: 20px; margin-top: 20px; }
        .logo-center img { width: 250px; height: 250px; border-radius: 15px; border: 2px solid var(--gold); box-shadow: 0 0 20px rgba(255,215,0,0.4); transition: transform 0.3s; }
        .logo-center img:hover { transform: scale(1.05); }
        
        .main-title { font-size: 72px; font-weight: 900; color: #FFD700; text-transform: uppercase; letter-spacing: 8px; text-shadow: 0 0 25px rgba(255,215,0,0.7); margin-bottom: 10px; }
        .sub-title { font-size: 20px; color: #FFD700; letter-spacing: 2px; font-weight: 400; margin-bottom: 5px; }
        .region-time { font-size: 16px; color: #FFD700; letter-spacing: 1px; font-family: monospace; margin-top: 5px; padding: 8px 20px; background: rgba(0,0,0,0.5); display: inline-block; border-radius: 30px; border: 1px solid rgba(255,215,0,0.3); }
        .region-time i { margin-right: 8px; color: var(--gold); }
        
        .neon-card { background: var(--card); border: 1px solid #333; border-radius: 15px; padding: 20px; margin-bottom: 25px; box-shadow: 0 5px 15px rgba(0,0,0,0.5); }
        .btn-gold { background: var(--gold); color: #000; font-weight: bold; border-radius: 8px; border: none; padding: 10px 20px; transition: 0.3s; }
        .btn-gold:hover { background: #fff; transform: scale(1.02); }
        .btn-edit { background: #2c3e50; color: var(--gold); border: 1px solid var(--gold); border-radius: 8px; padding: 5px 15px; font-size: 12px; transition: 0.3s; margin-left: 10px; }
        .btn-edit:hover { background: var(--gold); color: #000; }
        .form-control-custom { background: #000 !important; border: 1px solid #444 !important; color: var(--gold) !important; padding: 12px; border-radius: 8px; }
        .form-control-custom:focus { border-color: var(--gold) !important; box-shadow: 0 0 10px rgba(255,215,0,0.3) !important; }
        .table-scroll { max-height: 450px; overflow-y: auto; border: 1px solid #333; border-radius: 10px; }
        .table-scroll::-webkit-scrollbar { width: 6px; }
        .table-scroll::-webkit-scrollbar-thumb { background: var(--gold); border-radius: 10px; }
        .table { width: 100%; margin: 0; background: transparent !important; color: #fff !important; }
        .table thead th { background: #1a1a1a !important; color: var(--gold); padding: 15px; position: sticky; top: 0; border-bottom: 1px solid #333; }
        .table tbody tr { background: transparent !important; }
        .table tbody td { background: transparent !important; padding: 12px 15px; border-bottom: 1px solid #222; vertical-align: middle; }
        .table tbody tr:hover { background: rgba(255,215,0,0.05) !important; }
        .text-gold { color: var(--gold) !important; }
        
        .username-cell { font-weight: bold; color: #FFD700 !important; font-family: monospace; font-size: 16px; display: inline-block; }
        .password-cell { font-family: monospace; font-size: 14px; font-weight: bold; color: #00ff00; background: transparent !important; }
        .expiry-cell { font-weight: bold; color: #FFD700 !important; font-family: monospace; font-size: 16px; display: inline-block; }
        .device-cell { font-weight: bold; }
        .device-online { color: #28a745; }
        .device-offline { color: #FFD700; }
        .device-limit { color: #ff6b6b; }
        .status-online { background: #28a745; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 12px; display: inline-block; }
        .status-offline { background: #6c757d; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 12px; display: inline-block; }
        .status-expired { background: #dc3545; color: #fff; padding: 4px 10px; border-radius: 20px; font-size: 12px; display: inline-block; }
        
        .ports-grid { display: grid; grid-template-columns: repeat(6, 1fr); gap: 12px; margin-top: 10px; }
        .port-card { background: #1a1a1a; border: 1px solid #333; border-radius: 12px; padding: 12px 8px; text-align: center; transition: all 0.3s ease; }
        .port-card:hover { border-color: var(--gold); transform: translateY(-2px); box-shadow: 0 5px 15px rgba(255,215,0,0.1); }
        .port-label { font-size: 11px; font-weight: bold; color: var(--gold); text-transform: uppercase; letter-spacing: 1px; margin-bottom: 8px; }
        .port-value { font-size: 14px; font-weight: bold; color: #28a745; font-family: monospace; word-break: break-word; }
        
        @media (max-width: 992px) {
            .logo-center img { width: 250px; height: 250px; }
            .ports-grid { grid-template-columns: repeat(3, 1fr); gap: 10px; }
            .main-title { font-size: 48px; letter-spacing: 5px; }
            .sub-title { font-size: 16px; }
            .region-time { font-size: 14px; }
        }
        @media (max-width: 576px) {
            .logo-center img { width: 250px; height: 250px; }
            .ports-grid { grid-template-columns: repeat(2, 1fr); gap: 8px; }
            .main-title { font-size: 28px; letter-spacing: 3px; }
            .sub-title { font-size: 12px; }
            .region-time { font-size: 11px; padding: 5px 12px; }
        }
        
        .alert-success { background: #1a3a1a; color: #90ee90; border: 1px solid #2ecc2e; }
        .alert-danger { background: #3a1a1a; color: #ff6b6b; border: 1px solid #ff6b6b; }
        .alert-warning { background: #3a3a1a; color: #ffd700; border: 1px solid #ffd700; }
        .copy-icon { cursor: pointer; margin-left: 8px; color: var(--gold); transition: 0.3s; display: inline-block; }
        .copy-icon:hover { color: #fff; transform: scale(1.1); }
        .btn-outline-custom { background: transparent; border: 1px solid var(--gold); color: var(--gold); border-radius: 8px; padding: 8px 20px; transition: 0.3s; margin: 0 5px; text-decoration: none; display: inline-block; }
        .btn-outline-custom:hover { background: var(--gold); color: #000; text-decoration: none; }
        .footer-buttons { display: flex; justify-content: center; gap: 20px; margin-top: 20px; flex-wrap: wrap; }
        .refresh-indicator { position: fixed; bottom: 10px; right: 10px; background: rgba(0,0,0,0.7); padding: 5px 10px; border-radius: 20px; font-size: 11px; color: #888; z-index: 999; }
    </style>
</head>
<body>
    <div class="refresh-indicator"><i class="fas fa-sync-alt fa-fw"></i> Auto-refresh: 60s</div>
    
    <div class="container-fluid px-md-5 py-4">
        <div class="logo-center">
            <img src="https://raw.githubusercontent.com/snaymyo/logo/refs/heads/main/evt.png" alt="EVT Logo">
        </div>
        
        <div class="text-center mb-4">
            <h1 class="main-title">EVT SSH MANAGER</h1>
            <p class="sub-title">Professional SSH Account Management System</p>
            <div class="region-time" id="regionTimeDisplay">
                <i class="fas fa-map-marker-alt"></i> <span id="regionText">Loading...</span> | 
                <i class="fas fa-clock"></i> <span id="regionCurrentTime">Loading...</span>
            </div>
        </div>

        <div class="row g-3 mb-4 text-center">
            <div class="col-md-3 col-6"><div class="neon-card"><div class="text-warning small"><i class="fas fa-clock"></i> UPTIME</div><div class="fw-bold fs-5">{{ info.uptime }}</div></div></div>
            <div class="col-md-3 col-6"><div class="neon-card"><div class="text-warning small"><i class="fas fa-memory"></i> RAM</div><div class="fw-bold fs-5">{{ info.ram }}</div></div></div>
            <div class="col-md-3 col-6"><div class="neon-card"><div class="text-warning small"><i class="fas fa-users"></i> TOTAL USERS</div><div class="fw-bold fs-5 text-info">{{ info.total }}</div></div></div>
            <div class="col-md-3 col-6"><div class="neon-card"><div class="text-warning small"><i class="fas fa-globe"></i> ONLINE</div><div class="fw-bold fs-5 text-success" id="online-count">{{ info.online }}</div></div></div>
        </div>

        <div class="neon-card border-info">
            <h6 class="text-info mb-3"><i class="fas fa-dns"></i> DNS SETTINGS <button class="btn-edit" id="toggleDnsEditBtn" onclick="toggleDnsEdit()"><i class="fas fa-edit"></i> Edit</button></h6>
            <div id="dnsDisplayMode">
                <div class="row">
                    <div class="col-md-6"><div class="p-2 bg-black border border-secondary rounded mb-2"><small class="text-warning">DOMAIN</small><br><b class="text-white" id="domain-display">{{ config.DOMAIN }}</b><i class="fas fa-copy copy-icon" onclick="copyToClipboard('domain-display')" title="Copy Domain"></i></div></div>
                    <div class="col-md-6"><div class="p-2 bg-black border border-secondary rounded mb-2"><small class="text-warning">NAME SERVER</small><br><b class="text-white" id="ns-display">{{ config.NS_DOMAIN }}</b><i class="fas fa-copy copy-icon" onclick="copyToClipboard('ns-display')" title="Copy NameServer"></i></div></div>
                    <div class="col-md-12 mt-2"><div class="p-2 bg-black border border-secondary rounded"><small class="text-warning">PUBLIC KEY</small><br><code class="text-white small" id="pubkey-display">{{ dns_key }}</code><i class="fas fa-copy copy-icon" onclick="copyToClipboard('pubkey-display')" title="Copy Public Key"></i></div></div>
                </div>
            </div>
            <div id="dnsEditMode" style="display: none;">
                <form action="/update_dns_settings" method="POST">
                    <div class="row">
                        <div class="col-md-6"><div class="mb-3"><label class="text-warning small">DOMAIN</label><input type="text" name="domain" class="form-control-custom" value="{{ config.DOMAIN }}" required></div></div>
                        <div class="col-md-6"><div class="mb-3"><label class="text-warning small">NAME SERVER</label><input type="text" name="ns_domain" class="form-control-custom" value="{{ config.NS_DOMAIN }}" required></div></div>
                        <div class="col-md-12"><div class="mb-3"><label class="text-warning small">PUBLIC KEY</label><input type="text" name="pubkey" class="form-control-custom" value="{{ dns_key }}" placeholder="Enter public key"></div></div>
                        <div class="col-md-12"><button type="submit" class="btn-gold w-100"><i class="fas fa-save"></i> Save DNS Settings</button><button type="button" class="btn-outline-custom w-100 mt-2" onclick="toggleDnsEdit()"><i class="fas fa-times"></i> Cancel</button></div>
                    </div>
                </form>
            </div>
        </div>

        <div class="neon-card border-info">
            <h6 class="text-info mb-3"><i class="fas fa-plug"></i> ACTIVE PORTS</h6>
            <div class="ports-grid">
                {% for label, port in ports.items() %}
                <div class="port-card">
                    <div class="port-label">{{ label }}</div>
                    <div class="port-value">{{ port }}</div>
                </div>
                {% endfor %}
            </div>
        </div>

        {% with messages = get_flashed_messages(with_categories=true) %}{% if messages %}{% for category, message in messages %}<div class="alert alert-{{ category if category != 'message' else 'info' }} text-center fw-bold mb-4 flash-message">{{ message }}</div>{% endfor %}{% endif %}{% endwith %}

        <div class="neon-card"><h5 class="text-gold mb-4"><i class="fas fa-plus-circle"></i> CREATE SSH ACCOUNT</h5>
            <form action="/gen_key" method="POST" class="row g-3">
                <div class="col-md-3"><input type="text" name="username" class="form-control-custom w-100" placeholder="Username" required></div>
                <div class="col-md-3"><input type="text" name="password" class="form-control-custom w-100" placeholder="Password" required></div>
                <div class="col-md-2"><input type="number" name="days" class="form-control-custom w-100" value="30" required><small class="text-secondary">Days</small></div>
                <div class="col-md-2"><input type="number" name="limit" class="form-control-custom w-100" value="1" required><small class="text-secondary">Limit</small></div>
                <div class="col-md-2"><button type="submit" class="btn-gold w-100">CREATE</button></div>
            </form>
        </div>

        <div class="neon-card p-0 overflow-hidden shadow-lg">
            <h5 class="text-primary p-4 mb-0"><i class="fas fa-users"></i> ACTIVE SSH USERS</h5>
            <div class="table-scroll">
                <table class="table table-hover text-center">
                    <thead>
                        <tr><th>USERNAME</th><th>PASSWORD</th><th>DEVICE</th><th>EXPIRY</th><th>STATUS</th><th>ACTIONS</th> </thead>
                    <tbody>
                        {% for key, val in keys.items() %}
                        {% set is_expired = val.expiry < today %}
                        <tr style="border-bottom: 1px solid #333;">
                            <td class="username-cell"><i class="fas fa-user-circle me-2"></i>{{ val.username }}</td>
                            <td><span class="password-cell" id="pass-{{ loop.index }}">••••••••</span> <i class="fas fa-eye-slash ms-2 text-secondary" id="icon-{{ loop.index }}" style="cursor:pointer" onclick="togglePass('{{ loop.index }}', '{{ val.password }}')"></i></td>
                            <td class="device-cell"><span class="{% if val.online_count > val.limit %}device-limit{% elif val.online_count > 0 %}device-online{% else %}device-offline{% endif %}">{{ val.online_count }} / {{ val.limit }}</span></td>
                            <td class="expiry-cell">{{ val.expiry }}</td>
                            <td>{% if is_expired %}<span class="status-expired">Expired</span>{% elif val.status == 'Online' %}<span class="status-online">Online</span>{% else %}<span class="status-offline">Offline</span>{% endif %}</td>
                            <td><div class="btn-group btn-group-sm"><button class="btn btn-outline-warning" data-bs-toggle="modal" data-bs-target="#editModal{{ loop.index }}"><i class="fas fa-edit"></i> EDIT</button><a href="/delete/{{ key }}" class="btn btn-outline-danger" onclick="return confirm('Delete user {{ val.username }}?')"><i class="fas fa-trash"></i> DEL</a></div></td>
                        </tr>
                        <div class="modal fade" id="editModal{{ loop.index }}" tabindex="-1"><div class="modal-dialog modal-dialog-centered"><div class="modal-content bg-black border border-secondary text-white"><div class="modal-header border-secondary"><h5 class="text-gold">Edit User: {{ val.username }}</h5><button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button></div><form action="/edit_key/{{ key }}" method="POST"><div class="modal-body"><div class="mb-3"><label class="small text-warning">PASSWORD</label><input type="text" name="password" class="form-control-custom w-100" value="{{ val.password }}" required></div><div class="mb-3"><label class="small text-warning">LIMIT</label><input type="number" name="limit" class="form-control-custom w-100" value="{{ val.limit }}" required></div><div class="mb-3"><label class="small text-warning">EXPIRY DATE</label><input type="date" name="expiry" class="form-control-custom w-100" value="{{ val.expiry }}" required></div></div><div class="modal-footer border-secondary"><button type="submit" class="btn-gold w-100">SAVE CHANGES</button></div></form></div></div></div>
                        {% endfor %}
                    </tbody>
                </table>
            </div>
        </div>

        <div class="footer-buttons">
            <a href="/backup_users" class="btn-outline-custom"><i class="fas fa-download"></i> Backup Users</a>
            <button class="btn-outline-custom" onclick="document.getElementById('restore-file-input').click()"><i class="fas fa-upload"></i> Restore Users</button>
            <a href="/logout" class="btn-outline-custom" style="border-color: #dc3545; color: #dc3545;"><i class="fas fa-sign-out-alt"></i> Logout</a>
            <form id="restore-form" action="/restore_users" method="POST" enctype="multipart/form-data" style="display: none;"><input type="file" id="restore-file-input" name="backup_file" accept=".json" onchange="document.getElementById('restore-form').submit()"></form>
        </div>
    </div>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
    <script>
        function updateRegionTime() {
            const regionSpan = document.getElementById('regionText');
            const regionTimeSpan = document.getElementById('regionCurrentTime');
            if (regionSpan && regionTimeSpan) {
                const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
                const now = new Date();
                const options = { year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', second: '2-digit', hour12: false };
                const formattedTime = new Intl.DateTimeFormat('en-GB', options).format(now);
                regionSpan.innerHTML = timezone;
                regionTimeSpan.innerHTML = formattedTime;
            }
        }
        updateRegionTime();
        setInterval(updateRegionTime, 1000);
        
        function toggleDnsEdit() {
            const displayMode = document.getElementById('dnsDisplayMode');
            const editMode = document.getElementById('dnsEditMode');
            const toggleBtn = document.getElementById('toggleDnsEditBtn');
            if (displayMode.style.display === 'none') {
                displayMode.style.display = 'block';
                editMode.style.display = 'none';
                toggleBtn.innerHTML = '<i class="fas fa-edit"></i> Edit';
            } else {
                displayMode.style.display = 'none';
                editMode.style.display = 'block';
                toggleBtn.innerHTML = '<i class="fas fa-times"></i> Cancel';
            }
        }
        
        document.addEventListener('DOMContentLoaded', function() {
            const flashMessages = document.querySelectorAll('.flash-message');
            if (flashMessages.length > 0) {
                setTimeout(function() {
                    flashMessages.forEach(function(msg) {
                        msg.style.opacity = '0';
                        setTimeout(function() { if (msg.parentNode) msg.remove(); }, 500);
                    });
                }, 2000);
            }
        });
        
        function togglePass(id, p) {
            let span = document.getElementById('pass-' + id);
            let icon = document.getElementById('icon-' + id);
            if(span.innerText === '••••••••') {
                span.innerText = p;
                icon.classList.remove('fa-eye-slash');
                icon.classList.add('fa-eye');
            } else {
                span.innerText = '••••••••';
                icon.classList.remove('fa-eye');
                icon.classList.add('fa-eye-slash');
            }
        }
        
        function copyToClipboard(elementId) {
            const element = document.getElementById(elementId);
            const text = element.innerText;
            if (navigator.clipboard && navigator.clipboard.writeText) {
                navigator.clipboard.writeText(text).then(() => {
                    const icon = event.target;
                    const originalClass = icon.className;
                    icon.className = 'fas fa-check copy-icon';
                    icon.style.color = '#28a745';
                    setTimeout(() => { icon.className = originalClass; icon.style.color = ''; }, 1500);
                }).catch(err => { fallbackCopy(text); });
            } else { fallbackCopy(text); }
        }
        
        function fallbackCopy(text) {
            const textarea = document.createElement('textarea');
            textarea.value = text;
            document.body.appendChild(textarea);
            textarea.select();
            try {
                document.execCommand('copy');
                const icon = event.target;
                const originalClass = icon.className;
                icon.className = 'fas fa-check copy-icon';
                icon.style.color = '#28a745';
                setTimeout(() => { icon.className = originalClass; icon.style.color = ''; }, 1500);
            } catch (err) {}
            document.body.removeChild(textarea);
        }
    </script>
</body>
</html>
"""

# ============================================
# FLASK ROUTES
# ============================================

@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    return redirect(url_for('admin_login'))

@app.route('/login', methods=['GET', 'POST'])
def admin_login():
    if current_user.is_authenticated:
        return redirect(url_for('admin_dashboard'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = request.form.get('remember')
        if username == ADMIN_USER and password == ADMIN_PASS:
            user = Admin(username)
            login_user(user, remember=True if remember else False)
            if remember:
                session.permanent = True
            return redirect(url_for('admin_dashboard'))
        else:
            flash("Invalid Credentials!")
    return render_template_string(LOGIN_HTML)

@app.route('/dashboard')
@login_required
def admin_dashboard():
    keys = load_keys()
    online_users = 0
    today = date.today().strftime("%Y-%m-%d")
    unique_keys = {}
    seen_usernames = set()
    for key, val in keys.items():
        username = val.get('username')
        if username not in seen_usernames:
            seen_usernames.add(username)
            unique_keys[key] = val
    for key, val in unique_keys.items():
        username = val.get('username')
        if username:
            is_online, online_num = get_user_online_status(username)
            val['online_count'] = online_num
            val['status'] = "Online" if is_online else "Offline"
            if is_online:
                online_users += 1
        else:
            val['online_count'] = 0
            val['status'] = "Not Synced"
    info = {
        "uptime": subprocess.getoutput("uptime -p").replace("up ", ""),
        "ram": subprocess.getoutput("free -h | grep Mem | awk '{print $3 \"/\" $2}'"),
        "total": len(unique_keys),
        "online": online_users
    }
    return render_template_string(DASHBOARD_HTML, info=info, keys=unique_keys, config=get_evt_config(), ports=get_live_ports(), dns_key=get_slowdns_pubkey(), today=today)

@app.route('/gen_key', methods=['POST'])
@login_required
def gen_key():
    username = request.form.get('username', '').strip()
    password = request.form.get('password', '').strip()
    try:
        days = int(request.form.get('days', 30))
        limit = int(request.form.get('limit', 1))
    except:
        days, limit = 30, 1
    if not username or not password:
        flash("Username and Password are required!", "danger")
        return redirect(url_for('admin_dashboard'))
    keys = load_keys()
    if any(v.get('username') == username for v in keys.values()):
        flash(f"Error: Username '{username}' already exists!", "danger")
        return redirect(url_for('admin_dashboard'))
    expiry = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    key = "EVT-" + str(uuid.uuid4()).upper()[:8]
    keys[key] = {
        "username": username, "password": password, "expiry": expiry,
        "limit": limit, "created_by": current_user.id,
        "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    save_keys(keys)
    if sync_user_to_system(username, password, expiry, limit):
        flash(f"✅ User '{username}' created successfully! (Days: {days}, Limit: {limit})", "success")
    else:
        flash(f"⚠️ User created but sync failed!", "warning")
    return redirect(url_for('admin_dashboard'))

@app.route('/edit_key/<key>', methods=['POST'])
@login_required
def edit_key(key):
    keys = load_keys()
    if key not in keys:
        flash("Key not found!", "danger")
        return redirect(url_for('admin_dashboard'))
    password = request.form.get('password', '').strip()
    try:
        limit = int(request.form.get('limit', 1))
    except:
        limit = 1
    expiry = request.form.get('expiry', '').strip()
    if password:
        keys[key]['password'] = password
    if limit:
        keys[key]['limit'] = limit
    if expiry:
        keys[key]['expiry'] = expiry
    save_keys(keys)
    username = keys[key]['username']
    sync_user_to_system(username, keys[key]['password'], keys[key]['expiry'], keys[key]['limit'])
    flash(f"✅ User '{username}' updated successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/delete/<key>')
@login_required
def delete_key(key):
    keys = load_keys()
    if key not in keys:
        flash("Key not found!", "danger")
        return redirect(url_for('admin_dashboard'))
    username = keys[key]['username']
    subprocess.run(["userdel", "-f", username], capture_output=True)
    subprocess.run(f"sed -i '/^{username} hard/d' /etc/security/limits.conf", shell=True, capture_output=True)
    del keys[key]
    save_keys(keys)
    flash(f"✅ User '{username}' deleted successfully!", "success")
    return redirect(url_for('admin_dashboard'))

@app.route('/backup_users')
@login_required
def backup_users():
    try:
        if os.path.exists(KEY_DB):
            return send_file(KEY_DB, as_attachment=True, download_name=f"evt_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json", mimetype='application/json')
        else:
            flash("No backup file found!", "danger")
            return redirect(url_for('admin_dashboard'))
    except Exception as e:
        flash(f"Backup failed: {str(e)}", "danger")
        return redirect(url_for('admin_dashboard'))

@app.route('/restore_users', methods=['POST'])
@login_required
def restore_users():
    try:
        if 'backup_file' not in request.files:
            flash("No file selected!", "danger")
            return redirect(url_for('admin_dashboard'))
        file = request.files['backup_file']
        if file.filename == '':
            flash("No file selected!", "danger")
            return redirect(url_for('admin_dashboard'))
        if not file.filename.endswith('.json'):
            flash("Please upload a JSON file!", "danger")
            return redirect(url_for('admin_dashboard'))
        content = file.read().decode('utf-8')
        restored_data = json.loads(content)
        if 'keys' in restored_data:
            restored_keys = restored_data['keys']
        else:
            restored_keys = restored_data
        if not isinstance(restored_keys, dict):
            flash("Invalid backup format!", "danger")
            return redirect(url_for('admin_dashboard'))
        if os.path.exists(KEY_DB):
            backup_name = f"keys_backup_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            backup_path = os.path.join(BASE_DIR, backup_name)
            shutil.copy2(KEY_DB, backup_path)
        save_keys(restored_keys)
        synced, errors = sync_all_users_to_system()
        flash(f"✅ Restore successful! Restored {len(restored_keys)} users. Synced: {synced}, Errors: {errors}", "success")
    except json.JSONDecodeError as e:
        flash(f"Invalid JSON file: {str(e)}", "danger")
    except Exception as e:
        flash(f"Restore failed: {str(e)}", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/update_dns_settings', methods=['POST'])
@login_required
def update_dns_settings():
    if current_user.id != ADMIN_USER:
        flash("Only admin can update DNS settings!", "danger")
        return redirect(url_for('admin_dashboard'))
    domain = request.form.get('domain', '').strip()
    ns_domain = request.form.get('ns_domain', '').strip()
    pubkey = request.form.get('pubkey', '').strip()
    try:
        with open(CONFIG_FILE, "w") as f:
            f.write(f'DOMAIN="{domain}"\n')
            f.write(f'NS_DOMAIN="{ns_domain}"\n')
        if pubkey and pubkey != "None":
            os.makedirs("/etc/dnstt", exist_ok=True)
            with open("/etc/dnstt/server.pub", "w") as f:
                f.write(pubkey)
        flash("✅ DNS Settings updated successfully!", "success")
    except Exception as e:
        flash(f"❌ Update failed: {str(e)}", "danger")
    return redirect(url_for('admin_dashboard'))

@app.route('/logout')
def logout():
    logout_user()
    session.clear()
    return redirect(url_for('admin_login'))

@app.route('/api/online_status')
@login_required
def api_online_status():
    keys = load_keys()
    status_dict = {}
    online_total = 0
    for key, val in keys.items():
        username = val.get('username')
        if username:
            is_online, online_num = get_user_online_status(username)
            status_dict[key] = {
                'username': username,
                'status': "Online" if is_online else "Offline",
                'online_count': online_num,
                'device_status': f"{online_num} / {val.get('limit', 1)}"
            }
            if is_online:
                online_total += 1
    return jsonify({'status': status_dict, 'total_online': online_total, 'total_users': len(keys), 'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")})

# ============================================
# AUTO-START SYSTEMD SERVICE SETUP
# ============================================

def setup_systemd_service():
    try:
        service_content = f"""[Unit]
Description=EVT SSH Manager Panel
After=network.target
Wants=network.target

[Service]
Type=simple
User=root
WorkingDirectory={BASE_DIR}
ExecStart={sys.executable} {SCRIPT_INFO['path']}
Restart=always
RestartSec=5
StandardOutput=null
StandardError=null
SyslogIdentifier=evtssh
NoNewPrivileges=yes
PrivateTmp=yes

[Install]
WantedBy=multi-user.target"""
        service_file = "/etc/systemd/system/evtssh.service"
        with open(service_file, 'w') as f:
            f.write(service_content)
        subprocess.run(['systemctl', 'daemon-reload'], capture_output=True)
        subprocess.run(['systemctl', 'enable', 'evtssh'], capture_output=True)
        subprocess.run(['systemctl', 'start', 'evtssh'], capture_output=True)
        return True
    except:
        return False

def setup_cron_autostart():
    try:
        cron_line = f"@reboot sleep 30 && {sys.executable} {SCRIPT_INFO['path']} > /dev/null 2>&1 &"
        result = subprocess.run(['crontab', '-l'], capture_output=True, text=True)
        cron_content = result.stdout if result.returncode == 0 else ""
        script_name = os.path.basename(SCRIPT_INFO['path'])
        if script_name not in cron_content:
            new_cron = cron_content.strip() + '\n' + cron_line + '\n' if cron_content.strip() else cron_line + '\n'
            subprocess.run(['crontab', '-'], input=new_cron, text=True, capture_output=True)
            return True
    except:
        return False

# ============================================
# MAIN EXECUTION
# ============================================

if __name__ == '__main__':
    # Check license
    if not check_license():
        print("\n" + "="*50)
        print("[❌] VPS IP စစ်ဆေးနေသည်")
        print("[❌] မင်းရဲ့ VPS IP ဝင်ရောက်ခွင့်မပြုပါ")
        print("[❌] ဆက်သွယ်ရနhttps://t.me/evtvpn143")
        print("="*50)
        sys.exit(1)
    
    # Setup auto-start service
    print("\n[🔧] Setting up auto-start...")
    if not os.path.exists("/etc/systemd/system/evtssh.service"):
        if setup_systemd_service():
            print("[✅] Auto-start configured via systemd")
        else:
            if setup_cron_autostart():
                print("[✅] Auto-start configured via cron")
            else:
                print("[⚠️] Auto-start setup failed!")
    else:
        print("[✅] Auto-start already configured")
    
    # Sync users
    print("\n[🔄] Syncing users from keys.json to system...")
    synced, errors = sync_all_users_to_system()
    print(f"[✅] Synced: {synced} users, Errors: {errors}")
    
    # Start Telegram bot
    telegram_thread = threading.Thread(target=run_telegram_bot, daemon=True)
    telegram_thread.start()
    print("[✅] Telegram Bot started!")
    
    vps_ip = get_vps_ip()
    
    print("\n" + "="*50)
    print("[✅] EVT SSH MANAGER STARTED SUCCESSFULLY!")
    print(f"[🌐] Web Panel: http://{vps_ip}:5001")
    print(f"[🔑] Login: {ADMIN_USER} / {ADMIN_PASS}")
    print("[🤖] Telegram Bot is running...")
    print("="*50)
    print("\n[💡] IMPORTANT: Service is installed and will auto-start on VPS reboot!")
    print("[💡] Check status: systemctl status evtssh")
    print("="*50)
    
    # Start server
    try:
        from waitress import serve
        serve(app, host='0.0.0.0', port=5001, threads=4, _quiet=True)
    except ImportError:
        from werkzeug.serving import run_simple
        run_simple('0.0.0.0', 5001, app, use_reloader=False, threaded=True)
