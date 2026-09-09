import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from dotenv import load_dotenv

load_dotenv()

# Force UTF-8 encoding for stdout on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")

# Check credentials
REQUIRED_ENVS = ["GROQ_API_KEY", "RIME_API_KEY", "LIVEKIT_URL"]
missing = [v for v in REQUIRED_ENVS if not os.getenv(v)]
if missing:
    print(f"[ERROR] Missing required env variables for benchmark: {', '.join(missing)}")
    sys.exit(1)

from livekit.agents import llm, utils
from livekit.plugins import groq, rime, silero

TEST_FIXTURES = [
    "What buffer solutions do I need for pH probe calibration?",
    "If buffer solution 10 touches my skin, what is the safety protocol?",
    "What is the acceptable slope percentage range for a calibrated probe?",
]


async def run_benchmark():
    print("\n" + "=" * 65)
    print("QUICKCUE REPEATABLE VOICE PIPELINE BENCHMARK SUITE")
    print("Evaluating: Groq STT / Groq LLM (openai/gpt-oss-20b) / Rime TTS (mistv3:astra)")
    print("=" * 65 + "\n")

    async with utils.http_context.open():
        stt = groq.STT(model="whisper-large-v3-turbo")
        llm_model = groq.LLM(model="openai/gpt-oss-20b")
        tts_model = rime.TTS(model="mistv3", speaker="astra")
        vad_model = silero.VAD.load()

        results = []
        
        for idx, query in enumerate(TEST_FIXTURES, 1):
            print(f"[*] Running Benchmark Turn {idx}: \"{query}\"")
            
            # 1. Simulate LLM Generation & measure TTFT
            start_llm = time.time()
            ctx = llm.ChatContext()
            ctx.add_message(role="system", content="You are Quickcue, a calm, concise lab copilot. Give 1 short sentence.")
            ctx.add_message(role="user", content=query)
            
            stream = llm_model.chat(chat_ctx=ctx)
            first_token_ts = None
            full_text = ""
            
            async for chunk in stream:
                if first_token_ts is None:
                    first_token_ts = time.time()
                text_chunk = getattr(chunk.choices[0].delta, "content", "") if hasattr(chunk, "choices") and chunk.choices else ""
                if text_chunk:
                    full_text += text_chunk

            end_llm = time.time()
            llm_ttft_ms = round((first_token_ts - start_llm) * 1000, 2) if first_token_ts else 0.0
            llm_total_ms = round((end_llm - start_llm) * 1000, 2)
            
            print(f"    |- LLM TTFT: {llm_ttft_ms} ms | Total LLM Time: {llm_total_ms} ms")
            print(f"    |- Response Generated: \"{full_text.strip()}\"")

            # 2. Simulate Rime TTS Synthesis & measure TTFB
            start_tts = time.time()
            tts_stream = tts_model.synthesize(text=full_text or "Quickcue standing by.")
            first_byte_ts = None
            
            async for audio_frame in tts_stream:
                if first_byte_ts is None:
                    first_byte_ts = time.time()
                    break

            end_tts = time.time()
            tts_ttfb_ms = round((first_byte_ts - start_tts) * 1000, 2) if first_byte_ts else 0.0

            print(f"    |- Rime TTS TTFB: {tts_ttfb_ms} ms")
            
            # Estimated total turn-to-speech delay (STT estimate ~ 200ms + LLM TTFT + TTS TTFB)
            estimated_stt_ms = 200.0
            total_turn_delay_ms = round(estimated_stt_ms + llm_ttft_ms + tts_ttfb_ms, 2)
            print(f"    \\- Estimated Total Turn Latency: {total_turn_delay_ms} ms\n")

            results.append({
                "turn_id": idx,
                "query": query,
                "response": full_text.strip(),
                "stt_estimated_ms": estimated_stt_ms,
                "llm_ttft_ms": llm_ttft_ms,
                "llm_total_ms": llm_total_ms,
                "rime_tts_ttfb_ms": tts_ttfb_ms,
                "total_turn_latency_ms": total_turn_delay_ms,
            })

    # Summary Statistics
    avg_ttft = round(sum(r["llm_ttft_ms"] for r in results) / len(results), 2)
    avg_ttfb = round(sum(r["rime_tts_ttfb_ms"] for r in results) / len(results), 2)
    avg_total = round(sum(r["total_turn_latency_ms"] for r in results) / len(results), 2)

    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "provider_config": {
            "stt": "groq/whisper-large-v3-turbo",
            "llm": "groq/openai/gpt-oss-20b",
            "tts": "rime/mistv3 (speaker: astra)",
            "vad": "silero/vad"
        },
        "averages": {
            "avg_llm_ttft_ms": avg_ttft,
            "avg_rime_tts_ttfb_ms": avg_ttfb,
            "avg_total_turn_latency_ms": avg_total
        },
        "turn_details": results
    }

    report_file = "benchmark_report.json"
    with open(report_file, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    print("=" * 65)
    print("BENCHMARK SUMMARY RESULTS")
    print(f"  Average LLM TTFT:       {avg_ttft} ms")
    print(f"  Average Rime TTS TTFB:  {avg_ttfb} ms")
    print(f"  Average Total Latency:  {avg_total} ms")
    print(f"[OK] Full report saved to: {report_file}")
    print("=" * 65 + "\n")


if __name__ == "__main__":
    asyncio.run(run_benchmark())
