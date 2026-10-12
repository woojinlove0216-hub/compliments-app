import os
import json
import time
import html
from datetime import datetime
from threading import Lock
from flask import Flask, request, jsonify, render_template_string

app = Flask(__name__)

# Render의 인스턴스 파일에 저장합니다.
# 무료 호스팅 환경에서는 재배포 시 파일이 초기화될 수 있습니다.
DATA_FILE = os.path.join(os.path.dirname(__file__), "compliments.json")
ADMIN_KEY = "1234!"

# 관리자 로그인 실패 제한
admin_failures = 0
admin_locked_until = 0.0
admin_lock = Lock()

def load_data():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []

def save_data(items):
    temp_file = DATA_FILE + ".tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(items, f, ensure_ascii=False, indent=2)
    os.replace(temp_file, DATA_FILE)

def safe_text(value, max_length):
    if not isinstance(value, str):
        return ""
    return value.strip()[:max_length]

HTML_CODE = r"""
<!DOCTYPE html>
<html lang="ko">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>익명 칭찬 우체통</title>
  <style>
    * { box-sizing: border-box; }
    body { margin: 0; padding: 16px; background: #f8fafc; color: #1e293b;
           font-family: Arial, sans-serif; }
    main { max-width: 520px; margin: auto; }
    h1 { text-align: center; font-size: 1.5rem; }
    section { background: white; padding: 16px; margin: 14px 0;
              border: 1px solid #dbe2ea; border-radius: 12px; }
    input, textarea, button { width: 100%; padding: 11px; margin-top: 8px;
              border: 1px solid #cbd5e1; border-radius: 7px; font-size: 1rem; }
    textarea { min-height: 90px; resize: vertical; }
    button { color: white; background: #4f46e5; border: 0; font-weight: bold; cursor: pointer; }
    button:disabled { opacity: .6; cursor: wait; }
    .row { display: flex; gap: 8px; align-items: center; }
    .row input { min-width: 0; }
    .row button { width: auto; flex: 0 0 90px; }
    .secondary { background: #475569; }
    .post { padding: 12px; margin-top: 10px; border-radius: 8px; background: #f1f5f9; }
    .meta { display: flex; justify-content: space-between; gap: 8px;
            margin-bottom: 7px; color: #64748b; font-size: .85rem; }
    .content { white-space: pre-wrap; overflow-wrap: anywhere; }
    .received { color: #166534; }
    .sent { color: #3730a3; }
    .admin { color: #991b1b; }
    .delete { width: auto; padding: 5px 9px; margin: 0; background: #dc2626; }
    #message { min-height: 1.3em; color: #475569; }
  </style>
</head>
<body>
<main>
  <h1>💌 익명 칭찬 우체통</h1>

  <section>
    <h2>칭찬 남기기</h2>
    <input id="sender" maxlength="40" placeholder="보내는 사람 이름">
    <input id="receiver" maxlength="40" placeholder="받는 사람 이름">
    <textarea id="content" maxlength="1000" placeholder="칭찬 내용을 적어주세요"></textarea>
    <button id="sendButton" type="button">익명으로 보내기</button>
  </section>

  <section>
    <h2>내 칭찬 확인</h2>
    <div class="row">
      <input id="lookupName" maxlength="40" placeholder="이름 입력">
      <button id="lookupButton" type="button">조회</button>
    </div>
  </section>

  <section>
    <h2>관리자</h2>
    <div class="row">
      <input id="adminCode" type="password" placeholder="관리자 코드">
      <button id="adminButton" class="secondary" type="button">전체 보기</button>
    </div>
    <p id="message" aria-live="polite"></p>
  </section>

  <section>
    <h2 id="listTitle">칭찬 목록</h2>
    <div id="list">이름을 입력하고 조회하세요.</div>
  </section>
</main>

<script>
let adminCodeForDelete = "";

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, ch => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;"
  })[ch]);
}

async function api(url, options = {}) {
  const response = await fetch(url, options);
  const result = await response.json().catch(() => ({}));
  if (!response.ok) {
    const error = new Error(result.message || `요청 실패 (${response.status})`);
    error.status = response.status;
    throw error;
  }
  return result;
}

function showPosts(posts, name) {
  const box = document.getElementById("list");
  if (!posts.length) {
    box.textContent = "관련된 칭찬이 없습니다.";
    return;
  }

  box.innerHTML = posts.map(post => {
    const received = name && post.receiver === name;
    const label = name
      ? (received ? "To. 나 (익명)" : `내가 보냄 · To. ${escapeHtml(post.receiver)}`)
      : `${escapeHtml(post.sender)} → ${escapeHtml(post.receiver)}`;

    return `<article class="post">
      <div class="meta">
        <span class="${name ? (received ? "received" : "sent") : "admin"}">${label}</span>
        <span>${escapeHtml(post.date)}</span>
      </div>
      <div class="content">${escapeHtml(post.content)}</div>
    </article>`;
  }).join("");
}

async function sendCompliment() {
  const sender = document.getElementById("sender").value.trim();
  const receiver = document.getElementById("receiver").value.trim();
  const content = document.getElementById("content").value.trim();
  const button = document.getElementById("sendButton");

  if (!sender || !receiver || !content) {
    alert("보내는 사람, 받는 사람, 칭찬 내용을 모두 입력해주세요.");
    return;
  }

  button.disabled = true;
  button.textContent = "보내는 중...";
  try {
    await api("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ sender, receiver, content })
    });
    alert("칭찬을 보냈습니다.");
    document.getElementById("content").value = "";
  } catch (error) {
    alert("전송 실패: " + error.message);
  } finally {
    button.disabled = false;
    button.textContent = "익명으로 보내기";
  }
}

async function lookupCompliments() {
  const name = document.getElementById("lookupName").value.trim();
  if (!name) {
    alert("이름을 입력해주세요.");
    return;
  }

  document.getElementById("listTitle").textContent = `${name}님의 칭찬`;
  document.getElementById("list").textContent = "불러오는 중...";
  try {
    const posts = await api(`/api/search?name=${encodeURIComponent(name)}`);
    showPosts(posts, name);
  } catch (error) {
    document.getElementById("list").textContent = "조회 실패: " + error.message;
  }
}

async function adminLogin() {
  const code = document.getElementById("adminCode").value;
  const message = document.getElementById("message");
  message.textContent = "";

  try {
    const result = await api(`/api/admin?code=${encodeURIComponent(code)}`);
    adminCodeForDelete = code;
    document.getElementById("listTitle").textContent = "관리자 전체 목록";
    showPosts(result.list, "");
    renderDeleteButtons(result.list);
  } catch (error) {
    message.textContent = error.message;
  }
}

function renderDeleteButtons(posts) {
  const box = document.getElementById("list");
  if (!posts.length) return;

  box.innerHTML = posts.map(post => `
    <article class="post">
      <div class="meta">
        <span>${escapeHtml(post.sender)} → ${escapeHtml(post.receiver)}</span>
        <button class="delete" type="button" data-id="${post.id}">삭제</button>
      </div>
      <div class="content">${escapeHtml(post.content)}</div>
      <div class="meta">${escapeHtml(post.date)}</div>
    </article>`).join("");

  box.querySelectorAll(".delete").forEach(button => {
    button.addEventListener("click", () => deletePost(button.dataset.id));
  });
}

async function deletePost(id) {
  if (!confirm("이 칭찬을 삭제할까요?")) return;
  try {
    const result = await api(
      `/api/delete?id=${encodeURIComponent(id)}&code=${encodeURIComponent(adminCodeForDelete)}`,
      { method: "DELETE" }
    );
    renderDeleteButtons(result.list);
  } catch (error) {
    alert("삭제 실패: " + error.message);
  }
}

document.getElementById("sendButton").addEventListener("click", sendCompliment);
document.getElementById("lookupButton").addEventListener("click", lookupCompliments);
document.getElementById("adminButton").addEventListener("click", adminLogin);
</script>
</body>
</html>
"""

