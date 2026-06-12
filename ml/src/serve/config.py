"""Build a TranslationSession from a YAML config.

The config has four sections:

    classifier:        # which model + checkpoint
      config_path: configs/asl_citizen100.yaml
      checkpoint:  artifacts/asl_citizen100/best_model.pt
      label_map:   datasets/ASL_Citizen/subset100/label_map.json   # optional
      device:      cuda
      top_k:       5

    llm:               # forwarded to llm.registry.build_llm_client
      type: anthropic
      model: claude-haiku-4-5-20251001

    pipeline:          # segmenter / buffer / extractor knobs
      target_lang: en
      min_confidence: 0.5
      segmenter:
        motion_threshold: 0.02
        pause_frames: 9
        min_segment_frames: 12
        max_segment_frames: 90
      buffer:
        max_segments: 8
        flush_pause_ms: 1500
      extractor:       # optional; omit to disable raw-frame mode
        static_image_mode: false
        min_detection_confidence: 0.5
        min_tracking_confidence: 0.5
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from src.llm.registry import build_llm_client
from src.serve.buffer import TopKBuffer
from src.serve.classifier_runner import ClassifierRunner
from src.serve.live_keypoint_extractor import LiveKeypointExtractor
from src.serve.postprocessor import Postprocessor
from src.serve.segmenter import Segmenter
from src.serve.session import TranslationSession
from src.utils.config import load_config


def build_session_from_config(
    path: str,
    llm_override: Optional[Dict[str, Any]] = None,
    speaker_name: Optional[str] = None,
) -> TranslationSession:
    """Load ``serve.yaml`` and instantiate a :class:`TranslationSession`.

    ``llm_override`` (if provided) replaces the ``llm:`` section — handy
    for tests (``llm_override={"type": "mock"}``) and for swapping
    providers without touching the config file.

    ``speaker_name`` (if provided) is baked into the LLM prompt so the
    sentence can use the right grammatical gender for the signer.
    """
    cfg = load_config(path)

    cls_cfg = cfg["classifier"]
    classifier = ClassifierRunner(
        config_path=cls_cfg["config_path"],
        checkpoint_path=cls_cfg["checkpoint"],
        label_map_path=cls_cfg.get("label_map"),
        device=cls_cfg.get("device", "cuda"),
        top_k=int(cls_cfg.get("top_k", 5)),
    )

    pipe_cfg = cfg.get("pipeline", {})
    seg_cfg = pipe_cfg.get("segmenter", {})
    segmenter = Segmenter(
        motion_threshold=float(seg_cfg.get("motion_threshold", 0.02)),
        pause_frames=int(seg_cfg.get("pause_frames", 9)),
        min_segment_frames=int(seg_cfg.get("min_segment_frames", 12)),
        max_segment_frames=int(seg_cfg.get("max_segment_frames", 90)),
        velocity_smoothing=float(seg_cfg.get("velocity_smoothing", 0.5)),
    )

    buf_cfg = pipe_cfg.get("buffer", {})
    buffer = TopKBuffer(
        max_segments=int(buf_cfg.get("max_segments", 8)),
        flush_pause_ms=int(buf_cfg.get("flush_pause_ms", 15000)),
    )

    ext_cfg = pipe_cfg.get("extractor")
    extractor = None
    if ext_cfg is not None:
        extractor = LiveKeypointExtractor(
            static_image_mode=bool(ext_cfg.get("static_image_mode", False)),
            min_detection_confidence=float(ext_cfg.get("min_detection_confidence", 0.5)),
            min_tracking_confidence=float(ext_cfg.get("min_tracking_confidence", 0.5)),
        )

    target_lang = str(pipe_cfg.get("target_lang", "en"))

    llm_cfg = dict(cfg["llm"])
    if llm_override:
        llm_cfg = {**llm_cfg, **llm_override}
    llm = build_llm_client(llm_cfg)
    postprocessor = Postprocessor(llm, target_lang=target_lang, speaker_name=speaker_name)

    return TranslationSession(
        classifier=classifier,
        segmenter=segmenter,
        buffer=buffer,
        postprocessor=postprocessor,
        extractor=extractor,
        min_confidence=float(pipe_cfg.get("min_confidence", 0.5)),
        target_lang=target_lang,
    )
