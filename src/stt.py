"""Speech-to-text module using faster-whisper."""

from __future__ import annotations

import logging
import os
import warnings
from pathlib import Path

from .models import TranscribeResult

logger = logging.getLogger(__name__)

# Suppress the FP16 warning on known-hardware combinations
warnings.filterwarnings("ignore", message=".*FP16 is not supported on CPU.*")

# ── Auto-discover NVIDIA CUDA libraries ──────────────────────────────
# The nvidia-cublas-cu12 pip package installs DLLs in the site-packages
# directory.  We add them to PATH here so ctranslate2 can find cuBLAS /
# cuRAND / cuDNN without the user installing the full CUDA Toolkit.

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


class STTEngine:
    """Wrapper around faster-whisper for transcribing audio files.

    Usage:
        engine = STTEngine(model_size="large-v3")
        result = engine.transcribe("input/call.mp3")
    """

    # Known model sizes for validation / auto-download hints
    KNOWN_SIZES = {"tiny", "base", "small", "medium", "large-v3"}

    def __init__(
        self,
        model_size: str = "large-v3",
        device: str = "auto",
        compute_type: str = "auto",
    ) -> None:
        """Initialize the Whisper model.

        Args:
            model_size: Whisper model size ("tiny", "base", "small",
                        "medium", "large-v3") OR a local directory path.
            device: "cuda", "cpu", or "auto".
            compute_type: "float16", "int8_float16", "auto", etc.
                          "auto" picks float16 on CUDA, int8 on CPU.
        """
        self.model_size = model_size
        self.device = device
        self.compute_type = compute_type
        self._model = None

    def _resolve_model_path(self) -> str:
        """Resolve model_size to a local path if it exists in ./models/."""
        size = self.model_size

        # If it's already a valid path or a known HuggingFace repo name, use as-is
        if Path(size).exists() or size not in self.KNOWN_SIZES:
            return size

        # Check local models/ directory
        local_path = Path(__file__).resolve().parent.parent / "models" / f"faster-whisper-{size}"
        if local_path.exists():
            logger.info("Using local model at %s", local_path)
            return str(local_path)

        # Check HuggingFace cache
        hf_cache = Path.home() / ".cache" / "huggingface" / "hub"
        if hf_cache.exists():
            # Snapshot folder pattern: models--Systran--faster-whisper-{size}
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
        """Transcribe a single audio file.

        Args:
            audio_path: Path to the audio file (MP3, WAV, etc.).
            language: Language code (e.g. "zh" for Chinese, "en" for English,
                      or None for auto-detect).

        Returns:
            TranscribeResult with full text and segments.
        """
        self._load_model()
        path = Path(audio_path)

        logger.info("Transcribing %s ...", path.name)
        segments, info = self._model.transcribe(
            str(path),
            language=language,
            beam_size=5,
            vad_filter=True,  # filter out non-speech
            vad_parameters=dict(
                min_silence_duration_ms=500,
            ),
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