@app.get("/")
def index():
    return render_template_string(HTML_CODE)

@app.post("/api/send")
def send_compliment():
    data = request.get_json(silent=True) or {}
    sender = safe_text(data.get("sender"), 40)
    receiver = safe_text(data.get("receiver"), 40)
    content = safe_text(data.get("content"), 1000)

    if not sender or not receiver or not content:
        return jsonify({"message": "모든 항목을 입력해주세요."}), 400

    posts = load_data()
    now = datetime.now()
    posts.insert(0, {
        "id": str(time.time_ns()),
        "sender": sender,
        "receiver": receiver,
        "content": content,
        "date": now.strftime("%Y-%m-%d %H:%M")
    })

    try:
        save_data(posts)
    except OSError:
        return jsonify({"message": "서버에 저장하지 못했습니다."}), 500

    return jsonify({"success": True})

@app.get("/api/search")
def search_compliments():
    name = safe_text(request.args.get("name", ""), 40)
    if not name:
        return jsonify([])

    # 이름만 입력하는 방식은 본인 인증이 아닙니다.
    posts = load_data()
    return jsonify([
        post for post in posts
        if post.get("sender") == name or post.get("receiver") == name
    ])

@app.get("/api/admin")
def admin_list():
    global admin_failures, admin_locked_until

    now = time.time()
    with admin_lock:
        remaining = int(admin_locked_until - now + 0.999)
        if remaining > 0:
            return jsonify({
                "message": f"로그인이 잠겼습니다. {remaining}초 후 다시 시도하세요."
            }), 429

        code = request.args.get("code", "")
        if code != ADMIN_KEY:
            admin_failures += 1

            if admin_failures >= 3:
                lock_seconds = 30 + (admin_failures - 3) * 5
                admin_locked_until = now + lock_seconds
                return jsonify({
                    "message": f"코드가 틀렸습니다. {lock_seconds}초 동안 잠깁니다."
                }), 401

            return jsonify({
                "message": f"코드가 틀렸습니다. {3 - admin_failures}회 더 실패하면 잠깁니다."
            }), 401

        admin_failures = 0
        admin_locked_until = 0.0

    return jsonify({"success": True, "list": load_data()})

@app.delete("/api/delete")
def delete_compliment():
    global admin_failures, admin_locked_until

    now = time.time()
    with admin_lock:
        if now < admin_locked_until:
            remaining = int(admin_locked_until - now + 0.999)
            return jsonify({"message": f"{remaining}초 후 다시 시도하세요."}), 429

        if request.args.get("code", "") != ADMIN_KEY:
            return jsonify({"message": "관리자 인증이 필요합니다."}), 403

    post_id = request.args.get("id", "")
    posts = load_data()
    updated = [post for post in posts if post.get("id") != post_id]

    try:
        save_data(updated)
    except OSError:
        return jsonify({"message": "삭제를 저장하지 못했습니다."}), 500

    return jsonify({"success": True, "list": updated})