#!/usr/bin/env python3
"""
MHQ Card Scanner — George's Version
=====================================
Connects to Google Sheets via service account.

Run:
  pip3 install flask gspread google-auth anthropic
  python3 george_card_scanner.py
"""

import base64
import json
import os
import webbrowser
import gspread
import anthropic
from google.oauth2.service_account import Credentials
from flask import Flask, request, jsonify, render_template_string
from datetime import datetime

# ── Configuration ─────────────────────────────────────────────────────────────
SPREADSHEET_ID    = "1ylBFfJEEk70ZUz0So_6hFhdcKx4KkZ-U3pch9p8JOAY"
ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

# ── Google Sheets client ───────────────────────────────────────────────────────
def get_sheet(tab_name):
    private_key = os.environ.get("GOOGLE_PRIVATE_KEY", "").replace("\\n", "\n")
    service_account_info = {
        "type": "service_account",
        "project_id": "mhq-card-scanner",
        "private_key_id": "3a6621310aac55f91294b34d5f3058a40250c0aa",
        "private_key": private_key,
        "client_email": "mhq-scanner@mhq-card-scanner.iam.gserviceaccount.com",
        "client_id": "103061283613421001106",
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
        "client_x509_cert_url": "https://www.googleapis.com/robot/v1/metadata/x509/mhq-scanner%40mhq-card-scanner.iam.gserviceaccount.com",
        "universe_domain": "googleapis.com"
    }
    scopes = ["https://www.googleapis.com/auth/spreadsheets"]
    creds  = Credentials.from_service_account_info(service_account_info, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).worksheet(tab_name)

