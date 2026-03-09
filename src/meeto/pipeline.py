"""Pipeline orchestrator that wires adapters to a raw MeetSession."""

import asyncio
import base64
import logging
from dataclasses import dataclass
from typing import Optional

from meeto.audio_writer import AudioDumpWriter
from meeto.config.models import AudioConfig, SttConfig
from meeto.meet.joiner import MeetSession
from meeto.meet.speaker_attribution import SpeakerAttributionAdapter, create_speaker_attribution
from meeto.storage import ArtifactStorageAdapter, LocalStorageAdapter
from meeto.stt.base import STTStreamingAdapter
from meeto.stt.factory import create_stt_adapter
from meeto.transcript_writer import TranscriptWriter

_logger = logging.getLogger(__name__)


async def _connect_stt_with_retries(
    stt_adapter: STTStreamingAdapter,
    *,
    provider: str,
    retries: int,
    initial_delay_s: float,
    max_delay_s: float,
) -> None:
    for attempt in range(1, retries + 1):
        try:
            await stt_adapter.connect()
            return
        except Exception as err:
            if attempt >= retries:
                raise
            delay_s = min(max_delay_s, initial_delay_s * (2 ** (attempt - 1)))
            _logger.warning(
                "GMEET: STT connect failed provider=%s attempt=%s/%s retry_in=%.2fs err=%s",
                provider,
                attempt,
                retries,
                delay_s,
                err,
            )
            await asyncio.sleep(delay_s)


