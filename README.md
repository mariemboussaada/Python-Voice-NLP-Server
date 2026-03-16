# 🎙️ Voice Transcription & NLP Server

Python microservice for speech-to-text transcription and NLP analysis, designed for a **medical context** with context-aware patient query handling.

---

## 📋 Table of Contents

- [Features](#features)
- [Prerequisites](#prerequisites)
- [Project Structure](#project-structure)
- [Installation](#installation)
- [Vosk Models Setup](#vosk-models-setup)
- [Configuration](#configuration)
- [Running the Server](#running-the-server)
- [API Endpoints](#api-endpoints)
- [Notes](#notes)

---

## ✨ Features

- 🎤 Speech recognition using **Vosk**
- 🌍 Multilingual support: **French, English, Arabic, Tunisian**
- 🔄 Automatic translation to French
- 🧠 NLP intent detection
- 🏥 Context-aware medical queries
- 🌐 REST API using **Flask**
- 📋 Handles patient data, appointments, and prescriptions
- 🔊 Supports both audio and text input

---

## ⚙️ Prerequisites

Make sure the following tools are installed on your system **before** proceeding with the Python setup:

| Tool | Purpose | Install |
|------|---------|---------|
| Python 3.8+ | Runtime | [python.org](https://www.python.org/downloads/) |
| MongoDB | Database for patients and records | [mongodb.com](https://www.mongodb.com/try/download/community) |
| FFmpeg | Audio conversion to WAV format | [ffmpeg.org](https://ffmpeg.org/download.html) |

> ⚠️ MongoDB must be **running locally** before starting the server.

---

## 📁 Project Structure

```
Pf_speech_to_text/
├── app.py                  # Main Flask application
├── requirements.txt        # Python dependencies
├── model_fr/               # Vosk French model
├── model_en/               # Vosk English model
├── model_ar/               # Vosk Arabic model
├── model_tn/               # Vosk Tunisian model
└── ...
```

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone <your-repo-url>
cd <your-repo-folder>
```

### 2. Create a virtual environment

```bash
python -m venv venv
```

### 3. Activate the virtual environment

**Windows PowerShell:**
```powershell
.\venv\Scripts\Activate.ps1
```

**Windows CMD:**
```cmd
.\venv\Scripts\activate.bat
```

**Linux / macOS:**
```bash
source venv/bin/activate
```

### 4. Install dependencies

```bash
pip install -r requirements.txt
```

If `requirements.txt` is not present, install manually:

```bash
pip install flask vosk flask-cors pymongo spacy dateparser
```

---

## 🧩 Vosk Models Setup

The Vosk models are **not included** in this repository due to their size (~50MB+ each).  
Download them from: **[https://alphacephei.com/vosk/models](https://alphacephei.com/vosk/models)**

| Language | Model Name | Destination Folder |
|----------|-----------|-------------------|
| 🇫🇷 French | `vosk-model-small-fr-0.22` | `Pf_speech_to_text/model_fr/` |
| 🇬🇧 English | `vosk-model-small-en-us-0.22` | `Pf_speech_to_text/model_en/` |
| 🇸🇦 Arabic | appropriate arabic model | `Pf_speech_to_text/model_ar/` |
| 🇹🇳 Tunisian | appropriate tunisian model | `Pf_speech_to_text/model_tn/` |

After unzipping, each model folder should contain:

```
model_fr/
├── am/
│   └── final.mdl
├── conf/
├── graph/
├── ivector/
└── ...
```

> ✅ Vosk requires the `am/final.mdl` file and the subfolders (`conf`, `graph`, `ivector`, etc.) to load correctly.

---

## 🔧 Configuration

Make sure MongoDB is running locally. By default, the server connects to:

```
mongodb://localhost:27017/
```

If needed, update the MongoDB URI and database name directly in `app.py` or via environment variables (`.env` file support recommended for production).

---

## ▶️ Running the Server

```bash
python app.py
```

The server will start on:

```
http://localhost:8100
```

---

## 📡 API Endpoints

### `POST /transcribe`

Convert an audio file to text.

- **Input:** `.wav` audio file (multipart/form-data)
- **Output:** Transcribed text in JSON

```bash
curl -X POST http://localhost:8100/transcribe \
  -F "audio=@your_audio_file.wav"
```

**Response:**
```json
{
  "transcription": "bonjour je voudrais prendre un rendez-vous"
}
```

---

### `POST /analyze`

Analyze a medical query in text form.

- **Input:** JSON body with text
- **Output:** Detected intent and extracted entities

```bash
curl -X POST http://localhost:8100/analyze \
  -H "Content-Type: application/json" \
  -d '{"text": "je voudrais voir mes ordonnances"}'
```

**Response:**
```json
{
  "intent": "get_prescriptions",
  "entities": { ... }
}
```

---

### `POST /analyze/direct`

Directly transcribe and analyze an audio file in one step.

- **Input:** `.wav` audio file (multipart/form-data)
- **Output:** Transcription + intent analysis

```bash
curl -X POST http://localhost:8100/analyze/direct \
  -F "audio=@your_audio_file.wav"
```

**Response:**
```json
{
  "transcription": "...",
  "intent": "...",
  "entities": { ... }
}
```

---

## 🛠️ Technologies

| Technology | Role |
|-----------|------|
| Python 3.x | Core language |
| Flask | REST API framework |
| Vosk | Offline speech-to-text engine |
| MongoDB | Patient and records database |
| FFmpeg | Audio conversion and preprocessing |
| SpaCy | NLP processing |
| DateParser | Date extraction from text |

---

## 📝 Notes

- 📂 Audio input must be `.wav` format — FFmpeg handles conversion automatically.
- 🏥 The server detects unknown patients and can suggest creating a new record.
- 🌐 Tunisian/Arabic and English inputs are automatically translated to French before NLP analysis.
- 🔌 MongoDB must be running locally with patient data loaded before starting the server.
