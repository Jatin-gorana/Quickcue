# Quickcue — Hands-Free Voice Assistant

Quickcue is a hands-free voice assistant tailored for field and lab technicians who require real-time spoken guidance while their hands are occupied with physical tasks.

This baseline implementation sets up a default voice pipeline using LiveKit Cloud, Groq STT/LLM, and Rime TTS, with built-in per-turn latency logging.

---

## 🛠️ Stack & Architecture

- **STT (Speech-to-Text):** Groq `whisper-large-v3-turbo` via `livekit-plugins-groq`
- **LLM (Language Model):** Groq `llama-3.3-70b-versatile` via `livekit-plugins-groq`
- **TTS (Text-to-Speech):** Rime `mistv3` (Speaker: `astra`) via `livekit-plugins-rime`
- **Transport:** LiveKit Cloud (Free Tier)
- **Frontend:** React + Vite + `@livekit/components-react`
- **Instrumentation:** Turn-level timestamp logging output to `latency_log.jsonl`

---

## 📋 Prerequisites & Key Acquisition

### 1. LiveKit Cloud Credentials
1. Sign up for a free account at [LiveKit Cloud](https://cloud.livekit.io/).
2. Create a new project.
3. In Project Settings -> Keys, generate an **API Key** and **API Secret**.
4. Copy your project's WebSockets URL (`wss://<your-project>.livekit.cloud`).

### 2. Groq API Key
1. Sign up at [Groq Console](https://console.groq.com/).
2. Create an API key (`gsk_...`).

### 3. Rime API Key
1. Sign up at [Rime AI](https://rime.ai/).
2. Create an API key under your Account settings.

---

## ⚙️ Project Setup

### 1. Configure Environment Variables
Copy `.env.example` to `.env` in the project root:

```bash
cp .env.example .env
```

Open `.env` and fill in your credential values:
```env
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

GROQ_API_KEY=gsk_your_groq_api_key
RIME_API_KEY=your_rime_api_key
```

### 2. Python Backend Setup

Create and activate a Python virtual environment, then install dependencies:

```bash
# Create virtual environment
python -m venv venv

# Activate on Windows (PowerShell)
.\venv\Scripts\Activate.ps1

# Install required packages
pip install -r requirements.txt
```

---

## 🚀 Running the Application

### Step 1: Start the Agent Worker
In your terminal with the Python environment active:

```bash
python agent.py dev
```

*(Optionally, in a separate terminal tab, run `python agent.py token-server` to launch the local browser token helper on port 8080).*

### Step 2: Start the React Frontend
In a new terminal window:

```bash
cd frontend
npm install
npm run dev
```

Open your browser at `http://localhost:3000`.

---

## 🧪 Testing the Voice Loop

1. Click **Connect to Voice Assistant** in the browser.
2. Grant microphone permissions when prompted.
3. Speak a question to Quickcue (e.g., *"What is the standard procedure for calibrating a pH meter?"*).
4. Quickcue will process your speech and reply aloud with a concise response while displaying the live transcript.

---

## 📊 Latency Instrumentation (`latency_log.jsonl`)

Each conversational turn is automatically instrumented and saved as a JSON line in `latency_log.jsonl`.

### Sample Log Format:
```json
{
  "turn_id": 1,
  "iso_timestamp": "2026-09-01T23:10:00.000000+00:00",
  "user_stopped_speaking_ts": 1725232200.1234,
  "stt_final_transcript_ts": 1725232200.4567,
  "llm_first_token_ts": 1725232200.7890,
  "llm_last_token_ts": 1725232201.1234,
  "tts_first_byte_ts": 1725232201.2500,
  "audio_playback_start_ts": 1725232201.3100,
  "limitations_note": "audio_playback_start_ts is estimated when agent speech audio stream starts emitting; exact speaker playback timing requires client-side audio element events."
}
```

### Timestamps Explained:
- `user_stopped_speaking_ts`: Timestamp when Voice Activity Detection (VAD) detected end of user speech.
- `stt_final_transcript_ts`: Timestamp when Groq Whisper final transcription was produced.
- `llm_first_token_ts`: Timestamp when Groq Llama 3.3 70B emitted its first token (Time-to-First-Token).
- `llm_last_token_ts`: Timestamp when Llama completed response generation.
- `tts_first_byte_ts`: Timestamp when Rime `mistv3` returned initial synthesized audio bytes.
- `audio_playback_start_ts`: Approximate timestamp when audio playback stream initiated for the client.