def _audio_capture_script(sample_rate: int, chunk_ms: int, debug: bool) -> str:
    return f"""
(() => {{
  if (window.__gmeetAudioCaptureRunning) return;
  window.__gmeetAudioCaptureRunning = true;
  window.__gmeetAudioCaptureStopped = false;

  const targetSampleRate = {sample_rate};
  const chunkMs = {chunk_ms};
  const chunkFrames = Math.max(1, Math.floor(targetSampleRate * chunkMs / 1000));

  const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
  const sources = new Map();
  const processor = audioCtx.createScriptProcessor(4096, 1, 1);
  const intervalIds = [];
  let sampleBuffer = [];
  let lastDebugTs = 0;
  const debugEnabled = {str(debug).lower()};

  function downsampleBuffer(buffer, inRate, outRate) {{
    if (outRate === inRate) {{
      return buffer;
    }}
    const ratio = inRate / outRate;
    const newLength = Math.floor(buffer.length / ratio);
    const result = new Float32Array(newLength);
    for (let i = 0; i < newLength; i++) {{
      const start = Math.floor(i * ratio);
      const end = Math.floor((i + 1) * ratio);
      let sum = 0;
      let count = 0;
      for (let j = start; j < end && j < buffer.length; j++) {{
        sum += buffer[j];
        count++;
      }}
      result[i] = count ? sum / count : 0;
    }}
    return result;
  }}

  function floatTo16BitPCM(float32) {{
    const output = new Int16Array(float32.length);
    for (let i = 0; i < float32.length; i++) {{
      let s = Math.max(-1, Math.min(1, float32[i]));
      output[i] = s < 0 ? s * 0x8000 : s * 0x7fff;
    }}
    return output;
  }}

  function base64FromBytes(bytes) {{
    let binary = "";
    const len = bytes.length;
    for (let i = 0; i < len; i++) {{
      binary += String.fromCharCode(bytes[i]);
    }}
    return btoa(binary);
  }}

  function emitSamples(int16Samples, floatSamples) {{
    if (window.__gmeetAudioCaptureStopped) return;
    for (let i = 0; i < int16Samples.length; i++) {{
      sampleBuffer.push(int16Samples[i]);
    }}
    while (sampleBuffer.length >= chunkFrames) {{
      const chunk = sampleBuffer.splice(0, chunkFrames);
      const pcm = new Int16Array(chunk);
      const bytes = new Uint8Array(pcm.buffer);
      const b64 = base64FromBytes(bytes);
      try {{
        window.onAudioChunk({{ pcm16_b64: b64, sample_rate: targetSampleRate }});
      }} catch (_err) {{
        // Ignore callback errors during shutdown races.
      }}
    }}

    if (debugEnabled) {{
      const now = Date.now();
      if (now - lastDebugTs >= 1000) {{
        lastDebugTs = now;
        let sumSquares = 0;
        let peak = 0;
        let floatPeak = 0;
        for (let i = 0; i < int16Samples.length; i++) {{
          const v = int16Samples[i];
          const abs = Math.abs(v);
          if (abs > peak) peak = abs;
          sumSquares += v * v;
        }}
        for (let i = 0; i < floatSamples.length; i++) {{
          const abs = Math.abs(floatSamples[i]);
          if (abs > floatPeak) floatPeak = abs;
        }}
        const rms = Math.sqrt(sumSquares / Math.max(1, int16Samples.length));
        window.onAudioDebug({{
          event: "rms",
          rms,
          peak,
          float_peak: floatPeak,
          audio_elements: document.querySelectorAll("audio").length,
          audio_state: audioCtx.state,
        }});
      }}
    }}
  }}

  processor.onaudioprocess = (event) => {{
    if (window.__gmeetAudioCaptureStopped) return;
    const input = event.inputBuffer.getChannelData(0);
    const downsampled = downsampleBuffer(input, audioCtx.sampleRate, targetSampleRate);
    const pcm16 = floatTo16BitPCM(downsampled);
    emitSamples(pcm16, downsampled);
    const output = event.outputBuffer.getChannelData(0);
    output.fill(0);
  }};

  processor.connect(audioCtx.destination);

  function attachAudio(el) {{
    if (sources.has(el)) return;
    try {{
      const source = el.srcObject
        ? audioCtx.createMediaStreamSource(el.srcObject)
        : audioCtx.createMediaElementSource(el);
      source.connect(processor);
      sources.set(el, source);
    }} catch (err) {{
      console.debug("GMeet audio attach failed", err);
    }}
  }}

  function scan() {{
    document.querySelectorAll("audio").forEach(attachAudio);
    if (debugEnabled) {{
      const details = Array.from(document.querySelectorAll("audio")).map((el) => {{
        const srcObject = el.srcObject;
        const tracks = srcObject && srcObject.getAudioTracks ? srcObject.getAudioTracks() : [];
        return {{
          muted: el.muted,
          volume: el.volume,
          paused: el.paused,
          track_count: tracks.length,
          track_state: tracks.map((t) => t.readyState || "unknown"),
          track_enabled: tracks.map((t) => t.enabled),
        }};
      }});
      window.onAudioDebug({{
        event: "scan",
        audio_elements: document.querySelectorAll("audio").length,
        audio_state: audioCtx.state,
        elements: details,
      }});
    }}
  }}

  scan();
  intervalIds.push(setInterval(scan, 2000));
  function ensureRunning() {{
    if (audioCtx.state !== "running") {{
      audioCtx.resume().catch(() => {{}});
    }}
  }}

  ensureRunning();
  intervalIds.push(setInterval(ensureRunning, 2000));

  window.__gmeetStopAudioCapture = async () => {{
    if (window.__gmeetAudioCaptureStopped) return true;
    window.__gmeetAudioCaptureStopped = true;
    window.__gmeetAudioCaptureRunning = false;

    for (const id of intervalIds) {{
      clearInterval(id);
    }}

    try {{
      processor.onaudioprocess = null;
      processor.disconnect();
    }} catch (_err) {{}}

    try {{
      for (const source of sources.values()) {{
        source.disconnect();
      }}
      sources.clear();
    }} catch (_err) {{}}

    try {{
      await audioCtx.close();
    }} catch (_err) {{}}

    return true;
  }};
}})();
"""


@dataclass
class PipelineSession:
    page: Optional[object] = None
    audio_writer: Optional[AudioDumpWriter] = None
    stt_adapter: Optional[STTStreamingAdapter] = None
    speaker_attribution: Optional[SpeakerAttributionAdapter] = None
    transcript_writer: Optional[TranscriptWriter] = None

    async def close(self) -> dict:
        close_result = {"audio": None, "transcript": None}
        if self.page:
            try:
                await self.page.evaluate(
                    "(async () => { if (window.__gmeetStopAudioCapture) await window.__gmeetStopAudioCapture(); })()"
                )
            except Exception as err:
                _logger.debug("GMEET: audio capture teardown skipped err=%s", err)
        if self.speaker_attribution:
            self.speaker_attribution.stop()
        if self.stt_adapter:
            await self.stt_adapter.close()
        if self.audio_writer:
            result = self.audio_writer.close()
            close_result["audio"] = result
            _logger.info(
                "GMEET: audio dump closed local=%s remote=%s bytes=%s duration=%.2fs",
                result.get("local_path"),
                result.get("remote_path"),
                result.get("bytes_written"),
                result.get("duration_seconds", 0),
            )
        if self.transcript_writer:
            close_result["transcript"] = self.transcript_writer.close()
        return close_result


