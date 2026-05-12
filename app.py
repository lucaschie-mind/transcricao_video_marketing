import streamlit as st
import os
import io
import zipfile
import json
import tempfile
import threading
from pathlib import Path
from datetime import datetime

# ── Page config ──────────────────────────────────────────────────────────────
st.set_page_config(
    page_title="VideoTranscriber",
    page_icon="🎬",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# ── Inject custom CSS ─────────────────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Space+Mono:wght@400;700&family=Syne:wght@400;600;700;800&display=swap');

:root {
  --bg: #0a0a0f;
  --surface: #111118;
  --border: #22223a;
  --accent: #7c5cbf;
  --accent2: #c084fc;
  --text: #e8e8f0;
  --muted: #6b6b8a;
  --success: #34d399;
  --error: #f87171;
  --warn: #fbbf24;
}

html, body, [data-testid="stAppViewContainer"] {
  background: var(--bg) !important;
  color: var(--text) !important;
  font-family: 'Syne', sans-serif !important;
}

[data-testid="stHeader"] { display: none; }

.main .block-container {
  padding: 2rem 3rem !important;
  max-width: 1200px;
}

/* Titles */
h1, h2, h3 { font-family: 'Syne', sans-serif !important; font-weight: 800 !important; }

/* Inputs */
.stTextInput > div > div > input,
.stSelectbox > div > div,
.stFileUploader {
  background: var(--surface) !important;
  border: 1px solid var(--border) !important;
  border-radius: 8px !important;
  color: var(--text) !important;
  font-family: 'Syne', sans-serif !important;
}

/* Buttons */
.stButton > button {
  background: var(--accent) !important;
  color: #fff !important;
  border: none !important;
  border-radius: 8px !important;
  font-family: 'Syne', sans-serif !important;
  font-weight: 700 !important;
  padding: 0.6rem 1.4rem !important;
  transition: all 0.2s !important;
}
.stButton > button:hover {
  background: var(--accent2) !important;
  transform: translateY(-1px) !important;
  box-shadow: 0 4px 20px rgba(124,92,191,0.4) !important;
}

/* Cards */
.card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 1.2rem 1.5rem;
  margin-bottom: 0.75rem;
}

/* Status badges */
.badge {
  display: inline-block;
  padding: 2px 10px;
  border-radius: 20px;
  font-size: 0.75rem;
  font-weight: 700;
  font-family: 'Space Mono', monospace;
}
.badge-pending   { background: rgba(251,191,36,0.15); color: var(--warn); border: 1px solid rgba(251,191,36,0.3); }
.badge-running   { background: rgba(124,92,191,0.15); color: var(--accent2); border: 1px solid rgba(124,92,191,0.3); }
.badge-done      { background: rgba(52,211,153,0.15); color: var(--success); border: 1px solid rgba(52,211,153,0.3); }
.badge-error     { background: rgba(248,113,113,0.15); color: var(--error); border: 1px solid rgba(248,113,113,0.3); }

/* Progress */
.stProgress > div > div > div { background: var(--accent2) !important; }

/* Selectbox label */
.stSelectbox label, .stTextInput label, .stFileUploader label {
  color: var(--muted) !important;
  font-size: 0.8rem !important;
  font-family: 'Space Mono', monospace !important;
  text-transform: uppercase !important;
  letter-spacing: 0.08em !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
  background: var(--surface) !important;
  border-right: 1px solid var(--border) !important;
}

/* Divider */
hr { border-color: var(--border) !important; }

/* Info / warning boxes */
.stAlert { border-radius: 8px !important; }

/* Radio */
.stRadio > div { gap: 1rem !important; }
.stRadio label { color: var(--text) !important; }

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
  background: var(--surface) !important;
  border-radius: 8px !important;
  border: 1px solid var(--border) !important;
  gap: 0 !important;
}
.stTabs [data-baseweb="tab"] {
  color: var(--muted) !important;
  font-family: 'Syne', sans-serif !important;
  font-weight: 600 !important;
}
.stTabs [aria-selected="true"] {
  background: var(--accent) !important;
  color: #fff !important;
  border-radius: 6px !important;
}

