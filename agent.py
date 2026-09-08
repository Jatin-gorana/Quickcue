import asyncio
import json
import logging
import os
import sys
import threading
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

from aiohttp import web
from livekit.agents import JobContext, WorkerOptions, cli, llm, metrics
try:
    from livekit.agents.voice import AgentSession, Agent
except ImportError:
    from livekit.agents.pipeline import VoicePipelineAgent as AgentSession
    Agent = None

from livekit.api import AccessToken, VideoGrants, LiveKitAPI, CreateAgentDispatchRequest
from livekit.plugins import groq, rime, silero

# Load environment variables
load_dotenv()

# Configure verbose logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("quickcue-agent")

REQUIRED_ENVS = ["GROQ_API_KEY", "RIME_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
missing_envs = [var for var in REQUIRED_ENVS if not os.getenv(var)]
if missing_envs:
    logger.error(f"❌ Missing required environment variables: {', '.join(missing_envs)}. Check your .env file!")

LOG_FILE = "latency_log.jsonl"


class TurnLatencyTracker:
    def __init__(self, log_path: str = LOG_FILE):
        self.log_path = log_path
        self.current_turn = None
        self.turn_counter = 0

    def start_new_turn(self):
        self.turn_counter += 1
        now_ts = time.time()
        self.current_turn = {
            "turn_id": self.turn_counter,
            "iso_timestamp": datetime.now(timezone.utc).isoformat(),
            "user_stopped_speaking_ts": round(now_ts, 4),
            "stt_final_transcript_ts": None,
            "llm_first_token_ts": None,
            "llm_last_token_ts": None,
            "tts_first_byte_ts": None,
            "audio_playback_start_ts": None,
            "limitations_note": "audio_playback_start_ts estimated at agent audio emit start."
        }
        logger.info(f"⏱️ [Turn {self.turn_counter}] VAD detected User Stopped Speaking at {now_ts:.4f}")

    def record(self, key: str, ts: float = None):
        if self.current_turn is None:
            self.start_new_turn()
        if ts is None:
            ts = time.time()
        if self.current_turn.get(key) is None:
            self.current_turn[key] = round(ts, 4)
            logger.info(f"⏱️ [Turn {self.current_turn['turn_id']}] Recorded {key}: {self.current_turn[key]}")

    def finish_turn(self):
        if self.current_turn:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(self.current_turn) + "\n")
                logger.info(f"✅ [Turn {self.current_turn['turn_id']}] Saved latency entry to {self.log_path}")
            except Exception as e:
                logger.error(f"Failed to write latency record: {e}")
            self.current_turn = None


# CORS-enabled Token Server Handler with automatic Agent Dispatch
async def token_handler(request):
    cors_headers = {
        "Access-Control-Allow-Origin": "*",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
        "Access-Control-Allow-Headers": "*",
    }

    if request.method == "OPTIONS":
        return web.Response(status=204, headers=cors_headers)

    room_name = request.query.get("roomName", "quickcue-room")
    participant_name = request.query.get("participantName", "tech-user")

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")

    if not api_key or not api_secret:
        return web.json_response({"error": "LIVEKIT_API_KEY or LIVEKIT_API_SECRET missing in .env"}, status=500, headers=cors_headers)

    # Dispatch the Quickcue Agent worker to the room in LiveKit Cloud
    try:
        lk_api = LiveKitAPI(livekit_url, api_key, api_secret)
        await lk_api.agent_dispatch.create_dispatch(CreateAgentDispatchRequest(room=room_name))
        await lk_api.aclose()
        logger.info(f"📢 Created LiveKit Agent Dispatch for room '{room_name}'")
    except Exception as e:
        logger.warning(f"Agent dispatch notice: {e}")

    grant = VideoGrants(
        room_join=True,
        room=room_name,
        can_publish=True,
        can_subscribe=True,
    )
    token = AccessToken(api_key, api_secret).with_identity(participant_name).with_grants(grant).to_jwt()

    return web.json_response({
        "token": token,
        "url": livekit_url,
        "roomName": room_name,
    }, headers=cors_headers)


