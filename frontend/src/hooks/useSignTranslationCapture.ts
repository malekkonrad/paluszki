import { useEffect, useRef } from 'react';
import WebSocketService from '../api/ws/websocketService';

interface UseSignTranslationCaptureOptions {
  localStream: MediaStream | null;
  enabled: boolean;
  /** Frames per second to sample and send. */
  fps?: number;
  /** Capture resolution sent to the backend (MediaPipe-friendly, small). */
  width?: number;
  height?: number;
}

/**
 * While `enabled`, samples the local camera stream at `fps`, encodes each
 * frame as JPEG/base64 and ships it over the meeting WebSocket as a
 * `video_frame` message. The backend runs the sign-translation pipeline and
 * broadcasts `translation_result` messages (consumed by useTranslationOverlay).
 */
export const useSignTranslationCapture = ({
  localStream,
  enabled,
  fps = 5,
  width = 480,
  height = 360,
}: UseSignTranslationCaptureOptions): void => {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const canvasRef = useRef<HTMLCanvasElement | null>(null);

  useEffect(() => {
    if (!enabled || !localStream) return;

    const video = document.createElement('video');
    video.muted = true;
    video.playsInline = true;
    video.srcObject = localStream;
    videoRef.current = video;

    const canvas = document.createElement('canvas');
    canvas.width = width;
    canvas.height = height;
    canvasRef.current = canvas;
    const ctx = canvas.getContext('2d');

    let cancelled = false;
    const playPromise = video.play().catch(() => {
      /* autoplay can reject if the stream isn't ready yet; the interval retries */
    });

    const sendFrame = () => {
      if (cancelled || !ctx || video.videoWidth === 0) return;
      ctx.drawImage(video, 0, 0, width, height);
      canvas.toBlob(
        (blob) => {
          if (cancelled || !blob) return;
          const reader = new FileReader();
          reader.onloadend = () => {
            if (cancelled || typeof reader.result !== 'string') return;
            const b64 = reader.result.split(',')[1]; // drop "data:image/jpeg;base64,"
            if (b64) {
              WebSocketService.getInstance().sendVideoFrame(b64, performance.now() / 1000);
            }
          };
          reader.readAsDataURL(blob);
        },
        'image/jpeg',
        0.6,
      );
    };

    const intervalId = window.setInterval(sendFrame, 1000 / fps);

    return () => {
      cancelled = true;
      window.clearInterval(intervalId);
      void playPromise;
      video.pause();
      video.srcObject = null;
      videoRef.current = null;
      canvasRef.current = null;
    };
  }, [localStream, enabled, fps, width, height]);
};

export default useSignTranslationCapture;
