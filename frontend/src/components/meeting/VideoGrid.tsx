import { Box, Typography, Paper, Avatar, Chip } from '@mui/material';
import {
  MicOff as MicOffIcon,
  MonitorHeart as MonitorHeartIcon,
  SignLanguage as SignLanguageIcon,
} from '@mui/icons-material';

interface PulseReading {
  bpm: number;
  confidence: number;
}

interface Detection {
  gestureLabel: string;
  confidence: number;
  accepted: boolean;
}

interface VideoGridProps {
  localStream: MediaStream | null;
  isScreenSharing: boolean;
  remoteStreams: Map<string, MediaStream>;
  peerNames: Map<string, string>;
  isCameraOff: boolean;
  isMuted: boolean;
  currentUserName: string;
  localUserId: string;
  getTranslationFor: (userId: string) => { text: string } | null;
  getDetectionFor: (userId: string) => Detection | null;
  getPulseFor: (userId: string) => PulseReading | null;
}

interface VideoTileProps {
  stream: MediaStream | null;
  name: string;
  isMuted?: boolean;
  isCameraOff?: boolean;
  isLocal?: boolean;
  /** Mirror the video horizontally; defaults to isLocal (self-view), but a
   *  shared screen must never be mirrored. */
  mirror?: boolean;
  caption?: string | null;
  detection?: Detection | null;
  pulse?: PulseReading | null;
}

// Below this peak-to-band power ratio the reading is likely motion/noise, so
// we dim the badge rather than hide it (keeps the UI from flickering).
const PULSE_CONFIDENCE_FLOOR = 0.12;