/* File list */
.file-row {
  display: flex;
  align-items: center;
  gap: 1rem;
  padding: 0.8rem 1rem;
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  margin-bottom: 0.5rem;
}
.file-icon { font-size: 1.4rem; }
.file-name { flex: 1; font-weight: 600; word-break: break-all; }
.file-size { color: var(--muted); font-size: 0.8rem; font-family: 'Space Mono', monospace; }
</style>
""", unsafe_allow_html=True)


# ── Session state init ────────────────────────────────────────────────────────
for key, default in {
    "drive_folders": [],
    "transcriptions": {},   # filename -> {"text": ..., "status": ...}
    "file_folder_map": {},  # filename -> folder_id
    "global_folder": None,
    "drive_url": "",
    "drive_connected": False,
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ── Helpers ───────────────────────────────────────────────────────────────────
def format_bytes(size):
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} TB"


def get_drive_service():
    """Return an authenticated Google Drive service or None."""
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
        creds_json = os.environ.get("GOOGLE_SERVICE_ACCOUNT_JSON", "")
        if not creds_json:
            return None
        info = json.loads(creds_json)
        scopes = ["https://www.googleapis.com/auth/drive"]
        creds = Credentials.from_service_account_info(info, scopes=scopes)
        return build("drive", "v3", credentials=creds)
    except Exception as e:
        st.error(f"Drive auth error: {e}")
        return None


def list_drive_folders(service, parent_id="root", depth=0, max_depth=3):
    """Recursively list folders from Google Drive."""
    if depth > max_depth:
        return []
    results = []
    try:
        query = f"'{parent_id}' in parents and mimeType='application/vnd.google-apps.folder' and trashed=false"
        resp = service.files().list(q=query, fields="files(id,name)", pageSize=200).execute()
        for f in resp.get("files", []):
            prefix = "  " * depth + ("└─ " if depth > 0 else "")
            results.append({"id": f["id"], "name": f["name"], "label": prefix + f["name"], "depth": depth})
            results += list_drive_folders(service, f["id"], depth + 1, max_depth)
    except Exception as e:
        st.warning(f"Could not list folders: {e}")
    return results


def upload_to_drive(service, file_bytes, filename, folder_id):
    """Upload a text file to a Drive folder."""
    from googleapiclient.http import MediaIoBaseUpload
    meta = {"name": filename, "parents": [folder_id]}
    media = MediaIoBaseUpload(io.BytesIO(file_bytes), mimetype="text/plain")
    service.files().create(body=meta, media_body=media, fields="id").execute()


def transcribe_video(file_bytes, filename, model_size="base"):
    """Transcribe audio from video bytes using Whisper."""
    import whisper
    import numpy as np

    with tempfile.NamedTemporaryFile(suffix=Path(filename).suffix, delete=False) as tmp:
        tmp.write(file_bytes)
        tmp_path = tmp.name

    try:
        model = whisper.load_model(model_size)
        result = model.transcribe(tmp_path)
        return result["text"].strip()
    finally:
        os.unlink(tmp_path)


def run_transcription_job(uploaded_files, folder_mode, global_folder_id, file_folder_map, model_size, service):
    """Run transcription for all files, updating session state."""
    total = len(uploaded_files)
    progress_bar = st.progress(0, text="Iniciando transcrições…")

    for i, uf in enumerate(uploaded_files):
        name = uf.name
        stem = Path(name).stem
        txt_name = stem + ".txt"

        st.session_state.transcriptions[name]["status"] = "running"
        progress_bar.progress((i) / total, text=f"Transcrevendo {name}…")

        try:
            file_bytes = uf.read()
            text = transcribe_video(file_bytes, name, model_size)
            st.session_state.transcriptions[name]["text"] = text
            st.session_state.transcriptions[name]["status"] = "done"

            # Upload to Drive if connected
            if service:
                fid = global_folder_id if folder_mode == "global" else file_folder_map.get(name)
                if fid:
                    upload_to_drive(service, text.encode("utf-8"), txt_name, fid)
                    st.session_state.transcriptions[name]["uploaded"] = True

        except Exception as e:
            st.session_state.transcriptions[name]["status"] = "error"
            st.session_state.transcriptions[name]["error"] = str(e)

        progress_bar.progress((i + 1) / total, text=f"Concluído {i+1}/{total}")

    progress_bar.empty()
    st.rerun()


# ══════════════════════════════════════════════════════════════════════════════
# UI
# ══════════════════════════════════════════════════════════════════════════════

# Header
st.markdown("""
<div style="margin-bottom:2.5rem">
  <div style="font-family:'Space Mono',monospace;font-size:0.75rem;color:#7c5cbf;letter-spacing:0.15em;margin-bottom:0.4rem">
    ▶ FERRAMENTA DE TRANSCRIÇÃO
  </div>
  <h1 style="font-size:2.8rem;margin:0;background:linear-gradient(135deg,#e8e8f0,#c084fc);-webkit-background-clip:text;-webkit-text-fill-color:transparent">
    VideoTranscriber
  </h1>
  <p style="color:#6b6b8a;margin-top:0.5rem;font-size:1rem">
    Faça upload de vídeos, transcreva automaticamente e salve no Google Drive
  </p>
