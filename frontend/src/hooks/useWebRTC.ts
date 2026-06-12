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
  /** Gate the WS connection until we're registered as a participant —
   *  the backend rejects sockets from non-participants (4003). */
  ready?: boolean;
}

interface UseWebRTCReturn {
  localStream: MediaStream | null;
  screenStream: MediaStream | null;
  isScreenSharing: boolean;
  remoteStreams: Map<string, MediaStream>;
  peerNames: Map<string, string>;
  /** Live RTCPeerConnection state per peer, for "reconnecting" badges. */
  peerStates: Map<string, RTCPeerConnectionState>;
  isMuted: boolean;
  isCameraOff: boolean;
  toggleMute: () => void;
  toggleCamera: () => void;
  startScreenShare: () => Promise<void>;
  stopScreenShare: () => void;
  startLocalStream: () => Promise<void>;
  stopLocalStream: () => void;
}

// Optional self-hosted TURN relay (coturn in docker-compose) — used when the
// direct P2P path can't traverse the NATs. Baked in at build time.
const TURN_HOST = process.env.NEXT_PUBLIC_TURN_HOST || '';
const TURN_USERNAME = process.env.NEXT_PUBLIC_TURN_USERNAME || 'paluszki';
const TURN_PASSWORD = process.env.NEXT_PUBLIC_TURN_PASSWORD || '';

const ICE_SERVERS: RTCConfiguration = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    ...(TURN_HOST && TURN_PASSWORD
      ? [
          {
            urls: [
              `turn:${TURN_HOST}:3478?transport=udp`,
              `turn:${TURN_HOST}:3478?transport=tcp`,
            ],
            username: TURN_USERNAME,
            credential: TURN_PASSWORD,
          },
        ]
      : []),
  ],
};