async def setup_pipeline(
    session: MeetSession,
    *,
    meeting_id: str,
    audio: AudioConfig = None,
    stt: SttConfig = None,
    storage_adapter: Optional[ArtifactStorageAdapter] = None,
    stt_adapter: Optional[STTStreamingAdapter] = None,
) -> PipelineSession:
    if audio is None:
        audio = AudioConfig()
    if stt is None:
        stt = SttConfig()
    if storage_adapter is None:
        storage_adapter = LocalStorageAdapter()

    page = session.page
    audio_writer = None
    speaker_attribution = None
    transcript_writer = None

    if audio.dump_enabled:
        try:
            audio_writer = AudioDumpWriter(
                meeting_id=meeting_id,
                sample_rate=audio.sample_rate,
                channels=1,
                storage_adapter=storage_adapter,
            )
            audio_writer.open()
            _logger.info("GMEET: audio dump writer initialized")
        except Exception:
            _logger.exception("GMEET: failed to initialize audio dump writer")
            audio_writer = None

    if stt_adapter or stt.provider:
        try:
            speaker_attribution = create_speaker_attribution(stt.diarization, page=page)
            await speaker_attribution.start()
        except Exception:
            _logger.exception("GMEET: failed to start speaker attribution (%s)", stt.diarization)
            speaker_attribution = None

        try:
            transcript_writer = TranscriptWriter(
                meeting_id=meeting_id,
                sample_rate=audio.sample_rate,
                stt_provider=stt.provider,
                storage_adapter=storage_adapter,
            )
            transcript_writer.open()
        except Exception:
            _logger.exception("GMEET: failed to start transcript writer")
            transcript_writer = None

        try:
            if stt_adapter is None:
                adapter_kwargs = dict(stt.extra)
                adapter_kwargs.setdefault("sample_rate", audio.sample_rate)
                if stt.api_key:
                    adapter_kwargs.setdefault("api_key", stt.api_key)
                stt_adapter = create_stt_adapter(stt.provider, **adapter_kwargs)
            await _connect_stt_with_retries(
                stt_adapter,
                provider=stt.provider,
                retries=max(1, stt.connect_retries),
                initial_delay_s=max(0.1, stt.connect_initial_delay_s),
                max_delay_s=max(0.1, stt.connect_max_delay_s),
            )

            async def on_segment(segment):
                speaker_name = speaker_attribution.get_speaker_for_segment(segment) if speaker_attribution else None
                _logger.info(
                    "GMEET: stt segment seq=%s final=%s speaker=%s diarized=%s text=%s",
                    segment.seq,
                    segment.is_final,
                    speaker_name,
                    segment.speaker,
                    segment.text,
                )
                if transcript_writer:
                    transcript_writer.write_segment(segment, speaker_name=speaker_name)

            await stt_adapter.start(on_segment)
        except Exception:
            _logger.exception("GMEET: failed to start STT (%s)", stt.provider)
            stt_adapter = None

    if audio_writer or stt_adapter:
        try:

            async def handle_audio_chunk(source, payload):
                if not payload:
                    return
                if isinstance(payload, dict) and "pcm16_b64" in payload:
                    try:
                        decoded = base64.b64decode(payload["pcm16_b64"])
                    except Exception:
                        _logger.exception("GMEET: failed to decode audio chunk")
                        return
                    if audio_writer:
                        audio_writer.write_chunk(decoded)
                    if stt_adapter:
                        await stt_adapter.send_audio(decoded)

            async def handle_audio_debug(source, payload):
                if not payload:
                    return
                if isinstance(payload, dict):
                    _logger.info("GMEET: audio debug %s", payload)

            await page.expose_binding("onAudioChunk", handle_audio_chunk)
            if audio.debug:
                await page.expose_binding("onAudioDebug", handle_audio_debug)
            await page.evaluate(_audio_capture_script(audio.sample_rate, audio.chunk_ms, audio.debug))
            _logger.info("GMEET: audio capture initialized")
        except Exception:
            _logger.exception("GMEET: failed to start audio capture")

    return PipelineSession(
        page=page,
        audio_writer=audio_writer,
        stt_adapter=stt_adapter,
        speaker_attribution=speaker_attribution,
        transcript_writer=transcript_writer,
    )
