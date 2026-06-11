import { FaceDetector, FilesetResolver } from '@mediapipe/tasks-vision';

/**
 * Browser-side face detection for the rPPG forehead ROI.
 *
 * Uses MediaPipe's lightweight BlazeFace short-range detector (bounding box +
 * 6 keypoints) rather than the full 468-point FaceLandmarker — for a forehead
 * box we only need the eye positions, and BlazeFace is far cheaper to run every
 * frame. WASM + model are pulled from the jsDelivr / Google CDNs (no bundled
 * assets); the detector is created once and cached for the page lifetime.
 */

// Keypoint indices for BlazeFace (normalized to the input image).
const KP_RIGHT_EYE = 0;
const KP_LEFT_EYE = 1;

const WASM_URL =
  'https://cdn.jsdelivr.net/npm/@mediapipe/tasks-vision@0.10.35/wasm';
const MODEL_URL =
  'https://storage.googleapis.com/mediapipe-models/face_detector/blaze_face_short_range/float16/1/blaze_face_short_range.task';

export interface NormalizedRoi {
  /** Fractions of the frame: top-left x, y and width, height (all 0..1). */
  x: number;
  y: number;
  w: number;
  h: number;
}

let detectorPromise: Promise<FaceDetector> | null = null;

/** Lazily create (and cache) the FaceDetector. Rejects if WASM/model fail. */
export const getFaceDetector = (): Promise<FaceDetector> => {
  if (!detectorPromise) {
    detectorPromise = (async () => {
      const vision = await FilesetResolver.forVisionTasks(WASM_URL);
      return FaceDetector.createFromOptions(vision, {
        baseOptions: { modelAssetPath: MODEL_URL, delegate: 'GPU' },
        runningMode: 'VIDEO',
      });
    })().catch((err) => {
      detectorPromise = null; // allow a retry on the next toggle
      throw err;
    });
  }
  return detectorPromise;
};

const clamp01 = (v: number) => Math.min(1, Math.max(0, v));

/**
 * Detect a face in `source` and return a normalized forehead ROI, or `null`
 * if no face is found. The forehead box sits above the eyes, scaled by the
 * inter-ocular distance so it tracks face size and position. `tsMs` must be
 * monotonically increasing (VIDEO running mode requirement).
 */
export const detectForeheadRoi = (
  detector: FaceDetector,
  source: HTMLCanvasElement | HTMLVideoElement,
  tsMs: number,
): NormalizedRoi | null => {
  const result = detector.detectForVideo(source, tsMs);
  const det = result.detections?.[0];
  const kp = det?.keypoints;
  if (!kp || kp.length <= KP_LEFT_EYE) return null;

  const rightEye = kp[KP_RIGHT_EYE];
  const leftEye = kp[KP_LEFT_EYE];
  const midX = (rightEye.x + leftEye.x) / 2;
  const eyeY = (rightEye.y + leftEye.y) / 2;
  const eyeDist = Math.abs(leftEye.x - rightEye.x);
  if (eyeDist < 1e-3) return null;

  // Forehead: a band above the brow line, ~0.7×eyeDist wide / 0.5×eyeDist tall.
  const w = 0.7 * eyeDist;
  const h = 0.5 * eyeDist;
  const x = midX - w / 2;
  const y = eyeY - 0.35 * eyeDist - h; // 0.35 gap to clear the eyebrows

  return {
    x: clamp01(x),
    y: clamp01(y),
    w: clamp01(w),
    h: clamp01(h),
  };
};
