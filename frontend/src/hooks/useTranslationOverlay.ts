import { useCallback, useEffect, useRef, useState } from 'react';
import WebSocketService from '../api/ws/websocketService';
import type { IWsMessage, IWsTranslationResult } from '../api/interfaces/chat';

export interface TranslationOverlayEntry {
  text: string;
  gestureLabel: string | null;
  confidence: number;
  ts: number;
}

export interface DetectionEntry {
  gestureLabel: string;
  confidence: number;
  accepted: boolean;
  ts: number;
}

/** How long (ms) a caption stays on screen after it arrives. */
const TTL_MS = 6000;
/** Detections are transient — they refresh with every recognized sign. */
const DETECTION_TTL_MS = 2500;
const SWEEP_MS = 500;

interface UseTranslationOverlayReturn {
  getTranslationFor: (userId: string) => TranslationOverlayEntry | null;
  getDetectionFor: (userId: string) => DetectionEntry | null;
}

/**
 * Listens for `translation_result` WS messages and keeps, per user:
 * - the latest finished sentence (caption under the tile, TTL_MS), and
 * - the latest single-sign detection with its confidence (live badge,
 *   DETECTION_TTL_MS) — sent by the backend per classified segment.
 */
export const useTranslationOverlay = (): UseTranslationOverlayReturn => {
  const [entries, setEntries] = useState<Map<string, TranslationOverlayEntry>>(new Map());
  const [detections, setDetections] = useState<Map<string, DetectionEntry>>(new Map());
  const entriesRef = useRef(entries);
  entriesRef.current = entries;
  const detectionsRef = useRef(detections);
  detectionsRef.current = detections;

  useEffect(() => {
    const ws = WebSocketService.getInstance();

    const unsubscribe = ws.on('translation_result', (msg: IWsMessage) => {
      const payload = msg.payload as IWsTranslationResult;
      if (!payload?.userId) return;
      if (payload.text) {
        setEntries((prev) => {
          const next = new Map(prev);
          next.set(payload.userId, {
            text: payload.text as string,
            gestureLabel: payload.gestureLabel ?? null,
            confidence: payload.confidence ?? 0,
            ts: Date.now(),
          });
          return next;
        });
      }
      if (payload.gestureLabel) {
        setDetections((prev) => {
          const next = new Map(prev);
          next.set(payload.userId, {
            gestureLabel: payload.gestureLabel as string,
            confidence: payload.confidence ?? 0,
            accepted: payload.gestureAccepted ?? true,
            ts: Date.now(),
          });
          return next;
        });
      }
    });

    const sweep = window.setInterval(() => {
      const now = Date.now();

      const current = entriesRef.current;
      const next = new Map(current);
      let changed = false;
      for (const [userId, entry] of current) {
        if (now - entry.ts > TTL_MS) {
          next.delete(userId);
          changed = true;
        }
      }
      if (changed) setEntries(next);

      const curDet = detectionsRef.current;
      const nextDet = new Map(curDet);
      let detChanged = false;
      for (const [userId, entry] of curDet) {
        if (now - entry.ts > DETECTION_TTL_MS) {
          nextDet.delete(userId);
          detChanged = true;
        }
      }
      if (detChanged) setDetections(nextDet);
    }, SWEEP_MS);

    return () => {
      unsubscribe();
      window.clearInterval(sweep);
    };
  }, []);

  const getTranslationFor = useCallback(
    (userId: string): TranslationOverlayEntry | null => entries.get(userId) ?? null,
    [entries],
  );

  const getDetectionFor = useCallback(
    (userId: string): DetectionEntry | null => detections.get(userId) ?? null,
    [detections],
  );

  return { getTranslationFor, getDetectionFor };
};

export default useTranslationOverlay;
