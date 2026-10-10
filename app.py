from flask import Flask, render_template, request, jsonify, session
import time
import os
import threading
from pyrogram import Client

app = Flask(__name__)
app.secret_key = "gizli_telegram_saas_anahtari"

# --- LİSANS VERİTABANI ---
KEYS_DB = {
    "ADMIN-SINIRSIZ-KEY": {
        "duration": 0, 
        "expires_at": 0, 
        "used_by": "8916532114", 
        "used_by_name": "Admin (Siz)", 
        "status": "active"
    }
}
ADMIN_ID = "8916532114"
active_clients = {}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login/send_code', methods=['POST'])
def send_code():
    data = request.json
    phone = data.get('phone')
    API_ID = 611335
    API_HASH = "d524b414d21f4d37f08684c1df41ac9d"
    
    session_name = f"session_{phone.replace('+', '')}"
    session['session_name'] = session_name
    session['phone'] = phone

    try:
        client = Client(session_name, api_id=API_ID, api_hash=API_HASH, in_memory=True)
        client.connect()
        sent_code = client.send_code(phone)
        session['phone_code_hash'] = sent_code.phone_code_hash
        active_clients[session_name] = client
        return jsonify({"success": True, "message": "Telegram doğrulama kodu gönderildi!"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Hata: {str(e)}"})

@app.route('/api/login/verify_code', methods=['POST'])
def verify_code():
    data = request.json
    code = data.get('code')
    session_name = session.get('session_name')
    phone = session.get('phone')
    phone_code_hash = session.get('phone_code_hash')

    client = active_clients.get(session_name)
    if not client:
        return jsonify({"success": False, "message": "Oturum bulunamadı, tekrar deneyin."})

    try:
        client.sign_in(phone, phone_code_hash, code)
        me = client.get_me()
        session['user_id'] = str(me.id)
        session['user_name'] = f"{me.first_name or ''} (@{me.username or 'yok'})"
        return jsonify({"success": True, "user_id": str(me.id), "user_name": session['user_name']})
    except Exception as e:
        if "SESSION_PASSWORD_NEEDED" in str(e) or "Password" in str(e):
            session['need_password'] = True
            return jsonify({"success": False, "need_password": True, "message": "Bulut şifresi gerekiyor."})
        return jsonify({"success": False, "message": f"Kod hatalı: {str(e)}"})

@app.route('/api/login/verify_password', methods=['POST'])
def verify_password():
    data = request.json
    password = data.get('password')
    session_name = session.get('session_name')
    client = active_clients.get(session_name)

    try:
        client.check_password(password)
        me = client.get_me()
        session['user_id'] = str(me.id)
        session['user_name'] = f"{me.first_name or ''} (@{me.username or 'yok'})"
        return jsonify({"success": True, "user_name": session['user_name']})
    except Exception as e:
        return jsonify({"success": False, "message": f"Şifre yanlış: {str(e)}"})

@app.route('/api/check_license', methods=['POST'])
def check_license():
    data = request.json
    key = data.get('key').strip()
    user_id = session.get('user_id', 'Bilinmeyen')
    user_name = session.get('user_name', 'Kullanıcı')

    if key not in KEYS_DB:
        return jsonify({"success": False, "message": "Geçersiz Key!"})

    key_data = KEYS_DB[key]
    if key_data['used_by'] and key_data['used_by'] != user_id:
        return jsonify({"success": False, "message": "Bu key başka bir hesaba ait!"})

    current_time = time.time()
    if key_data['duration'] > 0 and current_time > key_data['expires_at']:
        key_data['status'] = 'expired'
        return jsonify({"success": False, "message": "Bu key'in süresi dolmuş!"})

    if not key_data['used_by']:
        key_data['used_by'] = user_id
        key_data['used_by_name'] = user_name
        if key_data['duration'] > 0:
            key_data['expires_at'] = current_time + key_data['duration']

    remaining = 0 if key_data['duration'] == 0 else int(key_data['expires_at'] - current_time)
    return jsonify({"success": True, "unlimited": key_data['duration'] == 0, "remaining_seconds": remaining, "used_by": key_data['used_by_name']})

@app.route('/api/admin/create_key', methods=['POST'])
def admin_create_key():
    data = request.json
    if data.get('admin_id') != ADMIN_ID:
        return jsonify({"success": False, "message": "Yetkisiz Admin ID!"})

    duration_minutes = int(data.get('duration_minutes', 60))
    import uuid
    new_key = "KEY-" + str(uuid.uuid4()).upper()[:8]
    
    duration_sec = 0 if duration_minutes <= 0 else duration_minutes * 60
    expires_at = 0 if duration_sec == 0 else time.time() + duration_sec

    KEYS_DB[new_key] = {"duration": duration_sec, "expires_at": expires_at, "used_by": None, "used_by_name": None, "status": "unused"}
    return jsonify({"success": True, "key": new_key})

@app.route('/api/admin/list_keys', methods=['POST'])
def admin_list_keys():
    data = request.json
    if data.get('admin_id') != ADMIN_ID:
        return jsonify({"success": False, "message": "Yetkisiz!"})
    return jsonify({"success": True, "keys": KEYS_DB})

@app.route('/api/start_flood', methods=['POST'])
def start_flood():
    data = request.json
    chat = data.get('chat')
    message = data.get('message')
    interval = int(data.get('interval', 2))
    count = int(data.get('count', 5))
    session_name = session.get('session_name')
    client = active_clients.get(session_name)

    if not client:
        return jsonify({"success": False, "message": "Aktif oturum yok!"})

    def run_real_flood():
        try:
            for i in range(count):
                client.send_message(chat, message)
                time.sleep(interval)
        except Exception as e:
            print(f"Hata: {e}")

    threading.Thread(target=run_real_flood).start()
    return jsonify({"success": True, "message": f"{count} adet mesaj otomasyonu başlatıldı!"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
