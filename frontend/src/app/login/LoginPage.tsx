'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  Box,
  Card,
  CardContent,
  Typography,
  TextField,
  Button,
  Divider,
  Alert,
  InputAdornment,
  IconButton,
  CircularProgress,
} from '@mui/material';
import {
  Google as GoogleIcon,
  Visibility,
  VisibilityOff,
  Email as EmailIcon,
  Lock as LockIcon,
  VideoCameraFront as VideoIcon,
  PersonOutline as DemoIcon,
} from '@mui/icons-material';
import { useAuth } from '@/hooks/useAuth';

const LoginPage = () => {
  const { login, googleLogin, demoLogin } = useAuth();
  const router = useRouter();
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [showPassword, setShowPassword] = useState(false);
  const [error, setError] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setIsLoading(true);

    try {
      await login({ email, password });
      router.push('/');
    } catch (err: unknown) {
      const error = err as { response?: { data?: { message?: string } } };
      setError(error.response?.data?.message || 'Błąd logowania. Sprawdź dane i spróbuj ponownie.');
    } finally {
      setIsLoading(false);
    }
  };

  const handleGoogleLogin = async () => {
    setError('');
    try {
      // W pełnej implementacji tutaj będzie Google OAuth flow
      // Na razie symulujemy credential token
      await googleLogin({ credential: 'google-oauth-token' });
      router.push('/');
    } catch {
      setError('Błąd logowania przez Google.');
    }
  };

  return (
    <Box
      sx={{
        minHeight: '100vh',
        display: 'flex',
        justifyContent: 'center',
        alignItems: 'center',
        background: 'linear-gradient(135deg, #0A0E1A 0%, #1A1A2E 50%, #16213E 100%)',
        p: 2,
        position: 'relative',
        overflow: 'hidden',
        '&::before': {
          content: '""',
          position: 'absolute',
          width: 600,
          height: 600,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(124, 77, 255, 0.08) 0%, transparent 70%)',
          top: '-10%',
          right: '-10%',
        },
        '&::after': {
          content: '""',
          position: 'absolute',
          width: 500,
          height: 500,
          borderRadius: '50%',
          background: 'radial-gradient(circle, rgba(0, 229, 255, 0.06) 0%, transparent 70%)',
          bottom: '-10%',
          left: '-10%',
        },
      }}
    >
      <Card
        sx={{
          maxWidth: 440,
          width: '100%',
          position: 'relative',
          zIndex: 1,
          background: 'rgba(17, 24, 39, 0.8)',
          backdropFilter: 'blur(20px)',
          border: '1px solid rgba(255, 255, 255, 0.06)',
          boxShadow: '0 20px 60px rgba(0, 0, 0, 0.5)',
        }}
      >
        <CardContent sx={{ p: { xs: 3, sm: 4 } }}>
          <Box sx={{ textAlign: 'center', mb: 4 }}>
            <Box
              sx={{
                display: 'inline-flex',
                alignItems: 'center',
                justifyContent: 'center',
                width: 64,
                height: 64,
                borderRadius: '16px',
                background: 'linear-gradient(135deg, rgba(124, 77, 255, 0.2) 0%, rgba(0, 229, 255, 0.2) 100%)',
                mb: 2,
              }}
            >
              <VideoIcon sx={{ fontSize: 36, color: '#7C4DFF' }} />
            </Box>
            <Typography variant="h4" sx={{ fontWeight: 700, mb: 0.5 }}>
              Witaj ponownie
            </Typography>
            <Typography variant="body2" color="text.secondary">
              Zaloguj się, aby kontynuować do MeetFlow
            </Typography>
          </Box>

          {error && (
            <Alert
              severity="error"
              sx={{
                mb: 3,
                borderRadius: 2,
                bgcolor: 'rgba(255, 82, 82, 0.08)',
                border: '1px solid rgba(255, 82, 82, 0.2)',
              }}
            >
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit}>
            <TextField
              fullWidth
              label="Email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              sx={{ mb: 2 }}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <EmailIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                    </InputAdornment>
                  ),
                },
              }}
            />

            <TextField
              fullWidth
              label="Hasło"
              type={showPassword ? 'text' : 'password'}
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
              sx={{ mb: 3 }}
              slotProps={{
                input: {
                  startAdornment: (
                    <InputAdornment position="start">
                      <LockIcon sx={{ color: 'text.secondary', fontSize: 20 }} />
                    </InputAdornment>
                  ),
                  endAdornment: (
                    <InputAdornment position="end">
                      <IconButton
                        onClick={() => setShowPassword(!showPassword)}
                        edge="end"
                        size="small"
                      >
                        {showPassword ? <VisibilityOff fontSize="small" /> : <Visibility fontSize="small" />}
                      </IconButton>
                    </InputAdornment>
                  ),
                },
              }}
            />

            <Button
              type="submit"
              fullWidth
              variant="contained"
              size="large"
              disabled={isLoading}
              sx={{
                py: 1.5,
                mb: 2,
                background: 'linear-gradient(135deg, #7C4DFF 0%, #651FFF 100%)',
                '&:hover': {
                  background: 'linear-gradient(135deg, #651FFF 0%, #536DFE 100%)',
                },
              }}
            >
              {isLoading ? <CircularProgress size={24} color="inherit" /> : 'Zaloguj się'}
            </Button>
          </form>

          <Divider sx={{ my: 2.5 }}>
            <Typography variant="body2" color="text.secondary">
              lub
            </Typography>
          </Divider>

          <Button
            fullWidth
            variant="outlined"
            size="large"
            onClick={handleGoogleLogin}
            startIcon={<GoogleIcon />}
            sx={{
              py: 1.5,
              borderColor: 'rgba(255, 255, 255, 0.12)',
              color: 'text.primary',
              '&:hover': {
                borderColor: 'rgba(255, 255, 255, 0.3)',
                bgcolor: 'rgba(255, 255, 255, 0.04)',
              },
            }}
          >
            Zaloguj przez Google
          </Button>

          <Button
            fullWidth
            variant="outlined"
            size="large"
            onClick={() => { demoLogin(); router.push('/'); }}
            startIcon={<DemoIcon />}
            sx={{
              py: 1.5,
              mt: 1.5,
              borderColor: 'rgba(105, 240, 174, 0.3)',
              color: '#69F0AE',
              '&:hover': {
                borderColor: 'rgba(105, 240, 174, 0.5)',
                bgcolor: 'rgba(105, 240, 174, 0.06)',
              },
            }}
          >
            Wejdź jako Demo
          </Button>

          <Box sx={{ mt: 3, textAlign: 'center' }}>
            <Typography variant="body2" color="text.secondary">
              Nie masz konta?{' '}
              <Typography
                component={Link}
                href="/register"
                variant="body2"
                sx={{
                  color: '#7C4DFF',
                  textDecoration: 'none',
                  fontWeight: 600,
                  '&:hover': {
                    textDecoration: 'underline',
                  },
                }}
              >
                Zarejestruj się
              </Typography>
            </Typography>
          </Box>
        </CardContent>
      </Card>
    </Box>
  );
};

export default LoginPage;
