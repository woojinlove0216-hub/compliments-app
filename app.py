import os
import json
import time
from datetime import datetime
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

DATA_FILE = "compliments.json"
ADMIN_KEY = "1234!"

def load_data():
    if not os.path.exists(DATA_FILE):
        return []
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []

def save_data(data):
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

HTML_CODE = """
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>비밀 익명 칭찬 우체통</title>
  <script src="https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"></script>
  <style>
    body { font-family: sans-serif; background: #f8fafc; color: #1e293b; padding: 16px; margin: 0; display: flex; justify-content: center; }
    .container { width: 100%; max-width: 500px; }
    h1 { text-align: center; font-size: 1.4rem; margin-bottom: 20px; }
    .card { background: white; padding: 16px; border-radius: 10px; border: 1px solid #cbd5e1; margin-bottom: 14px; box-shadow: 0 2px 4px rgba(0,0,0,0.02); }
    input, textarea, button { width: 100%; padding: 10px; margin-top: 6px; border: 1px solid #cbd5e1; border-radius: 6px; box-sizing: border-box; font-size: 0.95rem; }
    button { background: #4f46e5; color: white; border: none; font-weight: bold; cursor: pointer; margin-top: 10px; }
    .btn-sub { background: #64748b; }
    .btn-del { background: #ef4444; width: auto; padding: 4px 8px; font-size: 0.8rem; margin: 0; }
    .row { display: flex; gap: 8px; }
    .post { background: #f1f5f9; padding: 12px; border-radius: 8px; margin-bottom: 10px; }
    .header { font-size: 0.85rem; color: #64748b; display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px; }
    .tag { font-weight: bold; padding: 2px 6px; border-radius: 4px; font-size: 0.75rem; }
    .tag-recv { background: #dcfce7; color: #15803d; }
    .tag-sent { background: #e0e7ff; color: #4338ca; }
    .tag-adm { background: #fee2e2; color: #b91c1c; }
    #qrcode { display: flex; justify-content: center; margin-top: 10px; }
  </style>
</head>
<body>
<div class="container">
  <h1>💌 비밀 익명 칭찬 우체통</h1>

  <div class="card">
    <b>📱 24시간 친구 접속 QR코드</b>
    <div id="qrcode"></div>
  </div>

  <div class="card">
    <b>✍️ 칭찬 남기기 (익명 전달)</b>
    <div class="row">
      <input type="text" id="sender" placeholder="내 이름 (작성자)">
      <input type="text" id="receiver" placeholder="받을 친구 이름">
    </div>
    <textarea id="content" placeholder="따뜻한 칭찬의 한마디를 적어주세요."></textarea>
    <button id="sendBtn" onclick="send()">보내기</button>
  </div>

  <div class="card">
    <b>🔍 내 칭찬함 열기</b>
    <div class="row">
      <input type="text" id="myname" placeholder="확인할 내 이름 입력">
      <button onclick="search()" style="width: 100px; margin-top: 6px;">조회</button>
    </div>
  </div>

  <div class="card">
    <b>🛡️ 관리자 모드</b>
    <div class="row">
      <input type="password" id="admKey" placeholder="관리자 코드">
      <button class="btn-sub" onclick="adminLogin()" style="width: 100px; margin-top: 6px;">열람</button>
    </div>
  </div>

  <div class="card">
    <b id="title">칭찬 목록</b>
    <div id="list" style="margin-top: 10px; color: #94a3b8; font-size: 0.9rem;">이름을 입력하고 조회하세요.</div>
  </div>
</div>

<script>
  let currentAdminKey = "";

  new QRCode(document.getElementById('qrcode'), {
    text: window.location.href,
    width: 140,
    height: 140
  });

  // 1. 보내기
  async function send() {
    const sender = document.getElementById('sender').value.trim();
    const receiver = document.getElementById('receiver').value.trim();
    const content = document.getElementById('content').value.trim();
    if (!sender || !receiver || !content) return alert("모든 항목을 입력해주세요.");

    const btn = document.getElementById('sendBtn');
    btn.disabled = true;
    btn.textContent = "전송 중...";

    const res = await fetch('/api/send', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sender, receiver, content })
    });
    const data = await res.json();
    btn.disabled = false;
    btn.textContent = "보내기";

    if (data.success) {
      alert(`${receiver} 친구에게 칭찬을 전달했습니다!`);
      document.getElementById('content').value = "";
    }
  }

  // 2. 조회 (보낸 사람 & 받는 사람 둘 다 확인)
  async function search() {
    const name = document.getElementById('myname').value.trim();
    if (!name) return alert("이름을 입력하세요.");

    const res = await fetch(`/api/search?name=${encodeURIComponent(name)}`);
    const list = await res.json();

    document.getElementById('title').textContent = `💬 ${name}님의 칭찬 목록`;
    const box = document.getElementById('list');
    if (list.length === 0) return box.innerHTML = "도착하거나 보낸 칭찬이 없습니다.";

    box.innerHTML = list.map(item => {
      const isRecv = item.receiver === name;
      return `
        <div class="post">
          <div class="header">
            <span class="tag ${isRecv ? 'tag-recv' : 'tag-sent'}">${isRecv ? 'To. 나 (익명 친구)' : '내가 보낸 칭찬 (To. ' + item.receiver + ')'}</span>
            <span>${item.date}</span>
          </div>
          <div>${item.content}</div>
        </div>
      `;
    }).join('');
  }

  // 3. 관리자 전체 열람 (코드: 1234!)
  async function adminLogin() {
    const code = document.getElementById('admKey').value.trim();
    const res = await fetch(`/api/admin?code=${encodeURIComponent(code)}`);
    const data = await res.json();
    if (!data.success) return alert("관리자 코드가 일치하지 않습니다.");

    currentAdminKey = code;
    document.getElementById('title').textContent = "🛡️ 관리자 전체 열람";
    renderAdmin(data.list);
  }

  function renderAdmin(list) {
    const box = document.getElementById('list');
    if (list.length === 0) return box.innerHTML = "등록된 글이 없습니다.";

    box.innerHTML = list.map(item => `
      <div class="post">
        <div class="header">
          <span class="tag tag-adm">${item.sender} ➔ ${item.receiver}</span>
          <button class="btn-del" onclick="del(${item.id})">삭제</button>
        </div>
        <div>${item.content}</div>
      </div>
    `).join('');
  }

  async function del(id) {
    if (!confirm("삭제하시겠습니까?")) return;
    const res = await fetch(`/api/delete?id=${id}&code=${encodeURIComponent(currentAdminKey)}`, { method: 'DELETE' });
    const data = await res.json();
    renderAdmin(data.list);
  }
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_CODE)

@app.route('/api/send', methods=['POST'])
def send_compliment():
    data = request.json
    compliments = load_data()
    now = datetime.now()
    new_item = {
        'id': int(time.time() * 1000),
        'sender': data['sender'],
        'receiver': data['receiver'],
        'content': data['content'],
        'date': f"{now.month}/{now.day} {now.hour:02d}:{now.minute:02d}"
    }
    compliments.insert(0, new_item)
    save_data(compliments)
    return jsonify({'success': True})

@app.route('/api/search')
def search_compliment():
    name = request.args.get('name', '').strip()
    compliments = load_data()
    my_posts = [c for c in compliments if c['receiver'] == name or c['sender'] == name]
    return jsonify(my_posts)

@app.route('/api/admin')
def admin_view():
    if request.args.get('code') != ADMIN_KEY:
        return jsonify({'success': False})
    return jsonify({'success': True, 'list': load_data()})

@app.route('/api/delete', methods=['DELETE'])
def admin_delete():
    if request.args.get('code') != ADMIN_KEY:
        return jsonify({'success': False})
    compliments = load_data()
    post_id = int(request.args.get('id'))
    compliments = [c for c in compliments if c['id'] != post_id]
    save_data(compliments)
    return jsonify({'success': True, 'list': compliments})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)