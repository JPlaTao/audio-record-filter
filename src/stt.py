"""Speech-to-text module with pluggable providers.

Supports three backends:
  - faster-whisper (local GPU/CPU, default)
  - OpenAI-compatible API (openai-api)
  - DashScope / 阿里云灵积 (dashscope)

Configure via STT_PROVIDER env var or create_stt() factory.
"""

from __future__ import annotations

import logging
import os
import warnings
from abc import ABC, abstractmethod
from pathlib import Path

from .models import TranscribeResult

logger = logging.getLogger(__name__)

# ── Abstract Provider ──────────────────────────────────────────────────


class STTProvider(ABC):
    """Abstract base for speech-to-text providers."""

    @abstractmethod
    def transcribe(self, audio_path: str | Path, language: str = "zh") -> TranscribeResult:
        """Transcribe an audio file to text.

        Args:
            audio_path: Path to the audio file.
            language: Language code (e.g. "zh", "en", or None for auto-detect).

        Returns:
            TranscribeResult with full text and segments.
        """
        ...


# ═══════════════════════════════════════════════════════════════════════
# Provider 1: faster-whisper (local model, GPU/CUDA accelerated)
# ═══════════════════════════════════════════════════════════════════════


def _discover_nvidia_dlls() -> None:
    """Add NVIDIA DLL directories to PATH if they exist in the venv."""
    site_packages = Path(__file__).resolve().parent.parent / "venv" / "Lib" / "site-packages"
    if not site_packages.exists():
        return  # probably not running from a venv – defer to system PATH

    nvidia_dirs = list(site_packages.glob("nvidia/*/bin"))
    if not nvidia_dirs:
        return  # nvidia packages not installed

    paths_to_add = [str(d) for d in sorted(nvidia_dirs)]
    for p in paths_to_add:
        if p not in os.environ.get("PATH", ""):
            os.environ["PATH"] = f"{p}{os.pathsep}{os.environ['PATH']}"
            logger.debug("Added to PATH: %s", p)


_discover_nvidia_dlls()


class FasterWhisperProvider(STTProvider):
    """Wrapper around faster-whisper for local GPU/CPU transcription.

    Usage:
        engine = FasterWhisperProvider(model_size="large-v3")
        result = engine.transcribe("input/call.mp3")
    """

    KNOWN_SIZES = {"tiny", "base", "small", "medium", "large-v3"}

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "auto",
        compute_type: str = "auto",
    ) -> None:
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _resolve_model_path(self) -> str:
        """Resolve model_size to a local path if it exists in ./models/."""
        size = self.model_size

        if Path(size).exists() or size not in self.KNOWN_SIZES:
            return size

        local_path = Path(__file__).resolve().parent.parent / "models" / f"faster-whisper-{size}"
        if local_path.exists():
            logger.info("Using local model at %s", local_path)
            return str(local_path)

        hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
        if hf_cache.exists():
            snapshot_dir = hf_cache / f"models--Systran--faster-whisper-{size}" / "snapshots"
            if snapshot_dir.exists():
                snapshots = list(snapshot_dir.iterdir())
                if snapshots:
                    return str(snapshots[0])

        return size

    def _load_model(self):
        """Lazy-load the model so CLI help is fast."""
        if self._model is not None:
            return
        from faster_whisper import WhisperModel  # noqa: PLC0415

        model_path = self._resolve_model_path()
        logger.info(
            "Loading faster-whisper model (size=%s, device=%s, compute=%s)...",
            model_path,
            self.device,
            self.compute_type,
        )
        try:
            self._model = WhisperModel(
                model_path,
                device=self.device,
                compute_type=self.compute_type,
            )
        except Exception as exc:
            msg = str(exc).lower()
            if "connection" in msg or "connect" in msg or "eof" in msg or "ssl" in msg:
                raise RuntimeError(
                    f"模型下载失败！无法连接到 HuggingFace 下载 Whisper 模型。\n"
                    f"请尝试以下方法之一：\n"
                    f"  1. 运行 scripts/download_model.bat {self.model_size} 尝试下载\n"
                    f"  2. 手动从 https://hf-mirror.com/Systran/faster-whisper-{self.model_size} 下载后放入\n"
                    f"     models/faster-whisper-{self.model_size}/ 目录\n"
                    f"  3. 检查代理/VPN 配置后重试\n"
                    f"  4. 用小模型: --model tiny 或 --model base（耗时更短）"
                ) from exc
            raise

    def transcribe(self, audio_path: str | Path, language: str = "zh") -> TranscribeResult:
        """Transcribe a single audio file using local faster-whisper model."""
        self._load_model()
        path = Path(audio_path)

        logger.info("Transcribing %s ...", path.name)
        segments, info = self._model.transcribe(
            str(path),
            language=language,
            beam_size=5,
            vad_filter=True,
            vad_parameters=dict(min_silence_duration_ms=500),
        )

        segments_list = []
        full_text_parts: list[str] = []

        for seg in segments:
            segments_list.append({
                "start": seg.start,
                "end": seg.end,
                "text": seg.text.strip(),
            })
            full_text_parts.append(seg.text.strip())

        full_text = " ".join(full_text_parts)

        logger.info(
            "  → %s: %.1fs, %d chars, lang=%s (prob=%.2f)",
            path.name,
            info.duration or 0,
            len(full_text),
            info.language,
            info.language_probability,
        )

        return TranscribeResult(
            file=path.name,
            duration=info.duration or 0,
            text=full_text,
            segments=segments_list,
        )