</div>
""", unsafe_allow_html=True)

tabs = st.tabs(["📁 Upload & Configuração", "⚡ Transcrição", "📥 Download"])

# ─────────────────────────────────────────────────────────────────────────────
# TAB 1 — Upload & Config
# ─────────────────────────────────────────────────────────────────────────────
with tabs[0]:
    col_left, col_right = st.columns([3, 2], gap="large")

    with col_left:
        st.markdown("### 🎬 Arquivos de Vídeo")
        uploaded_files = st.file_uploader(
            "Selecione os vídeos",
            type=["mp4", "mkv", "avi", "mov", "webm", "flv", "wmv", "m4v", "ts"],
            accept_multiple_files=True,
            key="video_uploader",
        )

        if uploaded_files:
            st.markdown(f"<div style='color:#6b6b8a;font-size:0.8rem;margin-bottom:0.5rem'>{len(uploaded_files)} arquivo(s) selecionado(s)</div>", unsafe_allow_html=True)
            for uf in uploaded_files:
                size_str = format_bytes(uf.size)
                st.markdown(f"""
                <div class="file-row">
                  <span class="file-icon">🎞️</span>
                  <span class="file-name">{uf.name}</span>
                  <span class="file-size">{size_str}</span>
                </div>
                """, unsafe_allow_html=True)

    with col_right:
        st.markdown("### ⚙️ Configurações")

        # Whisper model
        model_size = st.selectbox(
            "Modelo Whisper",
            ["tiny", "base", "small", "medium", "large"],
            index=1,
            help="Modelos maiores são mais precisos porém mais lentos",
        )
        st.markdown(f"<div style='color:#6b6b8a;font-size:0.75rem;margin-top:-0.5rem;margin-bottom:1rem'>tiny=mais rápido · large=mais preciso</div>", unsafe_allow_html=True)

        st.markdown("---")
        st.markdown("### ☁️ Google Drive (opcional)")

        drive_url = st.text_input(
            "URL ou ID da pasta raiz do Drive",
            value=st.session_state.drive_url,
            placeholder="https://drive.google.com/drive/folders/… ou ID",
        )

        if st.button("🔗 Conectar ao Drive"):
            if drive_url.strip():
                # Extract folder ID from URL if needed
                folder_id = drive_url.strip()
                if "folders/" in folder_id:
                    folder_id = folder_id.split("folders/")[-1].split("?")[0].strip()

                service = get_drive_service()
                if service:
                    with st.spinner("Listando pastas…"):
                        folders = list_drive_folders(service, parent_id=folder_id)
                    if folders is not None:
                        st.session_state.drive_folders = [{"id": folder_id, "label": "📁 (raiz selecionada)", "name": "raiz", "depth": 0}] + folders
                        st.session_state.drive_connected = True
                        st.session_state.drive_url = drive_url
                        st.success(f"✅ {len(folders)+1} pasta(s) encontrada(s)!")
                else:
                    st.warning("⚠️ Credenciais de serviço não configuradas. Veja o README para instruções.")
                    # Still allow folder name entry manually
                    st.session_state.drive_connected = False
            else:
                st.error("Informe a URL ou ID da pasta do Drive.")

    # ── Folder assignment ────────────────────────────────────────────────────
    if uploaded_files:
        st.markdown("---")
        st.markdown("### 📂 Destino das Transcrições")

        folder_mode = st.radio(
            "Modo de pasta destino",
            ["Uma pasta para todos", "Pasta por arquivo"],
            horizontal=True,
        )

        folder_options = [f["label"] for f in st.session_state.drive_folders] if st.session_state.drive_folders else []
        folder_ids = {f["label"]: f["id"] for f in st.session_state.drive_folders}

        if folder_mode == "Uma pasta para todos":
            if folder_options:
                chosen_label = st.selectbox("Pasta destino", folder_options)
                st.session_state.global_folder = folder_ids.get(chosen_label)
            else:
                st.info("ℹ️ Conecte ao Drive para escolher a pasta destino, ou os arquivos só serão salvos para download.")
                st.session_state.global_folder = None

        else:  # per-file
            st.markdown("Escolha a pasta destino para cada vídeo:")
            for uf in uploaded_files:
                cols = st.columns([3, 2])
                with cols[0]:
                    st.markdown(f"""
                    <div class="file-row" style="margin:0">
                      <span class="file-icon">🎞️</span>
                      <span class="file-name">{uf.name}</span>
                    </div>
                    """, unsafe_allow_html=True)
                with cols[1]:
                    if folder_options:
                        sel = st.selectbox("", folder_options, key=f"folder_{uf.name}", label_visibility="collapsed")
                        st.session_state.file_folder_map[uf.name] = folder_ids.get(sel)
                    else:
                        st.markdown("<span style='color:#6b6b8a;font-size:0.85rem'>Drive não conectado</span>", unsafe_allow_html=True)

        # ── Start button ─────────────────────────────────────────────────────
        st.markdown("<br>", unsafe_allow_html=True)
        if st.button("🚀 Iniciar Transcrições", use_container_width=True):
            # Init state for each file
            for uf in uploaded_files:
                st.session_state.transcriptions[uf.name] = {
                    "text": "",
                    "status": "pending",
                    "uploaded": False,
                    "error": "",
                }
            st.session_state["pending_transcription"] = True
            st.session_state["pending_files"] = uploaded_files
            st.session_state["pending_model"] = model_size
            st.session_state["pending_folder_mode"] = folder_mode
            st.session_state["pending_global_folder"] = st.session_state.global_folder
            st.session_state["pending_file_folder_map"] = st.session_state.file_folder_map.copy()
            st.rerun()


# ─────────────────────────────────────────────────────────────────────────────
# TAB 2 — Transcription status
# ─────────────────────────────────────────────────────────────────────────────
with tabs[1]:
    transcriptions = st.session_state.transcriptions

    if not transcriptions:
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:#6b6b8a">
          <div style="font-size:3rem;margin-bottom:1rem">🎙️</div>
          <div style="font-size:1.1rem">Nenhuma transcrição iniciada ainda.</div>
          <div style="font-size:0.85rem;margin-top:0.5rem">Vá para a aba Upload & Configuração para começar.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        # Run pending job
        if st.session_state.get("pending_transcription"):
            st.session_state["pending_transcription"] = False
            pfiles = st.session_state.get("pending_files", [])
            pmodel = st.session_state.get("pending_model", "base")
            pfmode = st.session_state.get("pending_folder_mode", "global")
            pgfolder = st.session_state.get("pending_global_folder")
            pffmap = st.session_state.get("pending_file_folder_map", {})
            service = get_drive_service()
            run_transcription_job(pfiles, pfmode, pgfolder, pffmap, pmodel, service)

        done_count = sum(1 for v in transcriptions.values() if v["status"] == "done")
        err_count  = sum(1 for v in transcriptions.values() if v["status"] == "error")
        total      = len(transcriptions)

        # Summary
        col1, col2, col3 = st.columns(3)
        with col1:
            st.markdown(f"""
            <div class="card" style="text-align:center">
              <div style="font-size:2rem;font-weight:800;color:#e8e8f0">{total}</div>
              <div style="color:#6b6b8a;font-size:0.8rem;font-family:'Space Mono',monospace">TOTAL</div>
            </div>
            """, unsafe_allow_html=True)
        with col2:
            st.markdown(f"""
            <div class="card" style="text-align:center">
              <div style="font-size:2rem;font-weight:800;color:#34d399">{done_count}</div>
              <div style="color:#6b6b8a;font-size:0.8rem;font-family:'Space Mono',monospace">CONCLUÍDOS</div>
            </div>
            """, unsafe_allow_html=True)
        with col3:
            st.markdown(f"""
            <div class="card" style="text-align:center">
              <div style="font-size:2rem;font-weight:800;color:#f87171">{err_count}</div>
              <div style="color:#6b6b8a;font-size:0.8rem;font-family:'Space Mono',monospace">ERROS</div>
            </div>
            """, unsafe_allow_html=True)

        st.markdown("<br>", unsafe_allow_html=True)

        badge_map = {
            "pending": "badge-pending", "running": "badge-running",
            "done": "badge-done", "error": "badge-error",
        }
        label_map = {
            "pending": "AGUARDANDO", "running": "TRANSCREVENDO",
            "done": "CONCLUÍDO", "error": "ERRO",
        }

        for fname, info in transcriptions.items():
            status = info["status"]
            badge_cls = badge_map.get(status, "badge-pending")
            badge_lbl = label_map.get(status, status.upper())
            uploaded_badge = ' <span class="badge badge-done">☁️ NO DRIVE</span>' if info.get("uploaded") else ""

            with st.expander(f"🎞️ {fname}", expanded=(status in ("error", "done"))):
                st.markdown(f'<span class="badge {badge_cls}">{badge_lbl}</span>{uploaded_badge}', unsafe_allow_html=True)

                if status == "done":
                    st.text_area("Transcrição", value=info["text"], height=200, key=f"ta_{fname}", label_visibility="collapsed")
                elif status == "error":
                    st.error(f"Erro: {info.get('error', 'Desconhecido')}")
                elif status == "running":
                    st.info("Transcrevendo… aguarde.")
                else:
                    st.markdown("<span style='color:#6b6b8a'>Na fila…</span>", unsafe_allow_html=True)


# ─────────────────────────────────────────────────────────────────────────────
# TAB 3 — Download
# ─────────────────────────────────────────────────────────────────────────────
with tabs[2]:
    transcriptions = st.session_state.transcriptions
    done_items = {k: v for k, v in transcriptions.items() if v["status"] == "done" and v["text"]}

    if not done_items:
        st.markdown("""
        <div style="text-align:center;padding:3rem;color:#6b6b8a">
          <div style="font-size:3rem;margin-bottom:1rem">📥</div>
          <div style="font-size:1.1rem">Nenhuma transcrição disponível para download.</div>
          <div style="font-size:0.85rem;margin-top:0.5rem">Complete as transcrições primeiro.</div>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown(f"### 📥 {len(done_items)} transcrição(ões) disponível(is)")

        # Individual downloads
        for fname, info in done_items.items():
            stem = Path(fname).stem
            txt_bytes = info["text"].encode("utf-8")
            cols = st.columns([3, 1])
            with cols[0]:
                st.markdown(f"""
                <div class="file-row">
                  <span class="file-icon">📄</span>
                  <span class="file-name">{stem}.txt</span>
                  <span class="file-size">{format_bytes(len(txt_bytes))}</span>
                </div>
                """, unsafe_allow_html=True)
            with cols[1]:
                st.download_button(
                    "⬇️ Baixar",
                    data=txt_bytes,
                    file_name=f"{stem}.txt",
                    mime="text/plain",
                    key=f"dl_{fname}",
                )

        st.markdown("---")

        # Bulk ZIP download
        if len(done_items) > 1:
            zip_buffer = io.BytesIO()
            with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
                for fname, info in done_items.items():
                    stem = Path(fname).stem
                    zf.writestr(f"{stem}.txt", info["text"])
            zip_buffer.seek(0)

            st.download_button(
                "📦 Baixar Todos (ZIP)",
                data=zip_buffer.getvalue(),
                file_name=f"transcricoes_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
                mime="application/zip",
                use_container_width=True,
            )
        
        st.markdown("<br>", unsafe_allow_html=True)
        st.markdown("""
        <div class="card" style="border-color:rgba(124,92,191,0.3);background:rgba(124,92,191,0.05)">
          <div style="font-size:0.85rem;color:#6b6b8a">
            💡 <strong style="color:#c084fc">Dica:</strong> Os arquivos <code>.txt</code> têm o mesmo nome dos vídeos originais.
            Se salvou no Drive, os arquivos também estão disponíveis lá.
          </div>
        </div>
        """, unsafe_allow_html=True)
