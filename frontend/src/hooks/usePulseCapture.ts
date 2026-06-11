import { useEffect, useRef } from 'react';
import WebSocketService from '../api/ws/websocketService';
import type { PulseSample } from '../api/interfaces/chat';

interface UsePulseCaptureOptions {
  localStream: MediaStream | null;
  enabled: boolean;
  /** Sampling rate (Hz). rPPG needs ≥15; 30 matches typical webcams. */
  fps?: number;
  /** How often (ms) to ship the accumulated samples to the backend. */
  batchMs?: number;
}

// Fixed forehead/cheek ROI as fractions of the frame (top-left x, y, w, h).
// Assumes a roughly centered face — good enough for a seated video call; a
// proper face-landmark ROI is the obvious upgrade. Keep in sync with the
// default in ml/scripts/test_pulse_estimator.py.
const ROI = { x: 0.35, y: 0.2, w: 0.3, h: 0.3 };

// Small analysis canvas — we only need a stable mean colour, not detail, and
// downscaling is cheap noise reduction.
const CANVAS_W = 160;
const CANVAS_H = 120;

/**
 * Contact-free pulse capture (videoplethysmography). While `enabled`, samples
 * the local camera at `fps`, computes the mean R,G,B over a face ROI per frame
 * (the rPPG "signal forming" step) and ships compact `(ts, r, g, b)` samples
 * over the meeting WebSocket as `pulse_samples`. The ML service runs the
 * frequency-domain estimation and the backend broadcasts `pulse_result`
 * (consumed by usePulseOverlay).
 *
 * Sending raw mean colours (not JPEG frames) sidesteps the compression and low
 * frame-rate of the translation stream, both of which destroy the ~1% colour
 * variation rPPG relies on.
 */
export const usePulseCapture = ({
  localStream,
  enabled,
  fps = 30,
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

    const rx = Math.floor(ROI.x * CANVAS_W);
    const ry = Math.floor(ROI.y * CANVAS_H);
    const rw = Math.floor(ROI.w * CANVAS_W);
    const rh = Math.floor(ROI.h * CANVAS_H);

    let cancelled = false;
    let buffer: PulseSample[] = [];
    const playPromise = video.play().catch(() => {
      /* autoplay can reject before the stream is ready; the interval retries */
    });

    const sample = () => {
      if (cancelled || !ctx || video.videoWidth === 0) return;
      ctx.drawImage(video, 0, 0, CANVAS_W, CANVAS_H);
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

    const sampleId = window.setInterval(sample, 1000 / fps);
    const flushId = window.setInterval(flush, batchMs);

    return () => {
      cancelled = true;
      window.clearInterval(sampleId);
      window.clearInterval(flushId);
      void playPromise;
      video.pause();
      video.srcObject = null;
    };
  }, [localStream, enabled, fps, batchMs]);
};

export default usePulseCapture;
