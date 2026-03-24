import {
  Box,
  Typography,
  Paper,
  Button,
  Avatar,
  List,
  ListItem,
  ListItemAvatar,
  ListItemText,
  ListItemSecondaryAction,
  CircularProgress,
  Divider,
} from '@mui/material';
import {
  Check as CheckIcon,
  Close as CloseIcon,
  HourglassBottom as PendingIcon,
  People as PeopleIcon,
} from '@mui/icons-material';
import type { IParticipant } from '@/api/interfaces/meeting';

interface WaitingRoomProps {
  isHost: boolean;
  waitingParticipants: IParticipant[];
  onApprove: (userId: string) => void;
  onReject: (userId: string) => void;
  isWaiting?: boolean; // For non-host: are they waiting for approval?
}

const WaitingRoom = ({
  isHost,
  waitingParticipants,
  onApprove,
  onReject,
  isWaiting = false,
}: WaitingRoomProps) => {
  // Non-host waiting view
  if (!isHost && isWaiting) {
    return (
      <Box
        sx={{
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          minHeight: '100vh',
          background: 'linear-gradient(135deg, #0A0E1A 0%, #1A1A2E 50%, #16213E 100%)',
        }}
      >
        <Paper
          elevation={0}
          sx={{
            textAlign: 'center',
            p: 6,
            maxWidth: 420,
            bgcolor: 'rgba(17, 24, 39, 0.8)',
            backdropFilter: 'blur(20px)',
            border: '1px solid rgba(255, 255, 255, 0.06)',
          }}
        >
          <Box
            sx={{
              display: 'inline-flex',
              alignItems: 'center',
              justifyContent: 'center',
              width: 80,
              height: 80,
              borderRadius: '50%',
              background: 'linear-gradient(135deg, rgba(124, 77, 255, 0.2) 0%, rgba(0, 229, 255, 0.2) 100%)',
              mb: 3,
            }}
          >
            <CircularProgress size={36} sx={{ color: '#7C4DFF' }} />
          </Box>
          <Typography variant="h5" sx={{ fontWeight: 700, mb: 1.5 }}>
            Oczekiwanie na zatwierdzenie
          </Typography>
          <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.7 }}>
            Organizator spotkania musi zatwierdzić Twoje uczestnictwo.
            Proszę czekać...
          </Typography>
        </Paper>
      </Box>
    );
  }

  // Host: waiting participants panel
  if (!isHost || waitingParticipants.length === 0) {
    return null;
  }

  return (
    <Paper
      elevation={0}
      sx={{
        position: 'fixed',
        top: 80,
        right: 16,
        width: 360,
        maxHeight: 400,
        zIndex: 100,
        bgcolor: 'rgba(17, 24, 39, 0.95)',
        backdropFilter: 'blur(16px)',
        border: '1px solid rgba(255, 215, 64, 0.2)',
        borderRadius: 3,
        boxShadow: '0 12px 40px rgba(0, 0, 0, 0.4)',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 2.5,
          py: 2,
          display: 'flex',
          alignItems: 'center',
          gap: 1,
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
        }}
      >
        <PeopleIcon sx={{ color: '#FFD740', fontSize: 22 }} />
        <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '0.95rem' }}>
          Poczekalnia
        </Typography>
        <Box
          sx={{
            ml: 'auto',
            bgcolor: 'rgba(255, 215, 64, 0.15)',
            color: '#FFD740',
            fontSize: '0.75rem',
            fontWeight: 700,
            px: 1,
            py: 0.25,
            borderRadius: 10,
            minWidth: 24,
            textAlign: 'center',
          }}
        >
          {waitingParticipants.length}
        </Box>
      </Box>

      {/* Participants list */}
      <List sx={{ overflow: 'auto', maxHeight: 320, py: 0.5 }}>
        {waitingParticipants.map((participant, index) => (
          <Box key={participant.userId}>
            <ListItem sx={{ py: 1.5, px: 2 }}>
              <ListItemAvatar>
                <Avatar
                  src={participant.avatarUrl}
                  sx={{
                    width: 40,
                    height: 40,
                    bgcolor: '#7C4DFF',
                    fontSize: '0.875rem',
                    fontWeight: 600,
                  }}
                >
                  {`${participant.firstName[0]}${participant.lastName[0]}`}
                </Avatar>
              </ListItemAvatar>
              <ListItemText
                primary={
                  <Typography variant="body2" sx={{ fontWeight: 600 }}>
                    {participant.firstName} {participant.lastName}
                  </Typography>
                }
                secondary={
                  <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5, mt: 0.25 }}>
                    <PendingIcon sx={{ fontSize: 14, color: '#FFD740' }} />
                    <Typography variant="caption" color="text.secondary">
                      Oczekuje...
                    </Typography>
                  </Box>
                }
              />
              <ListItemSecondaryAction>
                <Box sx={{ display: 'flex', gap: 0.5 }}>
                  <Button
                    size="small"
                    variant="contained"
                    onClick={() => onApprove(participant.userId)}
                    sx={{
                      minWidth: 36,
                      width: 36,
                      height: 36,
                      p: 0,
                      bgcolor: 'rgba(105, 240, 174, 0.15)',
                      color: '#69F0AE',
                      border: '1px solid rgba(105, 240, 174, 0.25)',
                      boxShadow: 'none',
                      '&:hover': {
                        bgcolor: 'rgba(105, 240, 174, 0.25)',
                        boxShadow: 'none',
                      },
                    }}
                  >
                    <CheckIcon sx={{ fontSize: 20 }} />
                  </Button>
                  <Button
                    size="small"
                    variant="contained"
                    onClick={() => onReject(participant.userId)}
                    sx={{
                      minWidth: 36,
                      width: 36,
                      height: 36,
                      p: 0,
                      bgcolor: 'rgba(255, 82, 82, 0.15)',
                      color: '#FF5252',
                      border: '1px solid rgba(255, 82, 82, 0.25)',
                      boxShadow: 'none',
                      '&:hover': {
                        bgcolor: 'rgba(255, 82, 82, 0.25)',
                        boxShadow: 'none',
                      },
                    }}
                  >
                    <CloseIcon sx={{ fontSize: 20 }} />
                  </Button>
                </Box>
              </ListItemSecondaryAction>
            </ListItem>
            {index < waitingParticipants.length - 1 && (
              <Divider variant="inset" component="li" />
            )}
          </Box>
        ))}
      </List>
    </Paper>
  );
};

export default WaitingRoom;
