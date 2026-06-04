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
  | 'sdp_debug_offer'
  | 'sdp_debug_answer'
  | 'ice_debug_candidate'
  | 'debug_overlay_toggle'
  | 'video_frame'
  | 'translation_result';

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

export interface IWsDebugSignalingMessage {
  type: 'sdp_debug_offer' | 'sdp_debug_answer' | 'ice_debug_candidate';
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
}
