# 🎬 VideoTranscriber

Aplicação Streamlit para transcrição automática de vídeos com integração ao Google Drive.

## ✨ Funcionalidades

- Upload de múltiplos vídeos (MP4, MKV, AVI, MOV, WEBM, FLV, WMV, M4V, TS)
- Transcrição automática via **OpenAI Whisper** (5 tamanhos de modelo: tiny → large)
- Integração com **Google Drive**: lista pastas/subpastas e salva as transcrições
- Pasta destino: **uma para todos** os arquivos ou **individual por arquivo**
- Download individual (.txt) ou em lote (.zip)

## 🚀 Deploy no Railway

### 1. Faça upload do código

```bash
# Crie o repositório no GitHub e faça push
git init
git add .
git commit -m "initial commit"
git remote add origin https://github.com/SEU_USUARIO/video-transcriber.git
git push -u origin main
```

### 2. Crie o projeto no Railway

1. Acesse [railway.app](https://railway.app) → **New Project** → **Deploy from GitHub**
2. Selecione o repositório
3. O Railway detectará automaticamente o `nixpacks.toml`

### 3. Configure a variável de ambiente (para Google Drive)

No painel do Railway, vá em **Variables** e adicione:

```
GOOGLE_SERVICE_ACCOUNT_JSON = { ... conteúdo do JSON da conta de serviço ... }
```

#### Como gerar a Service Account:

1. Acesse o [Google Cloud Console](https://console.cloud.google.com)
2. Crie um projeto (ou use um existente)
3. Ative a **Google Drive API** em APIs & Services → Library
4. Vá em **IAM & Admin** → **Service Accounts** → **Create Service Account**
5. Dê um nome e clique em **Create and Continue**
6. Pule a etapa de permissões e clique em **Done**
7. Clique na conta criada → **Keys** → **Add Key** → **JSON**
8. Copie o conteúdo completo do arquivo JSON e cole na variável `GOOGLE_SERVICE_ACCOUNT_JSON`

#### Compartilhe a pasta do Drive com a Service Account:

1. No arquivo JSON baixado, copie o campo `client_email` (algo como `nome@projeto.iam.gserviceaccount.com`)
2. No Google Drive, clique com o botão direito na pasta raiz que quer usar → **Compartilhar**
3. Cole o `client_email` e dê permissão de **Editor**

### 4. Obtenha a URL da pasta do Drive

No Google Drive, abra a pasta desejada e copie a URL:
```
https://drive.google.com/drive/folders/1AbCdEfGhIjKlMnOpQrStUvWxYz
```
Cole essa URL na aplicação para listar as subpastas.

## 🖥️ Executar localmente

```bash
pip install -r requirements.txt
# Instale o ffmpeg no seu sistema também (brew install ffmpeg / apt install ffmpeg)
streamlit run app.py
```

## 📝 Modelos Whisper

| Modelo | Velocidade | Precisão | VRAM |
|--------|-----------|---------|------|
| tiny   | ⚡⚡⚡⚡⚡ | ⭐⭐     | ~1GB |
| base   | ⚡⚡⚡⚡   | ⭐⭐⭐   | ~1GB |
| small  | ⚡⚡⚡     | ⭐⭐⭐⭐  | ~2GB |
| medium | ⚡⚡       | ⭐⭐⭐⭐⭐ | ~5GB |
| large  | ⚡         | ⭐⭐⭐⭐⭐ | ~10GB|

Para o Railway (sem GPU), recomenda-se **tiny** ou **base** para melhor desempenho.

## ⚙️ Variáveis de Ambiente

| Variável | Descrição |
|----------|-----------|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | JSON completo da Service Account do Google |
| `PORT` | Porta HTTP (definida automaticamente pelo Railway) |