# ═══════════════════════════════════════════════════════════════════════
# Provider 2: OpenAI-compatible Whisper API
# ═══════════════════════════════════════════════════════════════════════


class OpenAIAPIProvider(STTProvider):
    """Transcribe using OpenAI-compatible Whisper API.

    Uses the openai package (already a dependency).
    Compatible with any OpenAI-format endpoint (OpenAI, vLLM, etc.).
    """

    def __init__(
        self,
        api_key: str = "",
        base_url: str = "https://api.openai.com/v1",
        model: str = "whisper-1",
    ) -> None:
        if not api_key:
            raise ValueError(
                "OpenAI API key is required for OpenAIAPIProvider. "
                "Set STT_API_KEY env var or pass api_key."
            )
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model

    def _get_duration(self, path: Path) -> float:
        """Try to get audio duration via ffprobe, fall back to estimate."""
        import subprocess  # noqa: PLC0415

        try:
            result = subprocess.run(
                [
                    "ffprobe", "-v", "quiet",
                    "-show_entries", "format=duration",
                    "-of", "csv=p=0",
                    str(path),
                ],
                capture_output=True, text=True, timeout=15,
            )
            if result.returncode == 0 and result.stdout.strip():
                return float(result.stdout.strip())
        except Exception:
            pass
        return 0.0

    def transcribe(self, audio_path: str | Path, language: str = "zh") -> TranscribeResult:
        """Transcribe via OpenAI-compatible Whisper API."""
        from openai import OpenAI  # noqa: PLC0415

        path = Path(audio_path)
        logger.info("Transcribing %s via OpenAI API (model=%s) ...", path.name, self.model)

        client = OpenAI(api_key=self.api_key, base_url=self.base_url)

        with open(path, "rb") as f:
            kwargs = {
                "model": self.model,
                "file": f,
                "response_format": "verbose_json",
                "timestamp_granularities": ["segment"],
            }
            if language:
                kwargs["language"] = language

            response = client.audio.transcriptions.create(**kwargs)

        # Build segments from API response
        segments_list = []
        full_text_parts = []
        if hasattr(response, "segments") and response.segments:
            for seg in response.segments:
                text = (seg.text or "").strip()
                segments_list.append({
                    "start": getattr(seg, "start", 0),
                    "end": getattr(seg, "end", 0),
                    "text": text,
                })
                full_text_parts.append(text)

        full_text = response.text or " ".join(full_text_parts)

        duration = self._get_duration(path)

        logger.info("  → %s: %d chars (API)", path.name, len(full_text))

        return TranscribeResult(
            file=path.name,
            duration=duration,
            text=full_text.strip(),
            segments=segments_list,
        )


# ═══════════════════════════════════════════════════════════════════════
# Provider 3: DashScope / 阿里云灵积
# ═══════════════════════════════════════════════════════════════════════


