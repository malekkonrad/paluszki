export type DebugOverlayType = 'hand_detection' | 'gesture_recognition' | 'full';

export interface IDebugStreamConfig {
  enabled: boolean;
  overlayType: DebugOverlayType;
}

export interface IDebugOverlayInfo {
  type: DebugOverlayType;
  detections: IDetection[];
  fps: number;
  timestamp: string;
}

export interface IDetection {
  label: string;
  confidence: number;
  boundingBox?: {
    x: number;
    y: number;
    width: number;
    height: number;
  };
  landmarks?: { x: number; y: number; z?: number }[];
}
