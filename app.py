# app.py
import os
import json
import hashlib
import secrets
from datetime import datetime
from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from cryptography.fernet import Fernet
from functools import wraps

app = Flask(__name__)
app.secret_key = secrets.token_hex(32)

# 文件存储路径
DATA_DIR = 'chat_data'
USERS_FILE = os.path.join(DATA_DIR, 'users.json')
MESSAGES_FILE = os.path.join(DATA_DIR, 'messages.json')
KEYS_FILE = os.path.join(DATA_DIR, 'keys.json')

# 确保数据目录存在
os.makedirs(DATA_DIR, exist_ok=True)

# 初始化存储文件
def init_storage():
    if not os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'w') as f:
            json.dump({}, f)
    
    if not os.path.exists(MESSAGES_FILE):
        with open(MESSAGES_FILE, 'w') as f:
            json.dump([], f)
    
    if not os.path.exists(KEYS_FILE):
        with open(KEYS_FILE, 'w') as f:
            json.dump({}, f)

init_storage()

# 工具函数
def hash_password(password):
    """使用SHA-256哈希密码"""
    salt = secrets.token_hex(16)
    hash_obj = hashlib.sha256((password + salt).encode())
    return f"{salt}${hash_obj.hexdigest()}"

def verify_password(password, hashed):
    """验证密码"""
    salt, hash_value = hashed.split('$')
    hash_obj = hashlib.sha256((password + salt).encode())
    return hash_obj.hexdigest() == hash_value

def generate_keypair():
    """生成加密密钥对"""
    return Fernet.generate_key()

def encrypt_message(message, key):
    """加密消息"""
    f = Fernet(key)
    return f.encrypt(message.encode()).decode()

def decrypt_message(encrypted_message, key):
    """解密消息"""
    f = Fernet(key)
    return f.decrypt(encrypted_message.encode()).decode()

# 登录装饰器
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# 路由
@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('chat'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        
        if username in users and verify_password(password, users[username]['password']):
            session['username'] = username
            return redirect(url_for('chat'))
        
        return render_template('login.html', error='用户名或密码错误')
    
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        with open(USERS_FILE, 'r') as f:
            users = json.load(f)
        
        if username in users:
            return render_template('register.html', error='用户名已存在')
        
        # 存储用户密码哈希
        users[username] = {
            'password': hash_password(password),
            'created_at': datetime.now().isoformat()
        }
        
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=2)
        
        # 为用户生成加密密钥
        with open(KEYS_FILE, 'r') as f:
            keys = json.load(f)
        
        keys[username] = generate_keypair().decode()
        
        with open(KEYS_FILE, 'w') as f:
            json.dump(keys, f, indent=2)
        
        session['username'] = username
        return redirect(url_for('chat'))
    
    return render_template('register.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/chat')
@login_required
def chat():
    return render_template('chat.html', username=session['username'])

@app.route('/api/messages', methods=['GET'])
@login_required
def get_messages():
    with open(MESSAGES_FILE, 'r') as f:
        messages = json.load(f)
    
    # 解密消息
    with open(KEYS_FILE, 'r') as f:
        keys = json.load(f)
    
    current_user = session['username']
    decrypted_messages = []
    
    for msg in messages:
        # 尝试用当前用户的密钥解密
        try:
            sender_key = keys[msg['sender']].encode()
            decrypted_content = decrypt_message(msg['encrypted_content'], sender_key)
            decrypted_messages.append({
                'sender': msg['sender'],
                'content': decrypted_content,
                'timestamp': msg['timestamp'],
                'is_own': msg['sender'] == current_user
            })
        except:
            # 如果解密失败，跳过这条消息
            continue
    
    return jsonify(decrypted_messages)

@app.route('/api/send', methods=['POST'])
@login_required
def send_message():
    data = request.json
    content = data.get('content')
    recipient = data.get('recipient', 'all')
    
    if not content:
        return jsonify({'error': '消息内容不能为空'}), 400
    
    # 获取加密密钥
    with open(KEYS_FILE, 'r') as f:
        keys = json.load(f)
    
    sender = session['username']
    sender_key = keys[sender].encode()
    
    # 加密消息
    encrypted_content = encrypt_message(content, sender_key)
    
    # 存储消息
    with open(MESSAGES_FILE, 'r') as f:
        messages = json.load(f)
    
    messages.append({
        'sender': sender,
        'recipient': recipient,
        'encrypted_content': encrypted_content,
        'timestamp': datetime.now().isoformat()
    })
    
    # 限制存储的消息数量（最近1000条）
    if len(messages) > 1000:
        messages = messages[-1000:]
    
    with open(MESSAGES_FILE, 'w') as f:
        json.dump(messages, f, indent=2)
    
    return jsonify({'status': 'success'})

@app.route('/api/users')
@login_required
def get_users():
    with open(USERS_FILE, 'r') as f:
        users = json.load(f)
    
    current_user = session['username']
    user_list = [{'username': u} for u in users.keys() if u != current_user]
    
    return jsonify(user_list)

if __name__ == '__main__':
    app.run(debug=True)