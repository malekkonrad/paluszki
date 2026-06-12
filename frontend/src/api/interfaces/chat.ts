export interface IChatMessage {
  id: string;
  meetingCode: string;
  senderId: string;
  senderName: string;
  content: string;
  timestamp: string;
}

export type WsMessageType =
  | 'chat_message'
  | 'sdp_offer'
  | 'sdp_answer'
  | 'ice_candidate'
  | 'participant_joined'
  | 'participant_left'
  | 'participant_approved'
  | 'participant_rejected'
  | 'video_frame'
  | 'translation_result'
  | 'pulse_samples'
  | 'pulse_result'
  /** Synthetic, client-side only: this account opened the meeting elsewhere
   *  and the server kicked this socket (close code 4008). */
  | 'session_takeover'
  /** Synthetic, client-side only: connection-state notifications. */
  | 'ws_reconnecting'
  | 'ws_reconnected'
  | 'ws_failed';

export interface IWsMessage {
  type: WsMessageType;
  payload: unknown;
  senderId?: string;
  timestamp?: string;
}

export interface IWsSignalingMessage {
  type: 'sdp_offer' | 'sdp_answer' | 'ice_candidate';
  targetUserId: string;
  payload: RTCSessionDescriptionInit | RTCIceCandidateInit;
}

export interface IWsChatPayload {
  content: string;
  senderName: string;
}

export interface IWsParticipantEvent {
  userId: string;
  firstName: string;
  lastName: string;
  avatarUrl?: string;
}

export interface IWsVideoFramePayload {
  frameB64: string;
  ts: number;
}

export interface IWsTranslationResult {
  userId: string;
  text?: string | null;
  gestureLabel?: string | null;
  confidence: number;
  /** Whether the sign passed the pipeline's confidence threshold. */
  gestureAccepted?: boolean | null;
}

/** One ROI mean-color sample: [tsSeconds, meanR, meanG, meanB]. */
export type PulseSample = [number, number, number, number];

export interface IWsPulseSamplesPayload {
  samples: PulseSample[];
}

export interface IWsPulseResult {
  userId: string;
  bpm?: number | null;
  confidence: number;
}
