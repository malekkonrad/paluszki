import { useEffect, useRef } from 'react';
import WebSocketService from '../api/ws/websocketService';
import type { PulseSample } from '../api/interfaces/chat';
import {
  detectForeheadRoi,
  getFaceDetector,
  type NormalizedRoi,
} from '../lib/faceRoiDetector';
import type { FaceDetector } from '@mediapipe/tasks-vision';

interface UsePulseCaptureOptions {
  localStream: MediaStream | null;
  enabled: boolean;
  /** Colour sampling rate (Hz). rPPG needs ≥15; 30 matches typical webcams. */
  fps?: number;
  /** Face re-detection rate (Hz). The head moves slowly, so this can be far
   *  below `fps` — we reuse the last ROI for colour sampling in between. */
  detectFps?: number;
  /** How often (ms) to ship the accumulated samples to the backend. */
  batchMs?: number;
}

// Fallback ROI (fractions of the frame) used before the face detector loads or
// when no face is found — a central forehead/cheek box assuming a centered face.
const FALLBACK_ROI: NormalizedRoi = { x: 0.35, y: 0.2, w: 0.3, h: 0.3 };

// Small analysis canvas — we only need a stable mean colour, not detail, and
// downscaling is cheap noise reduction.
const CANVAS_W = 160;
const CANVAS_H = 120;

/**
 * Contact-free pulse capture (videoplethysmography). While `enabled`, tracks
 * the signer's forehead with a browser-side face detector and samples the mean
 * R,G,B over that ROI at `fps` (the rPPG "signal forming" step), shipping
 * compact `(ts, r, g, b)` samples over the meeting WebSocket as `pulse_samples`.
 * The ML service runs the frequency-domain estimation and the backend
 * broadcasts `pulse_result` (consumed by usePulseOverlay).
 *
 * Sending raw mean colours (not JPEG frames) sidesteps the compression and low
 * frame-rate of the translation stream, both of which destroy the ~1% colour
 * variation rPPG relies on.
 */
export const usePulseCapture = ({
  localStream,
  enabled,
  fps = 30,
  detectFps = 10,
  batchMs = 500,
}: UsePulseCaptureOptions): void => {
  useEffect(() => {
    if (!enabled || !localStream) return;

    const video = document.createElement('video');
    video.muted = true;
    video.playsInline = true;
    video.srcObject = localStream;

    const canvas = document.createElement('canvas');
    canvas.width = CANVAS_W;
    canvas.height = CANVAS_H;
    const ctx = canvas.getContext('2d', { willReadFrequently: true });

    let cancelled = false;
    let buffer: PulseSample[] = [];
    // Current ROI (fractions of the frame); updated by the detector, read by
    // the colour sampler. Starts at the fallback so we work before the model
    // loads and degrade gracefully if a face is never found.
    let roi: NormalizedRoi = FALLBACK_ROI;
    let detector: FaceDetector | null = null;

    const playPromise = video.play().catch(() => {
      /* autoplay can reject before the stream is ready; the intervals retry */
    });

    getFaceDetector()
      .then((d) => {
        if (!cancelled) detector = d;
      })
      .catch((err) => {
        console.warn('[pulse] face detector unavailable, using fixed ROI:', err);
      });

    const detect = () => {
      if (cancelled || !detector || video.videoWidth === 0) return;
      try {
        const found = detectForeheadRoi(detector, video, performance.now());
        if (found) roi = found;
      } catch {
        /* keep the last known ROI on a transient detection error */
      }
    };

    const sample = () => {
      if (cancelled || !ctx || video.videoWidth === 0) return;
      ctx.drawImage(video, 0, 0, CANVAS_W, CANVAS_H);
      const rx = Math.floor(roi.x * CANVAS_W);
      const ry = Math.floor(roi.y * CANVAS_H);
      const rw = Math.max(1, Math.floor(roi.w * CANVAS_W));
      const rh = Math.max(1, Math.floor(roi.h * CANVAS_H));
      const { data } = ctx.getImageData(rx, ry, rw, rh); // RGBA, row-major
      let r = 0;
      let g = 0;
      let b = 0;
      const px = data.length / 4;
      for (let i = 0; i < data.length; i += 4) {
        r += data[i];
        g += data[i + 1];
        b += data[i + 2];
      }
      buffer.push([performance.now() / 1000, r / px, g / px, b / px]);
    };

    const flush = () => {
      if (cancelled || buffer.length === 0) return;
      WebSocketService.getInstance().sendPulseSamples(buffer);
      buffer = [];
    };

    const detectId = window.setInterval(detect, 1000 / detectFps);
    const sampleId = window.setInterval(sample, 1000 / fps);
    const flushId = window.setInterval(flush, batchMs);

    return () => {
      cancelled = true;
      window.clearInterval(detectId);
      window.clearInterval(sampleId);
      window.clearInterval(flushId);
      void playPromise;
      video.pause();
      video.srcObject = null;
    };
  }, [localStream, enabled, fps, detectFps, batchMs]);
};

export default usePulseCapture;
