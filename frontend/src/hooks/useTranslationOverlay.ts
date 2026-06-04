import { useCallback, useEffect, useRef, useState } from 'react';
import WebSocketService from '../api/ws/websocketService';
import type { IWsMessage, IWsTranslationResult } from '../api/interfaces/chat';

export interface TranslationOverlayEntry {
  text: string;
  gestureLabel: string | null;
  confidence: number;
  ts: number;
}

/** How long (ms) a caption stays on screen after it arrives. */
const TTL_MS = 6000;
const SWEEP_MS = 500;

interface UseTranslationOverlayReturn {
  getTranslationFor: (userId: string) => TranslationOverlayEntry | null;
}

/**
 * Listens for `translation_result` WS messages and keeps the latest caption
 * per user, expiring them after TTL_MS. Captions are keyed by the signer's
 * userId so VideoGrid can render them under the matching tile.
 */
export const useTranslationOverlay = (): UseTranslationOverlayReturn => {
  const [entries, setEntries] = useState<Map<string, TranslationOverlayEntry>>(new Map());
  const entriesRef = useRef(entries);
  entriesRef.current = entries;

  useEffect(() => {
    const ws = WebSocketService.getInstance();

    const unsubscribe = ws.on('translation_result', (msg: IWsMessage) => {
      const payload = msg.payload as IWsTranslationResult;
      if (!payload?.userId || !payload.text) return;
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
    });

    const sweep = window.setInterval(() => {
      const now = Date.now();
      const current = entriesRef.current;
      let changed = false;
      const next = new Map(current);
      for (const [userId, entry] of current) {
        if (now - entry.ts > TTL_MS) {
          next.delete(userId);
          changed = true;
        }
      }
      if (changed) setEntries(next);
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

  return { getTranslationFor };
};

export default useTranslationOverlay;
