import os
import json
import time
import threading
import logging
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from flask_cors import CORS
import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global variables for automation control
automation_running = False
automation_thread = None
console_messages = []
current_status = "Stopped"

# Facebook Graph API endpoints
FB_API_BASE = "https://graph.facebook.com/v18.0"


class FacebookMessengerBot:
    def __init__(self, cookies_string=None):
        self.session = requests.Session()
        self.cookies = {}
        if cookies_string:
            self._parse_cookies(cookies_string)
        self.session.cookies.update(self.cookies)
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })

    def _parse_cookies(self, cookies_string):
        # Try JSON first
        try:
            self.cookies = json.loads(cookies_string)
            return
        except:
            pass
        # Try line-separated key=value
        for line in cookies_string.splitlines():
            line = line.strip()
            if '=' in line:
                key, value = line.split('=', 1)
                self.cookies[key.strip()] = value.strip()
        # Fallback: semicolon separated
        if not self.cookies and ';' in cookies_string:
            for item in cookies_string.split(';'):
                if '=' in item:
                    key, value = item.strip().split('=', 1)
                    self.cookies[key] = value

    def verify_cookies(self):
        try:
            response = self.session.get(
                f"{FB_API_BASE}/me",
                params={'access_token': self.cookies.get('access_token', ''), 'fields': 'id,name'}
            )
            return response.status_code == 200
        except:
            return False

    def send_message(self, conversation_id, message):
        try:
            if 'access_token' in self.cookies:
                url = f"{FB_API_BASE}/{conversation_id}/messages"
                params = {'access_token': self.cookies['access_token'], 'message': message}
                response = self.session.post(url, params=params)
                return response.status_code == 200
            else:
                url = "https://www.facebook.com/messages/send/"
                data = {
                    'message': message,
                    'thread_id': conversation_id,
                    'is_group': 'true' if conversation_id.startswith('g') else 'false'
                }
                response = self.session.post(url, data=data)
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            return False


bot = None


# ======================== ROUTES ========================

@app.route('/')
def index():
    # Embedded HTML template (single file)
    return render_template_string(HTML_TEMPLATE)


@app.route('/status')
def get_status():
    return jsonify({
        'status': current_status,
        'running': automation_running,
        'console': console_messages[-50:]
    })


