'use client';

import { useAuth } from '@/hooks/useAuth';
import { redirect } from 'next/navigation';
import { Box, CircularProgress } from '@mui/material';
import Layout from '@/components/Layout';

export default function ProtectedLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const { isAuthenticated, isLoading } = useAuth();

  if (isLoading) {
    return (
      <Box
        sx={{
          display: 'flex',
          justifyContent: 'center',
          alignItems: 'center',
          minHeight: '100vh',
          background: 'linear-gradient(135deg, #0A0E1A 0%, #1A1A2E 50%, #16213E 100%)',
        }}
      >
        <CircularProgress size={48} sx={{ color: '#7C4DFF' }} />
      </Box>
    );
  }

  if (!isAuthenticated) {
    redirect('/login');
  }

  return <Layout>{children}</Layout>;
}
