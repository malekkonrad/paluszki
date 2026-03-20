import { useEffect, useRef, useState, useCallback } from 'react';
import WebSocketService from '../api/ws/websocketService';
import type { IWsMessage } from '../api/interfaces/chat';

interface UseDebugStreamReturn {
  debugStream: MediaStream | null;
  isDebugActive: boolean;
  toggleDebug: () => void;
}

const ICE_SERVERS: RTCConfiguration = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
  ],
};

export const useDebugStream = (meetingCode: string): UseDebugStreamReturn => {
  const [debugStream, setDebugStream] = useState<MediaStream | null>(null);
  const [isDebugActive, setIsDebugActive] = useState(false);
  const pcRef = useRef<RTCPeerConnection | null>(null);

  const handleDebugMessage = useCallback(async (message: IWsMessage) => {
    const payload = message.payload as Record<string, unknown>;

    switch (message.type) {
      case 'sdp_debug_offer': {
        if (!pcRef.current) {
          pcRef.current = new RTCPeerConnection(ICE_SERVERS);

          pcRef.current.ontrack = (event) => {
            const [stream] = event.streams;
            if (stream) {
              setDebugStream(stream);
            }
          };

          pcRef.current.onicecandidate = (event) => {
            if (event.candidate) {
              const ws = WebSocketService.getInstance();
              ws.sendDebugSignaling('ice_debug_candidate', event.candidate.toJSON());
            }
          };
        }

        await pcRef.current.setRemoteDescription(
          new RTCSessionDescription(payload.data as RTCSessionDescriptionInit)
        );
        const answer = await pcRef.current.createAnswer();
        await pcRef.current.setLocalDescription(answer);

        const ws = WebSocketService.getInstance();
        ws.sendDebugSignaling('sdp_debug_answer', answer);
        break;
      }

      case 'ice_debug_candidate': {
        if (pcRef.current) {
          await pcRef.current.addIceCandidate(
            new RTCIceCandidate(payload.data as RTCIceCandidateInit)
          );
        }
        break;
      }
    }
  }, []);

  useEffect(() => {
    if (!meetingCode) return;

    const ws = WebSocketService.getInstance();
    const unsubscribe = ws.on('all', handleDebugMessage);

    return () => {
      unsubscribe();
      if (pcRef.current) {
        pcRef.current.close();
        pcRef.current = null;
      }
      setDebugStream(null);
    };
  }, [meetingCode, handleDebugMessage]);

  const toggleDebug = useCallback(() => {
    const ws = WebSocketService.getInstance();
    const newState = !isDebugActive;
    ws.toggleDebugOverlay(newState);
    setIsDebugActive(newState);

    if (!newState && pcRef.current) {
      pcRef.current.close();
      pcRef.current = null;
      setDebugStream(null);
    }
  }, [isDebugActive]);

  return {
    debugStream,
    isDebugActive,
    toggleDebug,
  };
};