const VideoTile = ({ stream, name, isMuted, isCameraOff, isLocal, mirror, caption, detection, pulse }: VideoTileProps) => {
  // Callback ref instead of useEffect: the <video> unmounts while the camera
  // is off (avatar branch) and a plain effect keyed on [stream] never re-runs
  // for the remounted element, leaving it black after re-enabling the camera.
  const attachStream = (el: HTMLVideoElement | null) => {
    if (el && stream && el.srcObject !== stream) {
      el.srcObject = stream;
    }
  };

  return (
    <Paper
      elevation={0}
      sx={{
        position: 'relative',
        width: '100%',
        paddingTop: '56.25%', // 16:9
        borderRadius: 3,
        overflow: 'hidden',
        bgcolor: '#1A1A2E',
        border: '1px solid rgba(255, 255, 255, 0.06)',
        transition: 'border-color 0.3s ease',
        '&:hover': {
          borderColor: 'rgba(124, 77, 255, 0.3)',
        },
      }}
    >
      {stream && !isCameraOff ? (
        <video
          ref={attachStream}
          autoPlay
          playsInline
          muted={isLocal}
          style={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            objectFit: 'cover',
            transform: (mirror ?? isLocal) ? 'scaleX(-1)' : 'none',
          }}
        />
      ) : (
        <Box
          sx={{
            position: 'absolute',
            top: 0,
            left: 0,
            width: '100%',
            height: '100%',
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            background: 'linear-gradient(135deg, #1A1A2E 0%, #16213E 100%)',
          }}
        >
          <Avatar
            sx={{
              width: 80,
              height: 80,
              bgcolor: '#7C4DFF',
              fontSize: '2rem',
              fontWeight: 700,
            }}
          >
            {name.split(' ').map(n => n[0]).join('').toUpperCase().slice(0, 2)}
          </Avatar>
        </Box>
      )}

      {/* Name label */}
      <Box
        sx={{
          position: 'absolute',
          bottom: 8,
          left: 8,
          display: 'flex',
          alignItems: 'center',
          gap: 0.5,
        }}
      >
        <Chip
          label={isLocal ? `${name} (Ty)` : name}
          size="small"
          sx={{
            bgcolor: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(8px)',
            color: '#fff',
            fontSize: '0.75rem',
            fontWeight: 500,
            height: 26,
          }}
        />
        {isMuted && (
          <Box
            sx={{
              width: 26,
              height: 26,
              borderRadius: '50%',
              bgcolor: 'rgba(255, 82, 82, 0.8)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
          >
            <MicOffIcon sx={{ fontSize: 14, color: '#fff' }} />
          </Box>
        )}
      </Box>

      {/* Live sign detection — top-left, dimmed when below the threshold */}
      {detection && (
        <Chip
          icon={<SignLanguageIcon sx={{ fontSize: 16, color: '#7C4DFF !important' }} />}
          label={`${detection.gestureLabel} ${Math.round(detection.confidence * 100)}%`}
          size="small"
          sx={{
            position: 'absolute',
            top: 8,
            left: 8,
            bgcolor: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(8px)',
            color: '#fff',
            fontSize: '0.75rem',
            fontWeight: 600,
            height: 26,
            opacity: detection.accepted ? 1 : 0.45,
          }}
        />
      )}

      {/* Pulse (rPPG) badge — top-right, dimmed when the signal is weak */}
      {pulse && (
        <Chip
          icon={<MonitorHeartIcon sx={{ fontSize: 16, color: '#FF5252 !important' }} />}
          label={`${Math.round(pulse.bpm)} bpm`}
          size="small"
          sx={{
            position: 'absolute',
            top: 8,
            right: 8,
            bgcolor: 'rgba(0, 0, 0, 0.6)',
            backdropFilter: 'blur(8px)',
            color: '#fff',
            fontSize: '0.75rem',
            fontWeight: 600,
            height: 26,
            opacity: pulse.confidence >= PULSE_CONFIDENCE_FLOOR ? 1 : 0.45,
          }}
        />
      )}

      {/* Sign-language translation caption (subtitle style) */}
      {caption && (
        <Box
          sx={{
            position: 'absolute',
            bottom: '10%',
            left: '50%',
            transform: 'translateX(-50%)',
            maxWidth: '90%',
            px: 1.5,
            py: 0.75,
            borderRadius: 1.5,
            bgcolor: 'rgba(0, 0, 0, 0.7)',
            backdropFilter: 'blur(4px)',
          }}
        >
          <Typography
            sx={{
              color: '#fff',
              fontSize: '0.95rem',
              fontWeight: 500,
              lineHeight: 1.3,
              textAlign: 'center',
              display: '-webkit-box',
              WebkitLineClamp: 2,
              WebkitBoxOrient: 'vertical',
              overflow: 'hidden',
            }}
          >
            {caption}
          </Typography>
        </Box>
      )}
    </Paper>
  );
};

const VideoGrid = ({
  localStream,
  isScreenSharing,
  remoteStreams,
  peerNames,
  isCameraOff,
  isMuted,
  currentUserName,
  localUserId,
  getTranslationFor,
  getDetectionFor,
  getPulseFor,
}: VideoGridProps) => {
  const totalParticipants = 1 + remoteStreams.size;

  const getGridColumns = () => {
    if (totalParticipants <= 1) return '1fr';
    if (totalParticipants <= 2) return '1fr 1fr';
    if (totalParticipants <= 4) return '1fr 1fr';
    return '1fr 1fr 1fr';
  };

  return (
    <Box sx={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 2, p: 2 }}>
      <Box
        sx={{
          flex: 1,
          display: 'grid',
          gridTemplateColumns: getGridColumns(),
          gap: 2,
          alignContent: 'center',
        }}
      >
        {/* Local video */}
        <VideoTile
          stream={localStream}
          name={currentUserName}
          isMuted={isMuted}
          // The shared screen should stay visible even with the camera off,
          // and must not be mirrored like the self-view.
          isCameraOff={isCameraOff && !isScreenSharing}
          mirror={!isScreenSharing}
          isLocal
          caption={getTranslationFor(localUserId)?.text ?? null}
          detection={getDetectionFor(localUserId)}
          pulse={getPulseFor(localUserId)}
        />

        {/* Remote videos */}
        {Array.from(remoteStreams.entries()).map(([peerId, stream]) => (
          <VideoTile
            key={peerId}
            stream={stream}
            name={peerNames.get(peerId) || 'Uczestnik'}
            caption={getTranslationFor(peerId)?.text ?? null}
            detection={getDetectionFor(peerId)}
            pulse={getPulseFor(peerId)}
          />
        ))}
      </Box>

      {/* No participants message */}
      {remoteStreams.size === 0 && (
        <Box
          sx={{
            textAlign: 'center',
            py: 2,
          }}
        >
          <Typography variant="body2" color="text.secondary">
            Oczekiwanie na uczestników...
          </Typography>
          <Typography variant="caption" color="text.disabled" sx={{ mt: 0.5 }}>
            Udostępnij link do spotkania, aby zaprosić innych
          </Typography>
        </Box>
      )}
    </Box>
  );
};

export default VideoGrid;
