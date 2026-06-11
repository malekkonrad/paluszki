import { useCallback, useEffect, useRef, useState } from 'react';
import WebSocketService from '../api/ws/websocketService';
import type { IWsMessage, IWsPulseResult } from '../api/interfaces/chat';

export interface PulseOverlayEntry {
  bpm: number;
  confidence: number;
  ts: number;
}

/** How long (ms) a reading stays on screen after it arrives. */
const TTL_MS = 5000;
const SWEEP_MS = 500;

interface UsePulseOverlayReturn {
  getPulseFor: (userId: string) => PulseOverlayEntry | null;
}

/**
 * Listens for `pulse_result` WS messages and keeps the latest bpm per user,
 * expiring readings after TTL_MS. Keyed by userId so VideoGrid can show the
 * pulse badge on the matching tile.
 */
export const usePulseOverlay = (): UsePulseOverlayReturn => {
  const [entries, setEntries] = useState<Map<string, PulseOverlayEntry>>(new Map());
  const entriesRef = useRef(entries);
  entriesRef.current = entries;

  useEffect(() => {
    const ws = WebSocketService.getInstance();

    const unsubscribe = ws.on('pulse_result', (msg: IWsMessage) => {
      const payload = msg.payload as IWsPulseResult;
      if (!payload?.userId || payload.bpm == null) return;
      setEntries((prev) => {
        const next = new Map(prev);
        next.set(payload.userId, {
          bpm: payload.bpm as number,
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

  const getPulseFor = useCallback(
    (userId: string): PulseOverlayEntry | null => entries.get(userId) ?? null,
    [entries],
  );

  return { getPulseFor };
};

export default usePulseOverlay;