export const useWebRTC = ({ meetingCode, token, userId, ready = true }: UseWebRTCOptions): UseWebRTCReturn => {
  const [localStream, setLocalStream] = useState<MediaStream | null>(null);
  const [screenStream, setScreenStream] = useState<MediaStream | null>(null);
  const [remoteStreams, setRemoteStreams] = useState<Map<string, MediaStream>>(new Map());
  const [peerNames, setPeerNames] = useState<Map<string, string>>(new Map());
  const [peerStates, setPeerStates] = useState<Map<string, RTCPeerConnectionState>>(new Map());
  const [isMuted, setIsMuted] = useState(false);
  const [isCameraOff, setIsCameraOff] = useState(false);
  const peersRef = useRef<Map<string, PeerConnection>>(new Map());
  const localStreamRef = useRef<MediaStream | null>(null);
  const screenStreamRef = useRef<MediaStream | null>(null);
  const wsRef = useRef<WebSocketService | null>(null);
  // ICE candidates that arrived before the peer's remote description was set
  // (handlers are async, so a candidate can outrun setRemoteDescription).
  const pendingCandidatesRef = useRef<Map<string, RTCIceCandidateInit[]>>(new Map());
  // Perfect-negotiation state: true while we're producing an offer for a peer.
  // Offers can cross (glare) — e.g. our post-approval offer vs. the guest's
  // renegotiation after their camera starts — and without rollback handling
  // one side drops the other's offer, leaving one-directional video.
  const makingOfferRef = useRef<Map<string, boolean>>(new Map());

  // Deterministic role per peer pair: the "polite" side rolls back its own
  // offer on collision and answers; the "impolite" side ignores the incoming
  // offer (its own will be answered by the polite peer).
  const isPoliteWith = (peerId: string): boolean => Number(userId) < Number(peerId);

  const sendOffer = async (peerId: string, pc: RTCPeerConnection) => {
    makingOfferRef.current.set(peerId, true);
    try {
      const offer = await pc.createOffer();
      await pc.setLocalDescription(offer);
      wsRef.current?.sendSignaling('sdp_offer', peerId, offer);
    } finally {
      makingOfferRef.current.set(peerId, false);
    }
  };

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
      const state = pc.connectionState;
      setPeerStates((prev) => new Map(prev).set(targetUserId, state));

      if (state === 'failed') {
        // Auto-reconnect: restart ICE over the same connection (new
        // candidates, fresh paths). Crossing restart offers from both sides
        // are resolved by perfect negotiation. Only if the restart doesn't
        // recover do we tear the peer down.
        console.warn(`[WebRTC] connection to ${targetUserId} failed — restarting ICE`);
        try {
          pc.restartIce();
          void sendOffer(targetUserId, pc).catch((err) =>
            console.error('[WebRTC] ICE-restart offer failed', err),
          );
        } catch {
          removePeer(targetUserId);
          return;
        }
        window.setTimeout(() => {
          if (peersRef.current.get(targetUserId)?.connection === pc && pc.connectionState === 'failed') {
            console.error(`[WebRTC] ICE restart for ${targetUserId} did not recover — dropping peer`);
            removePeer(targetUserId);
          }
        }, 10000);
      } else if (state === 'closed') {
        removePeer(targetUserId);
      }
    };

    if (localStreamRef.current) {
      // While screen sharing, peers created mid-share must receive the screen
      // track in the video slot (the camera track is restored on share end).
      const activeScreenTrack = screenStreamRef.current?.getVideoTracks()[0] ?? null;
      localStreamRef.current.getTracks().forEach((track) => {
        if (track.kind === 'video' && activeScreenTrack) {
          pc.addTrack(activeScreenTrack, localStreamRef.current!);
        } else {
          pc.addTrack(track, localStreamRef.current!);
        }
      });
    }

    peersRef.current.set(targetUserId, {
      userId: targetUserId,
      connection: pc,
      stream: null,
    });

    return pc;
  }, []);

  const flushPendingCandidates = useCallback(async (targetUserId: string, pc: RTCPeerConnection) => {
    const pending = pendingCandidatesRef.current.get(targetUserId);
    if (!pending) return;
    pendingCandidatesRef.current.delete(targetUserId);
    for (const candidate of pending) {
      try {
        await pc.addIceCandidate(new RTCIceCandidate(candidate));
      } catch (err) {
        console.error('[WebRTC] flushing queued ICE candidate failed', err);
      }
    }
  }, []);

  const removePeer = useCallback((targetUserId: string) => {
    pendingCandidatesRef.current.delete(targetUserId);
    makingOfferRef.current.delete(targetUserId);
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
      setPeerStates((prev) => {
        const next = new Map(prev);
        next.delete(targetUserId);
        return next;
      });
    }
  }, []);

  const handleWsMessage = useCallback(async (message: IWsMessage) => {
    try {
      await handleSignalingMessage(message);
    } catch (err) {
      // Without this, a single failed negotiation step rejects silently and
      // the peer never connects with no trace in the console.
      console.error(`[WebRTC] handling ${message.type} failed`, err);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userId, createPeerConnection, removePeer, flushPendingCandidates]);

  const handleSignalingMessage = async (message: IWsMessage) => {
    const payload = message.payload as Record<string, unknown>;

    switch (message.type) {
      case 'participant_joined': {
        const joinedUserId = payload.userId as string;
        if (joinedUserId === userId) return;

        // Waiting guests are connected only to hear the approval — the server
        // re-broadcasts participant_joined(approved) once the host lets them
        // in, and that's when we open WebRTC towards them.
        const isWaitingGuest = payload.status === 'waiting';

        // A re-join (page refresh, second device takeover) means any previous
        // connection to this user is dead — start clean. (Also clears the
        // name, so record it after.)
        if (!isWaitingGuest) {
          removePeer(joinedUserId);
        }

        if (payload.firstName) {
          setPeerNames((prev) => {
            const next = new Map(prev);
            next.set(joinedUserId, `${payload.firstName} ${payload.lastName}`);
            return next;
          });
        }

        if (isWaitingGuest) return;

        const pc = createPeerConnection(joinedUserId);
        await sendOffer(joinedUserId, pc);
        break;
      }

      case 'sdp_offer': {
        const senderId = payload.senderId as string || message.senderId as string;
        if (!senderId) return;

        let pc = peersRef.current.get(senderId)?.connection;
        if (!pc) {
          pc = createPeerConnection(senderId);
        }

        // Perfect negotiation: offers can cross. The impolite side ignores
        // the incoming one (its own offer will be answered); the polite side
        // rolls its own back and answers.
        const offerCollision =
          makingOfferRef.current.get(senderId) === true || pc.signalingState !== 'stable';
        if (offerCollision) {
          if (!isPoliteWith(senderId)) {
            console.warn(`[WebRTC] offer collision with ${senderId} — ignoring (impolite)`);
            return;
          }
          await pc.setLocalDescription({ type: 'rollback' });
        }

        await pc.setRemoteDescription(new RTCSessionDescription(payload.data as RTCSessionDescriptionInit));
        await flushPendingCandidates(senderId, pc);
        const answer = await pc.createAnswer();
        await pc.setLocalDescription(answer);
        wsRef.current?.sendSignaling('sdp_answer', senderId, answer);
        break;
      }

      case 'sdp_answer': {
        const senderId = payload.senderId as string || message.senderId as string;
        if (!senderId) return;
        const pc = peersRef.current.get(senderId)?.connection;
        // An answer is only valid against our outstanding offer; anything
        // else is a stale leftover from a collision — applying it would throw
        // and (worse) wedge the connection.
        if (pc && pc.signalingState === 'have-local-offer') {
          await pc.setRemoteDescription(new RTCSessionDescription(payload.data as RTCSessionDescriptionInit));
          await flushPendingCandidates(senderId, pc);
        }
        break;
      }

      case 'ice_candidate': {
        const senderId = payload.senderId as string || message.senderId as string;
        if (!senderId) return;
        const pc = peersRef.current.get(senderId)?.connection;
        const candidate = payload.data as RTCIceCandidateInit;
        // Candidates can outrun the offer/answer (async handlers); adding one
        // before the remote description is set throws and the candidate is
        // lost for good — queue it instead.
        if (!pc || pc.remoteDescription === null) {
          const queue = pendingCandidatesRef.current.get(senderId) ?? [];
          queue.push(candidate);
          pendingCandidatesRef.current.set(senderId, queue);
          return;
        }
        try {
          await pc.addIceCandidate(new RTCIceCandidate(candidate));
        } catch (err) {
          // Candidates from an offer we deliberately ignored (collision)
          // don't match the active negotiation — safe to drop.
          console.warn('[WebRTC] dropped ICE candidate', err);
        }
        break;
      }

      case 'participant_left': {
        const leftUserId = payload.userId as string;
        removePeer(leftUserId);
        break;
      }
    }
  };

  // Connect as soon as we're in the meeting — independent of the camera.
  // The WS carries presence/approval/chat, which must work even if the
  // local camera is unavailable (e.g. a second browser on the same machine
  // can't grab the one webcam). Media tracks are attached separately, with
  // renegotiation once the local stream arrives (see effect below).
  //
  // Deliberately NOT keyed on the message handler: its identity changes when
  // the auth user resolves, and reconnecting then makes the server broadcast
  // participant_left/joined — everyone else briefly drops this user's tile.
  useEffect(() => {
    const ws = WebSocketService.getInstance();
    wsRef.current = ws;
    if (meetingCode && token && ready) {
      ws.connect(meetingCode, token);
    }
  }, [meetingCode, token, ready]);

  useEffect(() => {
    const ws = WebSocketService.getInstance();
    const unsubscribe = ws.on('all', handleWsMessage);
    return unsubscribe;
  }, [handleWsMessage]);

  // If the local stream becomes available after a peer connection was already
  // created (e.g. a guest whose camera resolved after the host's offer
  // arrived), attach our tracks to existing peers and renegotiate — otherwise
  // the remote never receives our video.
  useEffect(() => {
    if (!localStream) return;
    peersRef.current.forEach(async (peer, peerId) => {
      const pc = peer.connection;
      const senders = pc.getSenders();
      const missing = localStream
        .getTracks()
        .filter((track) => !senders.some((s) => s.track === track))
        // While sharing, the video slot intentionally carries the screen
        // track — don't add the camera as a second video track.
        .filter((track) => !(track.kind === 'video' && screenStreamRef.current));
      if (missing.length === 0) return;
      missing.forEach((track) => pc.addTrack(track, localStream));
      try {
        await sendOffer(peerId, pc);
      } catch (err) {
        // A collision here is fine: the tracks are already attached, so they
        // ride along in the answer we produce for the peer's crossing offer.
        console.warn('[WebRTC] renegotiation offer superseded', err);
      }
    });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [localStream]);

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

  const stopScreenShare = useCallback(() => {
    const stream = screenStreamRef.current;
    if (!stream) return;
    stream.getTracks().forEach((track) => track.stop());
    screenStreamRef.current = null;
    setScreenStream(null);
    // Put the camera back into every peer's video slot.
    const cameraTrack = localStreamRef.current?.getVideoTracks()[0] ?? null;
    peersRef.current.forEach((peer) => {
      const sender = peer.connection.getSenders().find((s) => s.track?.kind === 'video');
      if (sender) {
        sender.replaceTrack(cameraTrack).catch((err) => {
          console.error('[WebRTC] restoring camera after screen share failed', err);
        });
      }
    });
  }, []);

  const startScreenShare = useCallback(async () => {
    if (screenStreamRef.current) return;
    const stream = await navigator.mediaDevices.getDisplayMedia({ video: true });
    const screenTrack = stream.getVideoTracks()[0];
    if (!screenTrack) return;
    // Swap the outgoing video track in-place — same m-line, so no
    // renegotiation; remotes see the screen in this user's existing tile.
    peersRef.current.forEach((peer) => {
      const sender = peer.connection.getSenders().find((s) => s.track?.kind === 'video');
      if (sender) {
        sender.replaceTrack(screenTrack).catch((err) => {
          console.error('[WebRTC] switching to screen track failed', err);
        });
      }
    });
    // Browser's own "Stop sharing" bar ends the track — clean up then too.
    screenTrack.onended = () => stopScreenShare();
    screenStreamRef.current = stream;
    setScreenStream(stream);
  }, [stopScreenShare]);

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
      screenStreamRef.current?.getTracks().forEach((track) => track.stop());
      screenStreamRef.current = null;
      stopLocalStream();
      peersRef.current.forEach((peer) => peer.connection.close());
      peersRef.current.clear();
      pendingCandidatesRef.current.clear();
      setRemoteStreams(new Map());
      const ws = WebSocketService.getInstance();
      ws.disconnect();
    };
  }, [stopLocalStream]);

  return {
    localStream,
    screenStream,
    isScreenSharing: screenStream !== null,
    remoteStreams,
    peerNames,
    peerStates,
    isMuted,
    isCameraOff,
    toggleMute,
    toggleCamera,
    startScreenShare,
    stopScreenShare,
    startLocalStream,
    stopLocalStream,
  };
};
