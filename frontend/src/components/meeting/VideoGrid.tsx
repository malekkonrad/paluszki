import { useEffect, useRef } from 'react';
import { Box, Typography, Paper, Avatar, Chip } from '@mui/material';
import {
  MicOff as MicOffIcon,
  BugReport as BugReportIcon,
} from '@mui/icons-material';

interface VideoGridProps {
  localStream: MediaStream | null;
  remoteStreams: Map<string, MediaStream>;
  peerNames: Map<string, string>;
  isCameraOff: boolean;
  isMuted: boolean;
  debugStream: MediaStream | null;
  isDebugActive: boolean;
  currentUserName: string;
}

interface VideoTileProps {
  stream: MediaStream | null;
  name: string;
  isMuted?: boolean;
  isCameraOff?: boolean;
  isLocal?: boolean;
}

const VideoTile = ({ stream, name, isMuted, isCameraOff, isLocal }: VideoTileProps) => {
  const videoRef = useRef<HTMLVideoElement>(null);

  useEffect(() => {
    if (videoRef.current && stream) {
      videoRef.current.srcObject = stream;
    }
  }, [stream]);

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
          ref={videoRef}
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
            transform: isLocal ? 'scaleX(-1)' : 'none',
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
    </Paper>
  );
};

const VideoGrid = ({
  localStream,
  remoteStreams,
  peerNames,
  isCameraOff,
  isMuted,
  debugStream,
  isDebugActive,
  currentUserName,
}: VideoGridProps) => {
  const debugVideoRef = useRef<HTMLVideoElement>(null);
  const totalParticipants = 1 + remoteStreams.size;

  useEffect(() => {
    if (debugVideoRef.current && debugStream) {
      debugVideoRef.current.srcObject = debugStream;
    }
  }, [debugStream]);

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
          isCameraOff={isCameraOff}
          isLocal
        />

        {/* Remote videos */}
        {Array.from(remoteStreams.entries()).map(([peerId, stream]) => (
          <VideoTile
            key={peerId}
            stream={stream}
            name={peerNames.get(peerId) || 'Uczestnik'}
          />
        ))}
      </Box>

      {/* Debug overlay stream */}
      {isDebugActive && debugStream && (
        <Paper
          elevation={0}
          sx={{
            position: 'relative',
            width: '100%',
            maxHeight: 240,
            borderRadius: 3,
            overflow: 'hidden',
            border: '2px solid rgba(255, 215, 64, 0.4)',
            bgcolor: '#1A1A2E',
          }}
        >
          <video
            ref={debugVideoRef}
            autoPlay
            playsInline
            muted
            style={{
              width: '100%',
              height: '100%',
              objectFit: 'contain',
              maxHeight: 240,
            }}
          />
          <Chip
            icon={<BugReportIcon sx={{ fontSize: 16 }} />}
            label="Debug Overlay"
            size="small"
            sx={{
              position: 'absolute',
              top: 8,
              left: 8,
              bgcolor: 'rgba(255, 215, 64, 0.15)',
              color: '#FFD740',
              border: '1px solid rgba(255, 215, 64, 0.3)',
              fontWeight: 600,
              fontSize: '0.7rem',
            }}
          />
        </Paper>
      )}

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
