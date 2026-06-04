import { Box, IconButton, Tooltip } from '@mui/material';
import {
  Mic as MicIcon,
  MicOff as MicOffIcon,
  Videocam as VideocamIcon,
  VideocamOff as VideocamOffIcon,
  CallEnd as CallEndIcon,
  ScreenShare as ScreenShareIcon,
  BugReport as BugReportIcon,
  ContentCopy as CopyIcon,
  Translate as TranslateIcon,
} from '@mui/icons-material';

interface MeetingControlsProps {
  isMuted: boolean;
  isCameraOff: boolean;
  isDebugActive: boolean;
  isTranslationActive: boolean;
  onToggleMute: () => void;
  onToggleCamera: () => void;
  onToggleDebug: () => void;
  onToggleTranslation: () => void;
  onScreenShare: () => void;
  onEndCall: () => void;
  onCopyLink: () => void;
}

const MeetingControls = ({
  isMuted,
  isCameraOff,
  isDebugActive,
  isTranslationActive,
  onToggleMute,
  onToggleCamera,
  onToggleDebug,
  onToggleTranslation,
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
      <Tooltip title="Udostępnij ekran">
        <IconButton
          onClick={onScreenShare}
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
          <ScreenShareIcon />
        </IconButton>
      </Tooltip>

      {/* Sign-language translation */}
      <Tooltip title={isTranslationActive ? 'Wyłącz tłumaczenie migowego' : 'Włącz tłumaczenie migowego'}>
        <IconButton
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

      {/* Debug Overlay */}
      <Tooltip title={isDebugActive ? 'Wyłącz debug overlay' : 'Włącz debug overlay'}>
        <IconButton
          onClick={onToggleDebug}
          sx={{
            width: 52,
            height: 52,
            bgcolor: isDebugActive
              ? 'rgba(255, 215, 64, 0.15)'
              : 'rgba(255, 255, 255, 0.08)',
            border: isDebugActive
              ? '2px solid rgba(255, 215, 64, 0.3)'
              : '2px solid rgba(255, 255, 255, 0.08)',
            color: isDebugActive ? '#FFD740' : '#E8EAED',
            '&:hover': {
              bgcolor: isDebugActive
                ? 'rgba(255, 215, 64, 0.25)'
                : 'rgba(255, 255, 255, 0.12)',
              transform: 'scale(1.1)',
            },
          }}
        >
          <BugReportIcon />
        </IconButton>
      </Tooltip>

      {/* Copy Link */}
      <Tooltip title="Kopiuj link spotkania">
        <IconButton
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