class DashScopeProvider(STTProvider):
    """Transcribe using DashScope (阿里云灵积) ASR API.

    Uses paraformer models which are optimized for Chinese speech.
    For telephone audio (8kHz), use model="paraformer-8k-v2".
    """

    def __init__(
        self,
        api_key: str = "",
        model: str = "paraformer-v2",
    ) -> None:
        if not api_key:
            raise ValueError(
                "DashScope API key is required for DashScopeProvider. "
                "Set DASHSCOPE_API_KEY env var or pass api_key."
            )
        self.api_key = api_key
        self.model = model

    def transcribe(self, audio_path: str | Path, language: str = "zh") -> TranscribeResult:
        """Transcribe via DashScope ASR API."""
        try:
            import dashscope  # noqa: PLC0415
            from dashscope.audio.asr import Recognition  # noqa: PLC0415
        except ImportError:
            raise ImportError(
                "DashScope package not installed. Run: pip install dashscope"
            )

        path = Path(audio_path)
        logger.info("Transcribing %s via DashScope (model=%s) ...", path.name, self.model)

        dashscope.api_key = self.api_key

        recognition = Recognition(model=self.model)

        # Map language hint to sample rate
        # Chinese telephone audio is typically 8kHz, general audio 16kHz
        sample_rate = 8000 if "8k" in self.model else 16000

        result = recognition.call(
            audio_file=str(path),
            format=path.suffix.lstrip("."),
            sample_rate=sample_rate,
        )

        status = getattr(result, "get_status", lambda: "UNKNOWN")()
        if status != "SUCCEEDED":
            error_msg = getattr(result, "get_message", lambda: "unknown error")()
            raise RuntimeError(f"DashScope transcription failed: {status} - {error_msg}")

        # Extract full text
        full_text = getattr(result, "get_text", lambda: "")() or ""

        # Extract sentences with timestamps
        segments_list = []
        sentences = getattr(result, "get_sentence", lambda: [])()
        if sentences:
            for sent in sentences:
                text = getattr(sent, "text", str(sent)) or ""
                segments_list.append({
                    "start": getattr(sent, "begin_time", 0),
                    "end": getattr(sent, "end_time", 0),
                    "text": text.strip(),
                })
        else:
            segments_list.append({
                "start": 0,
                "end": 0,
                "text": full_text.strip(),
            })

        logger.info("  → %s: %d chars (DashScope)", path.name, len(full_text))

        return TranscribeResult(
            file=path.name,
            duration=0.0,
            text=full_text.strip(),
            segments=segments_list,
        )


# ═══════════════════════════════════════════════════════════════════════
# Factory
# ═══════════════════════════════════════════════════════════════════════


def create_stt(
    provider: str | None = None,
    model_size: str = "large-v3",
    device: str = "auto",
    api_key: str | None = None,
    api_base_url: str | None = None,
    api_model: str | None = None,
) -> STTProvider:
    """Create an STT provider based on configuration.

    Provider is selected in this order:
      1. ``provider`` argument
      2. ``STT_PROVIDER`` env var
      3. ``"faster-whisper"`` (default)

    Args:
        provider: ``"faster-whisper"``, ``"openai-api"``, or ``"dashscope"``.
        model_size: Whisper model size (faster-whisper only).
        device: ``"cuda"``, ``"cpu"``, or ``"auto"`` (faster-whisper only).
        api_key: API key (for openai-api or dashscope; falls back to env vars).
        api_base_url: Base URL for OpenAI-compatible API.
        api_model: Model name for API calls (whisper-1 / paraformer-v2 / …).

    Returns:
        An STTProvider instance.
    """
    provider = (provider or os.environ.get("STT_PROVIDER", "faster-whisper")).lower()

    if provider == "dashscope":
        return DashScopeProvider(
            api_key=api_key or os.environ.get("DASHSCOPE_API_KEY", ""),
            model=api_model or os.environ.get("STT_DASHSCOPE_MODEL", "paraformer-v2"),
        )

    if provider == "openai-api":
        return OpenAIAPIProvider(
            api_key=api_key or os.environ.get("STT_API_KEY", ""),
            base_url=api_base_url or os.environ.get("STT_API_BASE_URL", "https://api.openai.com/v1"),
            model=api_model or os.environ.get("STT_API_MODEL", "whisper-1"),
        )

    # Default: faster-whisper
    return FasterWhisperProvider(model_size=model_size, device=device)


# ── Backward compatibility alias ──────────────────────────────────────
# Old code imported STTEngine; keep the name so existing imports still work.

STTEngine = FasterWhisperProvider
