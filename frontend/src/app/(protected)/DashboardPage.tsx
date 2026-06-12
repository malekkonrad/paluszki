'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Container,
  InputAdornment,
  CircularProgress,
  Divider,
  Snackbar,
  Alert,
} from '@mui/material';
import { AxiosError } from 'axios';
import {
  VideoCall as VideoCallIcon,
  Groups as GroupsIcon,
  LinkRounded as LinkIcon,
  Add as AddIcon,
  ArrowForward as ArrowForwardIcon,
  Security as SecurityIcon,
  Speed as SpeedIcon,
  Chat as ChatIcon,
} from '@mui/icons-material';
import MeetingService from '@/api/services/meetingService';

const DashboardPage = () => {
  const router = useRouter();
  const [meetingCode, setMeetingCode] = useState('');
  const [isCreating, setIsCreating] = useState(false);
  const [isJoining, setIsJoining] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleCreateMeeting = async () => {
    setIsCreating(true);
    try {
      const response = await MeetingService.create();
      router.push(`/meeting/${response.code}`);
    } catch {
      setError('Nie udało się utworzyć spotkania — spróbuj ponownie');
    } finally {
      setIsCreating(false);
    }
  };

  const handleJoinMeeting = async () => {
    if (!meetingCode.trim()) return;
    setIsJoining(true);
    try {
      await MeetingService.join(meetingCode.trim());
      router.push(`/meeting/${meetingCode.trim()}`);
    } catch (err) {
      const status = err instanceof AxiosError ? err.response?.status : undefined;
      if (status === 404) {
        setError('Spotkanie o tym kodzie nie istnieje');
      } else if (status === 410) {
        setError('To spotkanie zostało już zakończone');
      } else {
        setError('Nie udało się dołączyć do spotkania — spróbuj ponownie');
      }
    } finally {
      setIsJoining(false);
    }
  };

  const features = [
    {
      icon: <SecurityIcon sx={{ fontSize: 28 }} />,
      title: 'Bezpieczne połączenia',
      description: 'Szyfrowanie end-to-end dla wszystkich rozmów',
      color: '#7C4DFF',
    },
    {
      icon: <SpeedIcon sx={{ fontSize: 28 }} />,
      title: 'Niska latencja',
      description: 'WebRTC zapewnia błyskawiczną komunikację',
      color: '#00E5FF',
    },
    {
      icon: <ChatIcon sx={{ fontSize: 28 }} />,
      title: 'Czat tekstowy',
      description: 'Wbudowany czat w każdym spotkaniu',
      color: '#69F0AE',
    },
  ];

  return (
    <Container maxWidth="lg" sx={{ py: 6 }}>
      {/* Hero Section */}
      <Box sx={{ textAlign: 'center', mb: 8 }}>
        <Typography
          variant="h2"
          sx={{
            fontWeight: 800,
            mb: 2,
            background: 'linear-gradient(135deg, #E8EAED 0%, #9AA0A6 100%)',
            backgroundClip: 'text',
            WebkitBackgroundClip: 'text',
            WebkitTextFillColor: 'transparent',
            fontSize: { xs: '2rem', sm: '2.5rem', md: '3rem' },
          }}
        >
          Twoje spotkania video,{' '}
          <Box
            component="span"
            sx={{
              background: 'linear-gradient(135deg, #7C4DFF 0%, #00E5FF 100%)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
            }}
          >
            bez granic
          </Box>
        </Typography>
        <Typography
          variant="h6"
          color="text.secondary"
          sx={{ maxWidth: 600, mx: 'auto', fontWeight: 400, lineHeight: 1.7 }}
        >
          Rozpocznij nowe spotkanie lub dołącz do istniejącego. MeetFlow zapewnia profesjonalną komunikację video z wysoką jakością.
        </Typography>
      </Box>

      {/* Action Cards */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', md: '1fr 1fr' },
          gap: 4,
          mb: 8,
          maxWidth: 900,
          mx: 'auto',
        }}
      >
        {/* Create Meeting Card */}
        <Card
          sx={{
            background: 'rgba(17, 24, 39, 0.6)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(124, 77, 255, 0.15)',
            transition: 'all 0.3s ease',
            '&:hover': {
              border: '1px solid rgba(124, 77, 255, 0.35)',
              boxShadow: '0 12px 40px rgba(124, 77, 255, 0.15)',
              transform: 'translateY(-4px)',
            },
          }}
        >
          <CardContent sx={{ p: 4 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 56,
                height: 56,
                borderRadius: '14px',
                background: 'linear-gradient(135deg, rgba(124, 77, 255, 0.2) 0%, rgba(124, 77, 255, 0.05) 100%)',
                mb: 3,
              }}
            >
              <VideoCallIcon sx={{ fontSize: 30, color: '#7C4DFF' }} />
            </Box>

            <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
              Nowe spotkanie
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3, lineHeight: 1.6 }}>
              Utwórz nowe spotkanie i zaproś uczestników za pomocą wygenerowanego linku.
            </Typography>

            <Button
              fullWidth
              variant="contained"
              size="large"
              onClick={handleCreateMeeting}
              disabled={isCreating}
              startIcon={isCreating ? <CircularProgress size={20} color="inherit" /> : <AddIcon />}
              sx={{
                py: 1.5,
                background: 'linear-gradient(135deg, #7C4DFF 0%, #651FFF 100%)',
                '&:hover': {
                  background: 'linear-gradient(135deg, #651FFF 0%, #536DFE 100%)',
                },
              }}
            >
              {isCreating ? 'Tworzenie...' : 'Utwórz spotkanie'}
            </Button>
          </CardContent>
        </Card>

        {/* Join Meeting Card */}
        <Card
          sx={{
            background: 'rgba(17, 24, 39, 0.6)',
            backdropFilter: 'blur(16px)',
            border: '1px solid rgba(0, 229, 255, 0.15)',
            transition: 'all 0.3s ease',
            '&:hover': {
              border: '1px solid rgba(0, 229, 255, 0.35)',
              boxShadow: '0 12px 40px rgba(0, 229, 255, 0.1)',
              transform: 'translateY(-4px)',
            },
          }}
        >
          <CardContent sx={{ p: 4 }}>
            <Box
              sx={{
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 56,
                height: 56,
                borderRadius: '14px',
                background: 'linear-gradient(135deg, rgba(0, 229, 255, 0.2) 0%, rgba(0, 229, 255, 0.05) 100%)',
                mb: 3,
              }}
            >
              <GroupsIcon sx={{ fontSize: 30, color: '#00E5FF' }} />
            </Box>

            <Typography variant="h5" sx={{ fontWeight: 700, mb: 1 }}>
              Dołącz do spotkania
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ mb: 3, lineHeight: 1.6 }}>
              Wpisz kod spotkania, aby dołączyć do trwającej rozmowy video.
            </Typography>

            <TextField
              fullWidth
              placeholder="Wpisz kod spotkania"
              value={meetingCode}
              onChange={(e) => setMeetingCode(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleJoinMeeting()}
              sx={{ mb: 2 }}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <LinkIcon sx={{ color: 'text.secondary' }} />
                    </InputAdornment>
                  ),
                },
              }}
            />

            <Button
              fullWidth
              variant="outlined"
              size="large"
              onClick={handleJoinMeeting}
              disabled={!meetingCode.trim() || isJoining}
              endIcon={isJoining ? <CircularProgress size={20} color="inherit" /> : <ArrowForwardIcon />}
              sx={{
                py: 1.5,
                borderColor: '#00E5FF',
                color: '#00E5FF',
                '&:hover': {
                  borderColor: '#00E5FF',
                  bgcolor: 'rgba(0, 229, 255, 0.08)',
                },
                '&.Mui-disabled': {
                  borderColor: 'rgba(0, 229, 255, 0.3)',
                  color: 'rgba(0, 229, 255, 0.3)',
                },
              }}
            >
              {isJoining ? 'Dołączanie...' : 'Dołącz'}
            </Button>
          </CardContent>
        </Card>
      </Box>

      <Divider sx={{ mb: 8 }} />

      {/* Features Section */}
      <Box
        sx={{
          display: 'grid',
          gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr 1fr' },
          gap: 4,
          maxWidth: 900,
          mx: 'auto',
        }}
      >
        {features.map((feature, index) => (
          <Box
            key={index}
            sx={{
              textAlign: 'center',
              p: 3,
            }}
          >
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 48,
                height: 48,
                borderRadius: '12px',
                background: `${feature.color}15`,
                mb: 2,
                color: feature.color,
              }}
            >
              {feature.icon}
            </Box>
            <Typography variant="h6" sx={{ fontWeight: 600, mb: 1, fontSize: '1rem' }}>
              {feature.title}
            </Typography>
            <Typography variant="body2" color="text.secondary" sx={{ lineHeight: 1.6 }}>
              {feature.description}
            </Typography>
          </Box>
        ))}
      </Box>

      <Snackbar
        open={error !== null}
        autoHideDuration={5000}
        onClose={() => setError(null)}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert onClose={() => setError(null)} severity="error" variant="filled" sx={{ borderRadius: 2 }}>
          {error}
        </Alert>
      </Snackbar>
    </Container>
  );
};

export default DashboardPage;
