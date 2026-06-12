import type { IWsMessage, WsMessageType } from '../interfaces/chat';

type MessageCallback = (message: IWsMessage) => void;

const WS_BASE_URL = process.env.NEXT_PUBLIC_WS_BASE_URL || 'ws://localhost:8000/ws';

class WebSocketService {
  private static instance: WebSocketService | null = null;
  private ws: WebSocket | null = null;
  private listeners: Map<string, MessageCallback[]> = new Map();
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;
  private reconnectDelay = 1000;
  private meetingCode: string | null = null;
  private token: string | null = null;

  private constructor() {}

  static getInstance(): WebSocketService {
    if (!WebSocketService.instance) {
      WebSocketService.instance = new WebSocketService();
    }
    return WebSocketService.instance;
  }

  connect(meetingCode: string, token: string): void {
    this.meetingCode = meetingCode;
    this.token = token;

    if (this.ws?.readyState === WebSocket.OPEN) {
      this.disconnect();
    }

    const url = `${WS_BASE_URL}/meetings/${meetingCode}?token=${token}`;
    this.ws = new WebSocket(url);

    this.ws.onopen = () => {
      console.log('[WS] Connected to meeting:', meetingCode);
      if (this.reconnectAttempts > 0) {
        this.notifyListeners({ type: 'ws_reconnected', payload: {} });
      }
      this.reconnectAttempts = 0;
    };

    this.ws.onmessage = (event) => {
      try {
        const message: IWsMessage = JSON.parse(event.data);
        this.notifyListeners(message);
      } catch (error) {
        console.error('[WS] Failed to parse message:', error);
      }
    };

    this.ws.onclose = (event) => {
      console.log('[WS] Connection closed:', event.code, event.reason);
      // 4008 = the same account connected from another tab/device and took
      // over this meeting session. Tell the UI instead of dying silently,
      // and don't reconnect (that would kick the new session in return).
      if (event.code === 4008) {
        this.notifyListeners({ type: 'session_takeover', payload: {} });
        return;
      }
      if (!event.wasClean) {
        if (this.reconnectAttempts < this.maxReconnectAttempts) {
          this.attemptReconnect();
        } else {
          this.notifyListeners({ type: 'ws_failed', payload: {} });
        }
      }
    };

    this.ws.onerror = (error) => {
      console.error('[WS] Error:', error);
    };
  }

  disconnect(): void {
    if (this.ws) {
      this.ws.close(1000, 'Client disconnect');
      this.ws = null;
    }
    this.reconnectAttempts = 0;
    this.meetingCode = null;
    this.token = null;
  }

  sendMessage(message: IWsMessage): void {
    if (this.ws?.readyState === WebSocket.OPEN) {
      this.ws.send(JSON.stringify(message));
    } else {
      console.warn('[WS] Cannot send message, connection not open');
    }
  }

  sendChat(content: string, senderName: string): void {
    this.sendMessage({
      type: 'chat_message',
      payload: { content, senderName },
    });
  }

  sendSignaling(type: 'sdp_offer' | 'sdp_answer' | 'ice_candidate', targetUserId: string, payload: RTCSessionDescriptionInit | RTCIceCandidateInit): void {
    this.sendMessage({
      type,
      payload: { targetUserId, data: payload },
    });
  }

  sendVideoFrame(frameB64: string, ts: number): void {
    this.sendMessage({
      type: 'video_frame',
      payload: { frameB64, ts },
    });
  }

  sendPulseSamples(samples: [number, number, number, number][]): void {
    this.sendMessage({
      type: 'pulse_samples',
      payload: { samples },
    });
  }

  on(type: WsMessageType | 'all', callback: MessageCallback): () => void {
    const key = type;
    if (!this.listeners.has(key)) {
      this.listeners.set(key, []);
    }
    this.listeners.get(key)!.push(callback);

    return () => {
      const callbacks = this.listeners.get(key);
      if (callbacks) {
        const index = callbacks.indexOf(callback);
        if (index > -1) callbacks.splice(index, 1);
      }
    };
  }

  private notifyListeners(message: IWsMessage): void {
    const typeListeners = this.listeners.get(message.type) || [];
    const allListeners = this.listeners.get('all') || [];
    [...typeListeners, ...allListeners].forEach((cb) => cb(message));
  }

  private attemptReconnect(): void {
    this.reconnectAttempts++;
    const delay = this.reconnectDelay * Math.pow(2, this.reconnectAttempts - 1);
    console.log(`[WS] Reconnecting in ${delay}ms (attempt ${this.reconnectAttempts}/${this.maxReconnectAttempts})`);
    this.notifyListeners({
      type: 'ws_reconnecting',
      payload: { attempt: this.reconnectAttempts, max: this.maxReconnectAttempts },
    });

    setTimeout(() => {
      if (this.meetingCode && this.token) {
        this.connect(this.meetingCode, this.token);
      }
    }, delay);
  }

  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export default WebSocketService;
