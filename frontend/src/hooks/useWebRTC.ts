import { useEffect, useRef, useState, useCallback } from 'react';
import WebSocketService from '../api/ws/websocketService';
import type { IWsMessage } from '../api/interfaces/chat';

interface PeerConnection {
  userId: string;
  connection: RTCPeerConnection;
  stream: MediaStream | null;
}

interface UseWebRTCOptions {
  meetingCode: string;
  token: string;
  userId: string;
}

interface UseWebRTCReturn {
  localStream: MediaStream | null;
  remoteStreams: Map<string, MediaStream>;
  peerNames: Map<string, string>;
  isMuted: boolean;
  isCameraOff: boolean;
  toggleMute: () => void;
  toggleCamera: () => void;
  startLocalStream: () => Promise<void>;
  stopLocalStream: () => void;
}

const ICE_SERVERS: RTCConfiguration = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
  ],
};

export const useWebRTC = ({ meetingCode, token, userId }: UseWebRTCOptions): UseWebRTCReturn => {
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [remoteStreams, setRemoteStreams] = useState<Map<string, MediaStream>>(new Map());
  const [peerNames, setPeerNames] = useState<Map<string, string>>(new Map());
  const [isMuted, setIsMuted] = useState(false);
  const [isCameraOff, setIsCameraOff] = useState(false);
  const peersRef = useRef<Map<string, PeerConnection>>(new Map());
  const localStreamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocketService | null>(null);

  const createPeerConnection = useCallback((targetUserId: string): RTCPeerConnection => {
    const pc = new RTCPeerConnection(ICE_SERVERS);

    pc.onicecandidate = (event) => {
      if (event.candidate) {
        wsRef.current?.sendSignaling('ice_candidate', targetUserId, event.candidate.toJSON());
      }
    };

    pc.ontrack = (event) => {
      const [stream] = event.streams;
      if (stream) {
        setRemoteStreams((prev) => {
          const next = new Map(prev);
          next.set(targetUserId, stream);
          return next;
        });
      }
    };

    pc.onconnectionstatechange = () => {
      if (pc.connectionState === 'disconnected' || pc.connectionState === 'failed') {
        removePeer(targetUserId);
      }
    };

    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => {
        pc.addTrack(track, localStreamRef.current!);
      });
    }

    peersRef.current.set(targetUserId, {
      userId: targetUserId,
      connection: pc,
      stream: null,
    });

    return pc;
  }, []);

  const removePeer = useCallback((targetUserId: string) => {
    const peer = peersRef.current.get(targetUserId);
    if (peer) {
      peer.connection.close();
      peersRef.current.delete(targetUserId);
      setRemoteStreams((prev) => {
        const next = new Map(prev);
        next.delete(targetUserId);
        return next;
      });
      setPeerNames((prev) => {
        const next = new Map(prev);
        next.delete(targetUserId);
        return next;
      });
    }
  }, []);

  const handleWsMessage = useCallback(async (message: IWsMessage) => {
    const payload = message.payload as Record<string, unknown>;

    switch (message.type) {
      case 'participant_joined': {
        const joinedUserId = payload.userId as string;
        if (joinedUserId === userId) return;

        setPeerNames((prev) => {
          const next = new Map(prev);
          next.set(joinedUserId, `${payload.firstName} ${payload.lastName}`);
          return next;
        });

        const pc = createPeerConnection(joinedUserId);
        const offer = await pc.createOffer();
        await pc.setLocalDescription(offer);
        wsRef.current?.sendSignaling('sdp_offer', joinedUserId, offer);
        break;
      }

      case 'sdp_offer': {
        const senderId = payload.senderId as string || message.senderId as string;
        if (!senderId) return;

        let pc = peersRef.current.get(senderId)?.connection;
        if (!pc) {
          pc = createPeerConnection(senderId);
        }
        await pc.setRemoteDescription(new RTCSessionDescription(payload.data as RTCSessionDescriptionInit));
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        wsRef.current?.sendSignaling('sdp_answer', senderId, answer);
        break;
      }

      case 'sdp_answer': {
        const senderId = payload.senderId as string || message.senderId as string;
        if (!senderId) return;
        const pc = peersRef.current.get(senderId)?.connection;
        if (pc) {
          await pc.setRemoteDescription(new RTCSessionDescription(payload.data as RTCSessionDescriptionInit));
        }
        break;
      }

      case 'ice_candidate': {
        const senderId = payload.senderId as string || message.senderId as string;
        if (!senderId) return;
        const pc = peersRef.current.get(senderId)?.connection;
        if (pc) {
          await pc.addIceCandidate(new RTCIceCandidate(payload.data as RTCIceCandidateInit));
        }
        break;
      }

      case 'participant_left': {
        const leftUserId = payload.userId as string;
        removePeer(leftUserId);
        break;
      }
    }
  }, [userId, createPeerConnection, removePeer]);

  useEffect(() => {
    const ws = WebSocketService.getInstance();
    wsRef.current = ws;

    if (meetingCode && token) {
      ws.connect(meetingCode, token);
      const unsubscribe = ws.on('all', handleWsMessage);

      return () => {
        unsubscribe();
        peersRef.current.forEach((peer) => peer.connection.close());
        peersRef.current.clear();
        setRemoteStreams(new Map());
      };
    }
  }, [meetingCode, token, handleWsMessage]);

  const startLocalStream = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: true,
        audio: true,
      });
      localStreamRef.current = stream;
      setLocalStream(stream);
    } catch (error) {
      console.error('Failed to get local stream:', error);
      throw error;
    }
  }, []);

  const stopLocalStream = useCallback(() => {
    if (localStreamRef.current) {
      localStreamRef.current.getTracks().forEach((track) => track.stop());
      localStreamRef.current = null;
      setLocalStream(null);
    }
  }, []);

  const toggleMute = useCallback(() => {
    if (localStreamRef.current) {
      const audioTrack = localStreamRef.current.getAudioTracks()[0];
      if (audioTrack) {
        audioTrack.enabled = !audioTrack.enabled;
        setIsMuted(!audioTrack.enabled);
      }
    }
  }, []);

  const toggleCamera = useCallback(() => {
    if (localStreamRef.current) {
      const videoTrack = localStreamRef.current.getVideoTracks()[0];
      if (videoTrack) {
        videoTrack.enabled = !videoTrack.enabled;
        setIsCameraOff(!videoTrack.enabled);
      }
    }
  }, []);

  useEffect(() => {
    return () => {
      stopLocalStream();
      const ws = WebSocketService.getInstance();
      ws.disconnect();
    };
  }, [stopLocalStream]);

  return {
    localStream,
    remoteStreams,
    peerNames,
    isMuted,
    isCameraOff,
    toggleMute,
    toggleCamera,
    startLocalStream,
    stopLocalStream,
  };
};
