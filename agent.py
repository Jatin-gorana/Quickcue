import json
import logging
import os
import sys
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

from aiohttp import web
from livekit.agents import JobContext, WorkerOptions, cli, llm, metrics
from livekit.agents.pipeline import VoicePipelineAgent
from livekit.api import AccessToken, VideoGrants
from livekit.plugins import groq, rime, silero

# Load environment variables
load_dotenv()

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("quickcue-agent")

# Validate required credentials
REQUIRED_ENVS = ["GROQ_API_KEY", "RIME_API_KEY", "LIVEKIT_URL", "LIVEKIT_API_KEY", "LIVEKIT_API_SECRET"]
missing_envs = [var for var in REQUIRED_ENVS if not os.getenv(var)]
if missing_envs:
    logger.warning(f"Missing environment variables: {', '.join(missing_envs)}. Ensure these are populated in .env")

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
            "user_stopped_speaking_ts": now_ts,
            "stt_final_transcript_ts": None,
            "llm_first_token_ts": None,
            "llm_last_token_ts": None,
            "tts_first_byte_ts": None,
            "audio_playback_start_ts": None,
            "limitations_note": "audio_playback_start_ts is estimated when agent speech audio stream starts emitting; exact speaker playback timing requires client-side audio element events."
        }
        logger.info(f"[Turn {self.turn_counter}] User stopped speaking recorded at {now_ts:.4f}")

    def record(self, key: str, ts: float = None):
        if self.current_turn is None:
            self.start_new_turn()
        if ts is None:
            ts = time.time()
        if self.current_turn.get(key) is None:
            self.current_turn[key] = round(ts, 4)
            logger.info(f"[Turn {self.current_turn['turn_id']}] Recorded {key}: {self.current_turn[key]}")

    def finish_turn(self):
        if self.current_turn:
            try:
                with open(self.log_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(self.current_turn) + "\n")
                logger.info(f"[Turn {self.current_turn['turn_id']}] Saved latency record to {self.log_path}")
            except Exception as e:
                logger.error(f"Failed to write latency record: {e}")
            self.current_turn = None


async def entrypoint(ctx: JobContext):
    logger.info(f"Connecting agent to LiveKit room: {ctx.room.name}")
    await ctx.connect()

    # System prompt establishing assistant as a calm, concise lab/field copilot
    system_prompt = (
        "You are Quickcue, a calm, concise hands-free lab and field copilot for technicians. "
        "Technicians speak to you while performing physical tasks with their hands occupied. "
        "Provide direct, factual, short spoken answers (1 to 3 sentences maximum). "
        "Avoid long intros, unnecessary filler, or markdown formatting since your text will be read aloud."
    )

    initial_ctx = llm.ChatContext().append(
        role="system",
        text=system_prompt,
    )

    # Baseline pipeline in DEFAULT / NAIVE mode out of the box
    agent = VoicePipelineAgent(
        vad=silero.VAD.load(),
        stt=groq.STT(model="whisper-large-v3-turbo"),
        llm=groq.LLM(model="llama-3.3-70b-versatile"),
        tts=rime.TTS(model="mistv3", speaker="astra"),
        chat_ctx=initial_ctx,
    )

    tracker = TurnLatencyTracker(LOG_FILE)

    @agent.on("user_started_speaking")
    def _on_user_started_speaking():
        logger.info("User started speaking...")

    @agent.on("user_stopped_speaking")
    def _on_user_stopped_speaking():
        tracker.start_new_turn()

    @agent.on("user_speech_committed")
    def _on_user_speech_committed(msg):
        tracker.record("stt_final_transcript_ts")

    @agent.on("agent_started_speaking")
    def _on_agent_started_speaking():
        tracker.record("audio_playback_start_ts")

    @agent.on("agent_stopped_speaking")
    def _on_agent_stopped_speaking():
        tracker.finish_turn()

    @agent.on("metrics_collected")
    def _on_metrics_collected(mtrcs: metrics.AgentMetrics):
        metrics.log_metrics(mtrcs)
        now = time.time()
        if isinstance(mtrcs, metrics.LLMMetrics):
            if hasattr(mtrcs, "ttft") and mtrcs.ttft > 0:
                tracker.record("llm_first_token_ts", now - getattr(mtrcs, "duration", 0) + mtrcs.ttft)
            else:
                tracker.record("llm_first_token_ts", now)
            tracker.record("llm_last_token_ts", now)
        elif isinstance(mtrcs, metrics.TTSMetrics):
            if hasattr(mtrcs, "ttfb") and mtrcs.ttfb > 0:
                tracker.record("tts_first_byte_ts", now - getattr(mtrcs, "duration", 0) + mtrcs.ttfb)
            else:
                tracker.record("tts_first_byte_ts", now)

    agent.start(ctx.room)
    await agent.say("Quickcue active. Ready for your field questions.", allow_interruptions=True)


# Local Token Server for Browser Frontend Testing
async def token_handler(request):
    room_name = request.query.get("roomName", "quickcue-room")
    participant_name = request.query.get("participantName", "tech-user")

    api_key = os.getenv("LIVEKIT_API_KEY")
    api_secret = os.getenv("LIVEKIT_API_SECRET")
    livekit_url = os.getenv("LIVEKIT_URL")

    if not api_key or not api_secret:
        return web.json_response({"error": "LIVEKIT_API_KEY or LIVEKIT_API_SECRET not set"}, status=500)

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
    }, headers={"Access-Control-Allow-Origin": "*"})


def run_token_server(port=8080):
    app = web.Application()
    app.router.add_get("/api/token", token_handler)
    logger.info(f"Starting token helper server at http://localhost:{port}/api/token")
    web.run_app(app, port=port)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "token-server":
        run_token_server()
    else:
        cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint))
