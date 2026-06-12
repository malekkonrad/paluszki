import { Box, IconButton, Tooltip } from '@mui/material';
import {
  Mic as MicIcon,
  MicOff as MicOffIcon,
  Videocam as VideocamIcon,
  VideocamOff as VideocamOffIcon,
  CallEnd as CallEndIcon,
  ScreenShare as ScreenShareIcon,
  ContentCopy as CopyIcon,
  Translate as TranslateIcon,
  MonitorHeart as MonitorHeartIcon,
} from '@mui/icons-material';

interface MeetingControlsProps {
  isMuted: boolean;
  isCameraOff: boolean;
  isTranslationActive: boolean;
  isPulseActive: boolean;
  isScreenSharing: boolean;
  onToggleMute: () => void;
  onToggleCamera: () => void;
  onToggleTranslation: () => void;
  onTogglePulse: () => void;
  onScreenShare: () => void;
  onEndCall: () => void;
  onCopyLink: () => void;
}

const MeetingControls = ({
  isMuted,
  isCameraOff,
  isTranslationActive,
  isPulseActive,
  isScreenSharing,
  onToggleMute,
  onToggleCamera,
  onToggleTranslation,
  onTogglePulse,
  onScreenShare,
  onEndCall,
  onCopyLink,
}: MeetingControlsProps) => {
  return (
    <Box
      sx={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        gap: { xs: 1, sm: 2 },
        py: 2,
        px: 3,
      }}
    >
      {/* Mute */}
      <Tooltip title={isMuted ? 'Włącz mikrofon' : 'Wycisz mikrofon'}>
        <IconButton
          aria-label="mikrofon"
          onClick={onToggleMute}
          sx={{
            width: 52,
            height: 52,
            bgcolor: isMuted ? 'rgba(255, 82, 82, 0.15)' : 'rgba(255, 255, 255, 0.08)',
            border: isMuted
              ? '2px solid rgba(255, 82, 82, 0.3)'
              : '2px solid rgba(255, 255, 255, 0.08)',
            color: isMuted ? '#FF5252' : '#E8EAED',
            '&:hover': {
              bgcolor: isMuted ? 'rgba(255, 82, 82, 0.25)' : 'rgba(255, 255, 255, 0.12)',
              transform: 'scale(1.1)',
            },
          }}
        >
          {isMuted ? <MicOffIcon /> : <MicIcon />}
        </IconButton>
      </Tooltip>

      {/* Camera */}
      <Tooltip title={isCameraOff ? 'Włącz kamerę' : 'Wyłącz kamerę'}>
        <IconButton
          aria-label="kamera"
          onClick={onToggleCamera}
          sx={{
            width: 52,
            height: 52,
            bgcolor: isCameraOff ? 'rgba(255, 82, 82, 0.15)' : 'rgba(255, 255, 255, 0.08)',
            border: isCameraOff
              ? '2px solid rgba(255, 82, 82, 0.3)'
              : '2px solid rgba(255, 255, 255, 0.08)',
            color: isCameraOff ? '#FF5252' : '#E8EAED',
            '&:hover': {
              bgcolor: isCameraOff ? 'rgba(255, 82, 82, 0.25)' : 'rgba(255, 255, 255, 0.12)',
              transform: 'scale(1.1)',
            },
          }}
        >
          {isCameraOff ? <VideocamOffIcon /> : <VideocamIcon />}
        </IconButton>
      </Tooltip>

      {/* Screen Share */}
      <Tooltip title={isScreenSharing ? 'Zatrzymaj udostępnianie ekranu' : 'Udostępnij ekran'}>
        <IconButton
          aria-label="udostępnianie ekranu"
          onClick={onScreenShare}
          sx={{
            width: 52,
            height: 52,
            bgcolor: isScreenSharing
              ? 'rgba(0, 229, 255, 0.15)'
              : 'rgba(255, 255, 255, 0.08)',
            border: isScreenSharing
              ? '2px solid rgba(0, 229, 255, 0.4)'
              : '2px solid rgba(255, 255, 255, 0.08)',
            color: isScreenSharing ? '#00E5FF' : '#E8EAED',
            '&:hover': {
              bgcolor: isScreenSharing
                ? 'rgba(0, 229, 255, 0.25)'
                : 'rgba(255, 255, 255, 0.12)',
              transform: 'scale(1.1)',
            },
          }}
        >
          <ScreenShareIcon />
        </IconButton>
      </Tooltip>

      {/* Sign-language translation */}
      <Tooltip title={isTranslationActive ? 'Wyłącz tłumaczenie migowego' : 'Włącz tłumaczenie migowego'}>
        <IconButton
          aria-label="tłumaczenie migowego"
          onClick={onToggleTranslation}
          sx={{
            width: 52,
            height: 52,
            bgcolor: isTranslationActive
              ? 'rgba(124, 77, 255, 0.18)'
              : 'rgba(255, 255, 255, 0.08)',
            border: isTranslationActive
              ? '2px solid rgba(124, 77, 255, 0.4)'
              : '2px solid rgba(255, 255, 255, 0.08)',
            color: isTranslationActive ? '#7C4DFF' : '#E8EAED',
            '&:hover': {
              bgcolor: isTranslationActive
                ? 'rgba(124, 77, 255, 0.28)'
                : 'rgba(255, 255, 255, 0.12)',
              transform: 'scale(1.1)',
            },
          }}
        >
          <TranslateIcon />
        </IconButton>
      </Tooltip>

      {/* Pulse detection (rPPG) */}
      <Tooltip title={isPulseActive ? 'Wyłącz detekcję pulsu' : 'Włącz detekcję pulsu'}>
        <IconButton
          aria-label="detekcja pulsu"
          onClick={onTogglePulse}
          sx={{
            width: 52,
            height: 52,
            bgcolor: isPulseActive
              ? 'rgba(255, 82, 82, 0.15)'
              : 'rgba(255, 255, 255, 0.08)',
            border: isPulseActive
              ? '2px solid rgba(255, 82, 82, 0.4)'
              : '2px solid rgba(255, 255, 255, 0.08)',
            color: isPulseActive ? '#FF5252' : '#E8EAED',
            '&:hover': {
              bgcolor: isPulseActive
                ? 'rgba(255, 82, 82, 0.25)'
                : 'rgba(255, 255, 255, 0.12)',
              transform: 'scale(1.1)',
            },
          }}
        >
          <MonitorHeartIcon />
        </IconButton>
      </Tooltip>

      {/* Copy Link */}
      <Tooltip title="Kopiuj link spotkania">
        <IconButton
          aria-label="kopiuj link"
          onClick={onCopyLink}
          sx={{
            width: 52,
            height: 52,
            bgcolor: 'rgba(255, 255, 255, 0.08)',
            border: '2px solid rgba(255, 255, 255, 0.08)',
            color: '#E8EAED',
            '&:hover': {
              bgcolor: 'rgba(255, 255, 255, 0.12)',
              transform: 'scale(1.1)',
            },
          }}
        >
          <CopyIcon />
        </IconButton>
      </Tooltip>

      {/* End Call */}
      <Tooltip title="Zakończ połączenie">
        <IconButton
          aria-label="zakończ połączenie"
          onClick={onEndCall}
          sx={{
            width: 56,
            height: 56,
            bgcolor: '#FF5252',
            color: '#fff',
            border: 'none',
            '&:hover': {
              bgcolor: '#D32F2F',
              transform: 'scale(1.1)',
            },
          }}
        >
          <CallEndIcon />
        </IconButton>
      </Tooltip>
    </Box>
  );
};

export default MeetingControls;
