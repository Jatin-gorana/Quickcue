# Quickcue — Hands-Free Voice Assistant for Field & Lab Technicians

> **DataForge x Rime Hackathon Submission**
> Quickcue is a voice-native, hands-free AI copilot built for field and lab technicians whose hands are occupied with physical tasks, protective gear, or delicate procedures.

---

## 🎯 Hard Voice Challenge & Core Solution

- **Selected Hard Voice Challenge:** *Perceived Response Time & Full-Duplex Interruption Recovery for Hands-Busy Work*
- **Primary Spoken Engine:** Rime AI Text-to-Speech (Model: `mistv3`, Speaker: `astra`)
- **Key Capabilities:**
  - Sub-second turn response delay (VAD -> STT -> LLM -> Rime TTS TTFB).
  - Full-duplex barge-in interruption recovery: Mid-speech interruption instantly truncates Rime audio playback within <150ms and cancels superseded LLM token generation.
  - Automated repeatable benchmark suite (`python benchmark.py`) exporting empirical latency metrics to `benchmark_report.json`.

---

## 🛠️ Architecture & Rime Integration Details

```
+------------------+         +------------------+         +------------------+
|  Lab Technician  | <=====> |   Vite React     | <=====> |  LiveKit Cloud   |
| (Microphone/Spkr)|  Audio  | Web Assistant UI | WebSock | Edge Transport   |
+------------------+         +------------------+         +--------+---------+
                                                                   |
                                                                   v
                                                          +------------------+
                                                          |  Quickcue Agent  |
                                                          |  (Python Worker) |
                                                          +--------+---------+
                                                                   |
                    +--------------------+-------------------------+--------------------+
                    |                    |                                              |
                    v                    v                                              v
           +-----------------+  +------------------+                          +-------------------+
           | Groq STT        |  | Groq LLM         |                          | Rime TTS          |
           | whisper-large-v3|  | groq/compound-mini|                          | mistv3 (astra)    |
           +-----------------+  +------------------+                          +-------------------+
```

### Exact Rime & Service Specifications:
- **Rime Model ID:** `mistv3`
- **Rime Speaker:** `astra`
- **Rime Language:** English (`en`)
- **Rime Audio Format:** PCM / Opus streaming over LiveKit WebRTC
- **Transport Layer:** LiveKit Cloud (Free Tier)
- **STT Engine:** Groq `whisper-large-v3-turbo`
- **LLM Engine:** Groq `groq/compound-mini`

---

## 📋 Environment Configuration Hygiene

Copy `.env.example` to `.env` and populate your credentials:

```bash
cp .env.example .env
```

```env
# LiveKit Cloud Transport
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your_livekit_api_key
LIVEKIT_API_SECRET=your_livekit_api_secret

# AI Service Credentials
GROQ_API_KEY=gsk_your_groq_api_key
RIME_API_KEY=your_rime_api_key
```

---

## 🚀 Quickstart & How to Run

### 1. Python Environment Setup
```powershell
# Create and activate virtual environment
python -m venv venv
.\venv\Scripts\Activate.ps1

# Install requirements
pip install -r requirements.txt
```

### 2. Launch Agent Worker
```powershell
python agent.py dev
```

### 3. Launch Frontend Web App
```powershell
cd frontend
npm install
npm run dev
```

Open **`http://localhost:3000`** in your browser, click **Start Voice Assistant**, and speak your lab/field questions hands-free!

---

## 🧪 Repeatable Benchmark Suite

To run the repeatable latency benchmark suite and verify performance metrics:

```powershell
python benchmark.py
```

This generates `benchmark_report.json` and logs turn-by-turn STT, LLM TTFT, Rime TTS TTFB, and overall turn latency.

---

## ⚠️ Failure Behavior & Known Limitations

1. **Client Audio Transducer Delay:** `audio_playback_start_ts` is measured when audio streaming begins from the agent. Browser WebAudio buffering and OS audio driver output may add minor hardware playback delay.
2. **Network Jitter:** Public WebSockets network conditions may introduce 20-80ms variance in latency depending on regional distance to LiveKit Cloud edge nodes.
3. **API Key Fallback:** If `RIME_API_KEY` or `GROQ_API_KEY` is missing, the backend logs a explicit error and returns an HTTP 500 status on token generation with details.