def run_token_server_in_background(port=8080):
    def _server():
        app = web.Application()
        app.router.add_route("GET", "/api/token", token_handler)
        app.router.add_route("OPTIONS", "/api/token", token_handler)
        logger.info(f"🌐 Background token server listening at http://localhost:{port}/api/token")
        try:
            web.run_app(app, port=port, handle_signals=False)
        except Exception as e:
            logger.warning(f"Token server background notice: {e}")

    t = threading.Thread(target=_server, daemon=True)
    t.start()


async def entrypoint(ctx: JobContext):
    logger.info(f"🔌 Connecting Quickcue Agent to LiveKit room: {ctx.room.name}")
    await ctx.connect()
    logger.info(f"✅ Connected Quickcue Agent to LiveKit room: {ctx.room.name}")

    system_prompt = (
        "You are Quickcue, a calm, concise hands-free lab and field copilot for technicians. "
        "Technicians speak to you while performing physical tasks with their hands occupied. "
        "Provide direct, factual, short spoken answers (1 to 3 sentences maximum). "
        "Avoid long intros, unnecessary filler, or markdown formatting since your text will be read aloud."
    )

    initial_ctx = llm.ChatContext()
    initial_ctx.add_message(
        role="system",
        content=system_prompt,
    )

    logger.info("⚙️ Initializing Groq STT (whisper-large-v3-turbo)...")
    stt_provider = groq.STT(model="whisper-large-v3-turbo")

    logger.info("⚙️ Initializing Groq LLM (groq/compound-mini)...")
    llm_provider = groq.LLM(model="groq/compound-mini")

    logger.info("⚙️ Initializing Rime TTS (mistv3, speaker=astra)...")
    tts_provider = rime.TTS(model="mistv3", speaker="astra")

    logger.info("⚙️ Loading Silero VAD...")
    vad_provider = silero.VAD.load()

    tracker = TurnLatencyTracker(LOG_FILE)

    if Agent is not None:
        agent_def = Agent(
            instructions=system_prompt,
            chat_ctx=initial_ctx,
            stt=stt_provider,
            llm=llm_provider,
            tts=tts_provider,
            vad=vad_provider,
        )
        session = AgentSession()
    else:
        agent_def = None
        session = AgentSession(
            vad=vad_provider,
            stt=stt_provider,
            llm=llm_provider,
            tts=tts_provider,
        )

    @session.on("user_started_speaking")
    def _on_user_started_speaking():
        logger.info("🎤 User started speaking into microphone...")

    @session.on("user_stopped_speaking")
    def _on_user_stopped_speaking():
        logger.info("🤫 User stopped speaking.")
        tracker.start_new_turn()

    @session.on("user_speech_committed")
    def _on_user_speech_committed(msg):
        text = getattr(msg, "content", getattr(msg, "text", str(msg)))
        logger.info(f"📝 STT Final Transcript (Groq Whisper): \"{text}\"")
        tracker.record("stt_final_transcript_ts")

    @session.on("agent_started_speaking")
    def _on_agent_started_speaking():
        logger.info("🔊 Agent started emitting spoken audio (Rime TTS)...")
        tracker.record("audio_playback_start_ts")

    @session.on("agent_stopped_speaking")
    def _on_agent_stopped_speaking():
        logger.info("🔇 Agent finished speaking response.")
        tracker.finish_turn()

    # Start the agent session properly WITH await!
    if agent_def is not None:
        await session.start(agent=agent_def, room=ctx.room)
    else:
        await session.start(room=ctx.room)

    logger.info("🚀 Quickcue Agent active in room. Saying greeting...")
    await session.say("Quickcue active. Ready for your field questions.", allow_interruptions=True)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "token-server":
        app = web.Application()
        app.router.add_route("GET", "/api/token", token_handler)
        app.router.add_route("OPTIONS", "/api/token", token_handler)
        web.run_app(app, port=8080)
    else:
        # Start background token server immediately so port 8080 is always up before room dispatch
        run_token_server_in_background(8080)
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