@app.route('/start', methods=['POST'])
def start_automation():
    global automation_running, automation_thread, bot, current_status, console_messages
    try:
        data = request.json

        # Get cookies (from file content or paste)
        cookies_file_content = data.get('cookies_file_content', '')
        cookies_paste = data.get('cookies_paste', '')
        cookies_string = cookies_file_content if cookies_file_content else cookies_paste

        if not cookies_string:
            return jsonify({'error': 'No cookies provided'}), 400

        global bot
        bot = FacebookMessengerBot(cookies_string=cookies_string)

        if not bot.verify_cookies():
            return jsonify({'error': 'Invalid cookies'}), 400

        # Load messages
        message_file_content = data.get('message_file_content', '')
        messages = []
        if message_file_content:
            messages = [line.strip() for line in message_file_content.splitlines() if line.strip()]
        elif data.get('message_text'):
            messages = [data.get('message_text')]
        else:
            messages = ['Hello from Facebook Bot!']

        # Parameters
        conversation_id = data.get('thread_id', '').strip()
        first_name = data.get('first_name', '').strip()
        last_name = data.get('last_name', '').strip()
        hater_prefix = data.get('hater_prefix', '').strip()
        time_interval = float(data.get('time_interval', 60))

        if not conversation_id:
            return jsonify({'error': 'Thread / Conversation ID required'}), 400

        # Start automation
        automation_running = True
        current_status = "Running"
        console_messages.append(f"[{datetime.now()}] Automation started")

        def automation_loop():
            message_index = 0
            while automation_running:
                try:
                    if messages:
                        message = messages[message_index % len(messages)]
                        # Build final message
                        prefix = f"{hater_prefix} " if hater_prefix else ""
                        name_part = f"{first_name} {last_name}".strip()
                        if name_part:
                            personalized = f"{prefix}{name_part}: {message}"
                        else:
                            personalized = f"{prefix}{message}"
                        # Send
                        success = bot.send_message(conversation_id, personalized)
                        if success:
                            console_messages.append(f"[{datetime.now()}] ✓ Sent: {personalized[:50]}...")
                        else:
                            console_messages.append(f"[{datetime.now()}] ✗ Failed: {personalized[:50]}...")
                        message_index += 1
                    else:
                        console_messages.append(f"[{datetime.now()}] No messages to send")
                    time.sleep(time_interval)
                except Exception as e:
                    console_messages.append(f"[{datetime.now()}] ✗ Error: {str(e)}")
                    time.sleep(10)
            console_messages.append(f"[{datetime.now()}] Automation stopped")

        automation_thread = threading.Thread(target=automation_loop)
        automation_thread.daemon = True
        automation_thread.start()

        return jsonify({'message': 'Automation started successfully'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/stop', methods=['POST'])
def stop_automation():
    global automation_running, current_status
    automation_running = False
    current_status = "Stopped"
    console_messages.append(f"[{datetime.now()}] ⛔ Stop button pressed")
    return jsonify({'message': 'Automation stopped'})


@app.route('/console')
def get_console():
    return jsonify(console_messages[-50:])


# ======================== EMBEDDED HTML ========================

HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>FB Messenger Bot · Offline Server</title>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/css/bootstrap.min.css" />
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" />
    <style>
        * { margin:0; padding:0; box-sizing:border-box; }
        body {
            background: linear-gradient(145deg, #0b0e1a 0%, #1a1f36 100%);
            min-height: 100vh;
            font-family: 'Segoe UI', system-ui, sans-serif;
            padding: 20px;
            color: #e8edf5;
        }
        .glass-card {
            background: rgba(255,255,255,0.04);
            backdrop-filter: blur(2px);
            border: 1px solid rgba(255,255,255,0.07);
            border-radius: 28px;
            padding: 28px 30px;
            box-shadow: 0 25px 50px -12px rgba(0,0,0,0.6);
            max-width: 1100px;
            margin:0 auto;
        }
        .card-header-custom {
            background: linear-gradient(135deg, #2563eb, #7c3aed);
            border-radius: 28px 28px 0 0 !important;
            padding: 22px 30px;
            margin: -28px -30px 20px -30px;
            border-bottom: 1px solid rgba(255,255,255,0.08);
        }
        .card-header-custom h3 { font-weight:700; margin:0; }
        .card-header-custom p { opacity:0.8; margin:4px 0 0; font-size:0.95rem; }
        .form-label {
            font-weight:500; font-size:0.85rem; text-transform:uppercase;
            letter-spacing:0.5px; color:#a0b4d0; margin-bottom:4px;
        }
        .form-control, .form-select {
            background: rgba(255,255,255,0.06);
            border: 1px solid rgba(255,255,255,0.10);
            border-radius: 14px;
            color: #f0f4ff;
            padding: 12px 16px;
            transition: 0.2s;
        }
        .form-control:focus {
            background: rgba(255,255,255,0.10);
            border-color: #6366f1;
            box-shadow: 0 0 0 3px rgba(99,102,241,0.25);
            color:#fff;
        }
        .form-control-file {
            background: rgba(255,255,255,0.04);
            border: 1px dashed rgba(255,255,255,0.15);
            border-radius: 14px;
            padding: 10px 14px;
            color: #b0c4e0;
            width:100%;
        }
        .form-control-file::-webkit-file-upload-button {
            background: rgba(99,102,241,0.25);
            border:none; border-radius:10px; padding:6px 18px;
            color:#c8d8ff; font-weight:500; cursor:pointer;
        }
        .btn-glow {
            background: linear-gradient(135deg, #2563eb, #7c3aed);
            border:none; border-radius:14px; padding:12px 40px;
            font-weight:600; font-size:1.05rem; color:#fff;
            box-shadow: 0 4px 15px rgba(37,99,235,0.30);
            transition:0.25s;
        }
        .btn-glow:hover { transform:translateY(-2px); box-shadow:0 8px 30px rgba(37,99,235,0.45); }
        .btn-glow:disabled { opacity:0.5; transform:none; box-shadow:none; }
        .btn-danger-glow {
            background: linear-gradient(135deg, #dc2626, #db2777);
            border:none; border-radius:14px; padding:12px 40px;
            font-weight:600; font-size:1.05rem; color:#fff;
            box-shadow: 0 4px 15px rgba(220,38,38,0.25);
        }
        .btn-danger-glow:hover { transform:translateY(-2px); box-shadow:0 8px 30px rgba(220,38,38,0.40); }
        .btn-outline-light-custom {
            background: rgba(255,255,255,0.06);
            border:1px solid rgba(255,255,255,0.12);
            border-radius:14px; color:#d0dce8; padding:10px 28px;
        }
        .btn-outline-light-custom:hover { background:rgba(255,255,255,0.13); color:#fff; }
        .status-badge {
            padding:6px 18px; border-radius:40px; font-weight:600; font-size:0.8rem;
            letter-spacing:0.3px; text-transform:uppercase;
        }
        .status-running {
            background: rgba(34,197,94,0.20); color:#4ade80;
            border:1px solid rgba(34,197,94,0.25);
        }
        .status-stopped {
            background: rgba(248,113,113,0.15); color:#f87171;
            border:1px solid rgba(248,113,113,0.20);
        }
        .console-box {
            background: #080b15;
            border:1px solid rgba(255,255,255,0.06);
            border-radius:16px; padding:18px 20px; height:320px;
            overflow-y:auto; font-family: monospace; font-size:0.85rem;
            line-height:1.7; color:#a0c4e8;
        }
        .console-box::-webkit-scrollbar { width:5px; }
        .console-box::-webkit-scrollbar-track { background:#080b15; }
        .console-box::-webkit-scrollbar-thumb { background:#4f46e5; border-radius:6px; }
        .console-line { padding:2px 0; border-bottom:1px solid rgba(255,255,255,0.02); }
        .console-line .time { color:#6b8bad; margin-right:12px; }
        .console-line .ok { color:#4ade80; }
        .console-line .err { color:#f87171; }
        .console-line .info { color:#60a5fa; }
        .console-line .warn { color:#fbbf24; }
        footer {
            margin-top:40px; text-align:center; color:rgba(255,255,255,0.35);
            border-top:1px solid rgba(255,255,255,0.04); padding-top:25px;
        }
        footer strong { color:rgba(255,255,255,0.55); }
        .preview-filename {
            color:#94a3b8; font-size:0.8rem; padding:4px 12px;
            background:rgba(255,255,255,0.04); border-radius:40px;
            border:1px solid rgba(255,255,255,0.06); display:inline-block; margin-top:4px;
        }
        .controls-wrapper {
            display:flex; flex-wrap:wrap; gap:14px; align-items:center;
            margin:24px 0 18px; padding:18px 22px;
            background:rgba(255,255,255,0.03); border-radius:20px;
            border:1px solid rgba(255,255,255,0.05);
        }
        @media (max-width:768px) {
            .glass-card { padding:18px 16px; }
            .card-header-custom { padding:16px 18px; margin:-18px -16px 16px -16px; }
            .console-box { height:220px; font-size:0.75rem; padding:12px 14px; }
            .btn-glow, .btn-danger-glow { padding:10px 24px; font-size:0.9rem; min-width:100px; }
        }
    </style>
</head>
<body>
    <div class="container" style="max-width:1100px;">
        <div class="glass-card">
            <div class="card-header-custom">
                <div class="d-flex flex-wrap align-items-center justify-content-between">
                    <div>
                        <h3><i class="fas fa-robot me-2" style="color:#a78bfa;"></i>FB Messenger Bot</h3>
                        <p>Offline Server · Advanced Automation · by Virat Rajput</p>
                    </div>
                    <div class="d-flex align-items-center gap-3 mt-2 mt-sm-0">
                        <span id="statusBadge" class="status-badge status-stopped">
                            <i class="fas fa-circle me-1" style="font-size:0.5rem;"></i> Stopped
                        </span>
                    </div>
                </div>
            </div>

            <form id="automationForm">
                <div class="row g-3 mb-3">
                    <div class="col-md-6">
                        <label class="form-label"><i class="fas fa-cookie me-1"></i> Cookies File</label>
                        <input class="form-control-file" type="file" id="cookiesFileInput" accept=".json,.txt" />
                        <small class="text-muted" style="font-size:0.7rem;">Upload JSON or text (key=value per line)</small>
                    </div>
                    <div class="col-md-6">
                        <label class="form-label"><i class="fas fa-list me-1"></i> Cookies as per line</label>
                        <textarea class="form-control" id="cookiesPaste" rows="3" placeholder="c_user=xxx&#10;xs=yyy&#10;..."></textarea>
                        <small class="text-muted" style="font-size:0.7rem;">One cookie per line (key=value)</small>
                    </div>
                </div>
                <div class="row g-3 mb-3">
                    <div class="col-md-4">
                        <label class="form-label"><i class="fas fa-users me-1"></i> Group / Thread Name</label>
                        <input class="form-control" type="text" id="groupName" placeholder="My Group" />
                    </div>
                    <div class="col-md-4">
                        <label class="form-label"><i class="fas fa-hashtag me-1"></i> Thread / Conversation ID</label>
                        <input class="form-control" type="text" id="threadId" placeholder="t_123456789 or 123456789" required />
                        <small class="text-muted" style="font-size:0.7rem;">Format: t_xxxxxxxxxx or numbers</small>
                    </div>
                    <div class="col-md-4">
                        <label class="form-label"><i class="fas fa-tag me-1"></i> Hater Name / Prefix</label>
                        <input class="form-control" type="text" id="haterPrefix" placeholder="e.g. Hater:" />
                    </div>
                </div>
                <div class="row g-3 mb-3">
                    <div class="col-md-4">
                        <label class="form-label"><i class="fas fa-user me-1"></i> First Name</label>
                        <input class="form-control" type="text" id="firstName" placeholder="John" />
                    </div>
                    <div class="col-md-4">
                        <label class="form-label"><i class="fas fa-user me-1"></i> Last Name</label>
                        <input class="form-control" type="text" id="lastName" placeholder="Doe" />
                    </div>
                    <div class="col-md-4">
                        <label class="form-label"><i class="fas fa-clock me-1"></i> Time Interval (seconds)</label>
                        <input class="form-control" type="number" id="timeInterval" value="60" min="1" />
                    </div>
                </div>
                <div class="row g-3 mb-3">
                    <div class="col-md-12">
                        <label class="form-label"><i class="fas fa-file-alt me-1"></i> Message File (.txt)</label>
                        <input class="form-control-file" type="file" id="messageFileInput" accept=".txt" />
                        <small class="text-muted" style="font-size:0.7rem;">One message per line</small>
                    </div>
                </div>
                <input type="hidden" id="cookiesFileContent" />
                <input type="hidden" id="messageFileContent" />
            </form>

            <div class="controls-wrapper">
                <button id="startBtn" class="btn btn-glow" onclick="startAutomation()">
                    <i class="fas fa-play me-2"></i>Start Automation
                </button>
                <button id="stopBtn" class="btn btn-danger-glow" onclick="stopAutomation()">
                    <i class="fas fa-stop me-2"></i>Stop 🛑
                </button>
                <button class="btn btn-outline-light-custom" onclick="clearConsole()">
                    <i class="fas fa-eraser me-1"></i> Clear Console
                </button>
                <span class="ms-auto text-muted" style="font-size:0.85rem;">
                    <i class="fas fa-server me-1"></i> v2.0 · Non‑Stop
                </span>
            </div>

            <div class="mt-2">
                <div class="d-flex justify-content-between align-items-center mb-2">
                    <h5 style="font-weight:600; margin:0; color:#d0dce8;">
                        <i class="fas fa-terminal me-2" style="color:#60a5fa;"></i>Live Console
                    </h5>
                    <span id="consoleCount" class="text-muted" style="font-size:0.8rem;">0 lines</span>
                </div>
                <div class="console-box" id="console">
                    <div class="console-line"><span class="time">[ system ]</span> <span class="info">⚡ Ready. Fill in your credentials and start automation.</span></div>
                    <div class="console-line"><span class="time">[ system ]</span> <span class="info">📌 Developed by Virat Rajput · 2026</span></div>
                </div>
            </div>
        </div>
        <footer>
            <p>Developed by <strong>Virat Rajput</strong> &nbsp;·&nbsp; All Rights Reserved 2026</p>
        </footer>
    </div>

    <script src="https://code.jquery.com/jquery-3.7.0.min.js"></script>
    <script src="https://cdnjs.cloudflare.com/ajax/libs/bootstrap/5.3.0/js/bootstrap.bundle.min.js"></script>
    <script>
        let isRunning = false;
        let consoleInterval = null;

        function readFileAsText(file) {
            return new Promise((resolve, reject) => {
                if (!file) { resolve(''); return; }
                const reader = new FileReader();
                reader.onload = e => resolve(e.target.result);
                reader.onerror = reject;
                reader.readAsText(file);
            });
        }

        async function startAutomation() {
            if (isRunning) { appendConsole('warn', 'Automation already running!'); return; }
            const cookiesFileEl = document.getElementById('cookiesFileInput');
            const messageFileEl = document.getElementById('messageFileInput');
            const cookiesFileContent = cookiesFileEl.files.length ? await readFileAsText(cookiesFileEl.files[0]) : '';
            const messageFileContent = messageFileEl.files.length ? await readFileAsText(messageFileEl.files[0]) : '';
            const payload = {
                cookies_file_content: cookiesFileContent,
                cookies_paste: document.getElementById('cookiesPaste').value,
                group_name: document.getElementById('groupName').value,
                thread_id: document.getElementById('threadId').value,
                hater_prefix: document.getElementById('haterPrefix').value,
                first_name: document.getElementById('firstName').value,
                last_name: document.getElementById('lastName').value,
                time_interval: parseInt(document.getElementById('timeInterval').value) || 60,
                message_file_content: messageFileContent,
            };
            if (!payload.cookies_file_content && !payload.cookies_paste) {
                appendConsole('err', '❌ Please provide cookies.');
                return;
            }
            if (!payload.thread_id) {
                appendConsole('err', '❌ Thread ID required.');
                return;
            }
            document.getElementById('startBtn').disabled = true;
            appendConsole('info', '🚀 Starting...');
            try {
                const resp = await fetch('/start', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await resp.json();
                if (!resp.ok) throw new Error(data.error || 'Unknown error');
                isRunning = true;
                setStatus('running');
                appendConsole('ok', '✅ ' + data.message);
                startConsoleUpdates();
            } catch (err) {
                appendConsole('err', '❌ ' + err.message);
                document.getElementById('startBtn').disabled = false;
            }
        }

        async function stopAutomation() {
            if (!isRunning) { appendConsole('warn', 'Not running.'); return; }
            appendConsole('info', '⏳ Stopping...');
            try {
                const resp = await fetch('/stop', { method: 'POST' });
                const data = await resp.json();
                if (!resp.ok) throw new Error(data.error);
                isRunning = false;
                setStatus('stopped');
                document.getElementById('startBtn').disabled = false;
                if (consoleInterval) { clearInterval(consoleInterval); consoleInterval = null; }
                appendConsole('ok', '⛔ ' + data.message);
            } catch (err) { appendConsole('err', '❌ ' + err.message); }
        }

        function appendConsole(type, text) {
            const box = document.getElementById('console');
            const time = new Date().toLocaleTimeString();
            const div = document.createElement('div');
            div.className = 'console-line';
            div.innerHTML = `<span class="time">[ ${time} ]</span> <span class="${type}">${text}</span>`;
            box.appendChild(div);
            box.scrollTop = box.scrollHeight;
            document.getElementById('consoleCount').textContent = box.children.length + ' lines';
        }

        function clearConsole() {
            const box = document.getElementById('console');
            box.innerHTML = '';
            document.getElementById('consoleCount').textContent = '0 lines';
            appendConsole('info', '🧹 Console cleared.');
        }

        function setStatus(state) {
            const badge = document.getElementById('statusBadge');
            if (state === 'running') {
                badge.className = 'status-badge status-running';
                badge.innerHTML = '<i class="fas fa-circle me-1" style="font-size:0.5rem;"></i> Running';
            } else {
                badge.className = 'status-badge status-stopped';
                badge.innerHTML = '<i class="fas fa-circle me-1" style="font-size:0.5rem;"></i> Stopped';
            }
        }

        function startConsoleUpdates() {
            if (consoleInterval) clearInterval(consoleInterval);
            consoleInterval = setInterval(async () => {
                try {
                    const resp = await fetch('/console');
                    const lines = await resp.json();
                    const box = document.getElementById('console');
                    const existing = new Set();
                    box.querySelectorAll('.console-line').forEach(el => existing.add(el.textContent.trim()));
                    for (const line of lines) {
                        if (!existing.has(line.trim())) {
                            const div = document.createElement('div');
                            div.className = 'console-line';
                            div.textContent = line;
                            box.appendChild(div);
                            existing.add(line.trim());
                        }
                    }
                    box.scrollTop = box.scrollHeight;
                    document.getElementById('consoleCount').textContent = box.children.length + ' lines';
                } catch (_) {}
            }, 1500);
        }

        async function checkInitialStatus() {
            try {
                const resp = await fetch('/status');
                const data = await resp.json();
                if (data.running) {
                    isRunning = true;
                    setStatus('running');
                    document.getElementById('startBtn').disabled = true;
                    const cResp = await fetch('/console');
                    const cLines = await cResp.json();
                    const box = document.getElementById('console');
                    box.innerHTML = '';
                    cLines.forEach(line => {
                        const div = document.createElement('div');
                        div.className = 'console-line';
                        div.textContent = line;
                        box.appendChild(div);
                    });
                    document.getElementById('consoleCount').textContent = box.children.length + ' lines';
                    startConsoleUpdates();
                }
            } catch (_) {}
        }

        document.addEventListener('DOMContentLoaded', checkInitialStatus);
    </script>
</body>
</html>
"""


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