# ── HTML ──────────────────────────────────────────────────────────────────────
HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>MHQ Card Scanner</title>
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #f0f2f5; min-height: 100vh;
    display: flex; align-items: flex-start; justify-content: center; padding: 32px 24px;
  }
  .card {
    background: white; border-radius: 16px;
    box-shadow: 0 4px 24px rgba(0,0,0,0.08);
    width: 100%; max-width: 540px; overflow: hidden;
  }
  .header { background: #C20019; padding: 28px 32px; color: white; }
  .header h1 { font-size: 20px; font-weight: 600; letter-spacing: -0.3px; }
  .header p  { font-size: 13px; color: rgba(255,255,255,0.6); margin-top: 4px; }
  .body { padding: 28px 32px; }

  .tabs { display: flex; gap: 8px; margin-bottom: 24px; }
  .tab {
    flex: 1; padding: 10px; border: 2px solid #e5e7eb; border-radius: 10px;
    background: white; cursor: pointer; font-size: 13px; font-weight: 600;
    color: #6b7280; transition: all 0.15s; text-align: center;
  }
  .tab.active { border-color: #C20019; background: #fff0f2; color: #C20019; }

  .scan-panel { display: none; }
  .scan-panel.visible { display: block; }

  .upload-zone {
    border: 2px dashed #d1d5db; border-radius: 10px; padding: 20px;
    text-align: center; cursor: pointer; transition: all 0.2s; margin-bottom: 12px;
    position: relative; min-height: 100px;
    display: flex; align-items: center; justify-content: center; flex-direction: column;
  }
  .upload-zone:hover { border-color: #C20019; background: #fff0f2; }
  .upload-zone.has-image { border-style: solid; border-color: #C20019; padding: 8px; }
  .upload-zone input[type=file] {
    position: absolute; inset: 0; opacity: 0; cursor: pointer; width: 100%; height: 100%;
  }
  .upload-zone img { max-height: 150px; border-radius: 6px; display: block; }
  .upload-icon { font-size: 28px; margin-bottom: 6px; }
  .upload-label { font-size: 13px; color: #6b7280; }
  .upload-label strong { color: #C20019; }

  .or-divider {
    text-align: center; font-size: 11px; font-weight: 700; color: #9ca3af;
    text-transform: uppercase; letter-spacing: 0.8px; margin: 12px 0;
  }
  textarea {
    width: 100%; padding: 12px 14px; border: 1.5px solid #e5e7eb;
    border-radius: 8px; font-size: 13px; color: #111; outline: none;
    resize: vertical; min-height: 90px; font-family: inherit; transition: border-color 0.15s;
  }
  textarea:focus { border-color: #C20019; }
  textarea::placeholder { color: #9ca3af; }

  .extract-btn {
    width: 100%; margin-top: 12px; padding: 11px;
    background: #C20019; color: white; border: none; border-radius: 9px;
    font-size: 14px; font-weight: 600; cursor: pointer; transition: background 0.15s;
  }
  .extract-btn:hover { background: #8c0012; }
  .extract-btn:disabled { background: #e8808e; cursor: not-allowed; }

  .divider { height: 1px; background: #f3f4f6; margin: 20px 0; }
  .section-title {
    font-size: 11px; font-weight: 700; color: #9ca3af;
    text-transform: uppercase; letter-spacing: 0.8px; margin-bottom: 14px;
  }
  .field { margin-bottom: 14px; }
  label {
    display: block; font-size: 12px; font-weight: 600; color: #374151;
    margin-bottom: 5px; text-transform: uppercase; letter-spacing: 0.4px;
  }
  input[type=text], input[type=email], input[type=tel] {
    width: 100%; padding: 10px 14px; border: 1.5px solid #e5e7eb;
    border-radius: 8px; font-size: 14px; color: #111; outline: none; transition: border-color 0.15s;
  }
  input:focus { border-color: #C20019; }
  .row { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }

  .tag-group { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 22px; }
  .tag-btn {
    padding: 10px; border: 2px solid #e5e7eb; border-radius: 10px;
    background: white; cursor: pointer; font-size: 13px; font-weight: 600;
    color: #6b7280; transition: all 0.15s; text-align: center;
  }
  .tag-btn.selected.customer { border-color: #C20019; background: #fff0f2; color: #8c0012; }
  .tag-btn.selected.vendor   { border-color: #059669; background: #ecfdf5; color: #047857; }

  .submit-btn {
    width: 100%; padding: 13px; background: #C20019; color: white;
    border: none; border-radius: 10px; font-size: 15px; font-weight: 600;
    cursor: pointer; transition: background 0.15s;
  }
  .submit-btn:hover { background: #8c0012; }
  .submit-btn:disabled { background: #9ca3af; cursor: not-allowed; }

  .toast {
    display: none; margin-top: 14px; padding: 12px 16px;
    border-radius: 8px; font-size: 13px; font-weight: 500; text-align: center;
  }
  .toast.success { background: #ecfdf5; color: #065f46; display: block; }
  .toast.error   { background: #fef2f2; color: #991b1b; display: block; }

  .spinner {
    display: inline-block; width: 14px; height: 14px;
    border: 2px solid rgba(255,255,255,0.3); border-top-color: white;
    border-radius: 50%; animation: spin 0.7s linear infinite;
    margin-right: 6px; vertical-align: middle;
  }
  @keyframes spin { to { transform: rotate(360deg); } }
</style>
</head>
<body>
<div class="card">
  <div class="header">
    <h1>MHQ Card Scanner</h1>
    <p>Add contacts directly to the MHQ spreadsheet</p>
  </div>
  <div class="body">

    <div class="tabs">
      <button class="tab active" onclick="switchTab('scan')"   id="tabScan">📷 Scan Card</button>
      <button class="tab"        onclick="switchTab('manual')" id="tabManual">✏️ Enter Manually</button>
    </div>

    <div class="scan-panel visible" id="scanPanel">
      <div class="upload-zone" id="uploadZone">
        <input type="file" id="cardImage" accept="image/*" onchange="previewImage(this)">
        <div id="uploadPlaceholder">
          <div class="upload-icon">📇</div>
          <div class="upload-label"><strong>Click to upload</strong> a photo of the card</div>
        </div>
        <img id="previewImg" style="display:none">
      </div>
      <div class="or-divider">— or paste card text —</div>
      <textarea id="pasteText" placeholder="Paste or type the text from the business card here..."></textarea>
      <button class="extract-btn" onclick="extractDetails()" id="extractBtn">✨ Auto-fill from Card</button>
    </div>

    <input type="hidden" id="firstName">
    <input type="hidden" id="lastName">
    <input type="hidden" id="email">
    <input type="hidden" id="company">
    <input type="hidden" id="phone">
    <input type="hidden" id="title">

    <div id="scanFields">
      <div class="divider"></div>
      <div class="section-title">Contact type</div>
      <div class="tag-group">
        <button class="tag-btn customer" onclick="selectTag('Customer')" id="btnCustomer">🤝 Customer</button>
        <button class="tag-btn vendor"   onclick="selectTag('Vendor')"   id="btnVendor">🏭 Vendor</button>
      </div>
      <button class="submit-btn" onclick="submitContact()" id="submitBtn">Add to Spreadsheet</button>
      <div class="toast" id="toast"></div>
    </div>

    <div id="manualFields" style="display:none">
      <div class="divider"></div>
      <div class="section-title">Contact type</div>
      <div class="tag-group">
        <button class="tag-btn customer" onclick="selectTag('Customer')" id="btnCustomerM">🤝 Customer</button>
        <button class="tag-btn vendor"   onclick="selectTag('Vendor')"   id="btnVendorM">🏭 Vendor</button>
      </div>
      <div class="section-title">Contact details</div>
      <div class="row">
        <div class="field"><label>First Name</label><input type="text" id="firstNameM" placeholder="Jane"></div>
        <div class="field"><label>Last Name</label><input type="text" id="lastNameM" placeholder="Smith"></div>
      </div>
      <div class="field">
        <label>Email <span style="color:#ef4444">*</span></label>
        <input type="email" id="emailM" placeholder="jane@example.com">
      </div>
      <div class="row">
        <div class="field"><label>Company</label><input type="text" id="companyM" placeholder="Acme Corp"></div>
        <div class="field"><label>Phone</label><input type="tel" id="phoneM" placeholder="(505) 555-0100"></div>
      </div>
      <div class="field" style="margin-bottom:22px">
        <label>Title / Role</label><input type="text" id="titleM" placeholder="Operations Manager">
      </div>
      <button class="submit-btn" onclick="submitContact()" id="submitBtnM">Add to Spreadsheet</button>
      <div class="toast" id="toastM"></div>
    </div>

  </div>
</div>

<script>
let selectedTag = null;
let currentMode = 'scan';

function switchTab(mode) {
  currentMode = mode;
  document.getElementById('tabScan').classList.toggle('active', mode === 'scan');
  document.getElementById('tabManual').classList.toggle('active', mode === 'manual');
  document.getElementById('scanPanel').classList.toggle('visible', mode === 'scan');
  document.getElementById('scanFields').style.display   = mode === 'scan'   ? 'block' : 'none';
  document.getElementById('manualFields').style.display = mode === 'manual' ? 'block' : 'none';
  selectedTag = null;
}

function selectTag(tag) {
  selectedTag = tag;
  ['Customer','Vendor'].forEach(t => {
    const key = t.toLowerCase();
    document.getElementById('btn' + t).className  = 'tag-btn ' + key + (tag === t ? ' selected' : '');
    document.getElementById('btn' + t + 'M').className = 'tag-btn ' + key + (tag === t ? ' selected' : '');
  });
}

function previewImage(input) {
  const zone = document.getElementById('uploadZone');
  const placeholder = document.getElementById('uploadPlaceholder');
  const img = document.getElementById('previewImg');
  if (input.files && input.files[0]) {
    const reader = new FileReader();
    reader.onload = e => {
      img.src = e.target.result;
      img.style.display = 'block';
      placeholder.style.display = 'none';
      zone.classList.add('has-image');
    };
    reader.readAsDataURL(input.files[0]);
  }
}

async function extractDetails() {
  const imageFile = document.getElementById('cardImage').files[0];
  const pasteText = document.getElementById('pasteText').value.trim();
  if (!imageFile && !pasteText) {
    showToast('Please upload a card photo or paste the card text first.', 'error');
    return;
  }
  const btn = document.getElementById('extractBtn');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Reading card…';
  const formData = new FormData();
  if (imageFile) formData.append('image', imageFile);
  if (pasteText) formData.append('text', pasteText);
  try {
    const res = await fetch('/extract', { method: 'POST', body: formData });
    const data = await res.json();
    if (res.ok && data) {
      if (data.firstName) document.getElementById('firstName').value = data.firstName;
      if (data.lastName)  document.getElementById('lastName').value  = data.lastName;
      if (data.email)     document.getElementById('email').value     = data.email;
      if (data.company)   document.getElementById('company').value   = data.company;
      if (data.phone)     document.getElementById('phone').value     = data.phone;
      if (data.title)     document.getElementById('title').value     = data.title;
      showToast('Card read — pick Customer or Vendor and hit Add to Spreadsheet.', 'success');
    } else {
      showToast(data.error || 'Could not read the card. Try pasting the text instead.', 'error');
    }
  } catch(e) {
    showToast('Something went wrong. Try again.', 'error');
  }
  btn.disabled = false;
  btn.innerHTML = '✨ Auto-fill from Card';
}

async function submitContact() {
  const isScan  = currentMode === 'scan';
  const toastId = isScan ? 'toast' : 'toastM';
  const btnId   = isScan ? 'submitBtn' : 'submitBtnM';
  const email   = isScan
    ? document.getElementById('email').value.trim()
    : document.getElementById('emailM').value.trim();
  if (!email)       { showToast('Email is required.', 'error', toastId); return; }
  if (!selectedTag) { showToast('Please select Customer or Vendor.', 'error', toastId); return; }
  const btn = document.getElementById(btnId);
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner"></span> Saving…';
  const payload = isScan ? {
    email, tag: selectedTag,
    firstName: document.getElementById('firstName').value.trim(),
    lastName:  document.getElementById('lastName').value.trim(),
    company:   document.getElementById('company').value.trim(),
    phone:     document.getElementById('phone').value.trim(),
    title:     document.getElementById('title').value.trim(),
  } : {
    email, tag: selectedTag,
    firstName: document.getElementById('firstNameM').value.trim(),
    lastName:  document.getElementById('lastNameM').value.trim(),
    company:   document.getElementById('companyM').value.trim(),
    phone:     document.getElementById('phoneM').value.trim(),
    title:     document.getElementById('titleM').value.trim(),
  };
  try {
    const res = await fetch('/add_contact', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if (res.ok) {
      showToast(`✓ ${email} added to ${selectedTag} tab.`, 'success', toastId);
      clearForm();
    } else {
      showToast(data.error || 'Something went wrong.', 'error', toastId);
    }
  } catch(e) {
    showToast('Could not reach the server.', 'error', toastId);
  }
  btn.disabled = false;
  btn.textContent = 'Add to Spreadsheet';
}

function clearForm() {
  ['firstName','lastName','email','company','phone','title',
   'firstNameM','lastNameM','emailM','companyM','phoneM','titleM'].forEach(id => {
    document.getElementById(id).value = '';
  });
  selectedTag = null;
  ['Customer','Vendor'].forEach(t => {
    document.getElementById('btn' + t).className  = 'tag-btn ' + t.toLowerCase();
    document.getElementById('btn' + t + 'M').className = 'tag-btn ' + t.toLowerCase();
  });
  document.getElementById('previewImg').style.display = 'none';
  document.getElementById('uploadPlaceholder').style.display = 'block';
  document.getElementById('uploadZone').classList.remove('has-image');
  document.getElementById('cardImage').value = '';
  document.getElementById('pasteText').value = '';
}

function showToast(msg, type, toastId = 'toast') {
  const t = document.getElementById(toastId);
  t.textContent = msg;
  t.className = 'toast ' + type;
  setTimeout(() => { t.className = 'toast'; }, 6000);
}
</script>
</body>
</html>
"""

# ── Flask app ─────────────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index():
    return render_template_string(HTML)

@app.route("/extract", methods=["POST"])
def extract():
    client     = anthropic.Anthropic(api_key=ANTHROPIC_API_KEY)
    image_file = request.files.get("image")
    paste_text = request.form.get("text", "").strip()
    prompt = (
        "Extract contact information from this business card. "
        "Return ONLY a JSON object with these keys (use empty string if not found): "
        "firstName, lastName, email, company, phone, title. "
        "No explanation, no markdown — just the raw JSON."
    )
    if image_file:
        image_data = base64.standard_b64encode(image_file.read()).decode("utf-8")
        mime_type  = image_file.content_type or "image/jpeg"
        messages   = [{"role": "user", "content": [
            {"type": "image", "source": {"type": "base64", "media_type": mime_type, "data": image_data}},
            {"type": "text",  "text": prompt}
        ]}]
    elif paste_text:
        messages = [{"role": "user", "content": f"{prompt}\n\nCard text:\n{paste_text}"}]
    else:
        return jsonify({"error": "No image or text provided."}), 400

    response = client.messages.create(model="claude-haiku-4-5-20251001", max_tokens=256, messages=messages)
    raw = response.content[0].text.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"): raw = raw[4:]
    raw = raw.strip()
    try:
        return jsonify(json.loads(raw))
    except json.JSONDecodeError:
        return jsonify({"error": "Could not parse the card. Try pasting the text instead."}), 422

@app.route("/add_contact", methods=["POST"])
def add_contact():
    data  = request.get_json()
    email = data.get("email", "").strip()
    tag   = data.get("tag", "Customer")
    if not email:
        return jsonify({"error": "Email is required."}), 400

    row = [
        datetime.now().strftime("%Y-%m-%d %H:%M"),
        data.get("firstName", ""),
        data.get("lastName", ""),
        email,
        data.get("company", ""),
        data.get("phone", ""),
        data.get("title", ""),
    ]

    try:
        # Customer → Customer tab, Vendor → Vendor tab
        tab_name = "Customer" if tag == "Customer" else "Vendor"
        sheet = get_sheet(tab_name)
        sheet.append_row(row)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

# ── Entry point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5001))
    print(f"\n  MHQ Card Scanner (George) is running → http://localhost:{port}\n")
    webbrowser.open(f"http://localhost:{port}")
    app.run(host="0.0.0.0", port=port, debug=False)
