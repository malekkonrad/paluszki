'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import {
  AppBar,
  Toolbar,
  Typography,
  IconButton,
  Avatar,
  Menu,
  MenuItem,
  ListItemIcon,
  ListItemText,
  Box,
  Tooltip,
} from '@mui/material';
import {
  VideoCameraFront as VideoIcon,
  Logout as LogoutIcon,
  Dashboard as DashboardIcon,
} from '@mui/icons-material';
import { useAuth } from '../hooks/useAuth';

const Navbar = () => {
  const { user, logout } = useAuth();
  const router = useRouter();
  const [anchorEl, setAnchorEl] = useState<null | HTMLElement>(null);

  const handleMenuOpen = (event: React.MouseEvent<HTMLElement>) => {
    setAnchorEl(event.currentTarget);
  };

  const handleMenuClose = () => {
    setAnchorEl(null);
  };

  const handleLogout = () => {
    handleMenuClose();
    logout();
    router.push('/login');
  };

  const handleDashboard = () => {
    handleMenuClose();
    router.push('/');
  };

  const getInitials = () => {
    if (!user) return '?';
    return `${user.firstName[0]}${user.lastName[0]}`.toUpperCase();
  };

  return (
    <AppBar position="fixed" elevation={0}>
      <Toolbar sx={{ px: { xs: 2, sm: 3 } }}>
        <Box
          sx={{
            display: 'flex',
            alignItems: 'center',
            gap: 1.5,
            cursor: 'pointer',
            '&:hover': { opacity: 0.85 },
            transition: 'opacity 0.2s ease',
          }}
          onClick={handleDashboard}
        >
          <VideoIcon
            sx={{
              fontSize: 32,
              color: '#7C4DFF',
              filter: 'drop-shadow(0 0 8px rgba(124, 77, 255, 0.4))',
            }}
          />
          <Typography
            variant="h5"
            sx={{
              fontWeight: 700,
              background: 'linear-gradient(135deg, #7C4DFF 0%, #00E5FF 100%)',
              backgroundClip: 'text',
              WebkitBackgroundClip: 'text',
              WebkitTextFillColor: 'transparent',
              letterSpacing: '-0.02em',
            }}
          >
            MeetFlow
          </Typography>
        </Box>

        <Box sx={{ flexGrow: 1 }} />

        {user && (
          <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
            <Typography
              variant="body2"
              sx={{
                color: 'text.secondary',
                display: { xs: 'none', sm: 'block' },
              }}
            >
              {user.firstName} {user.lastName}
            </Typography>
            <Tooltip title="Menu użytkownika">
              <IconButton onClick={handleMenuOpen} size="small">
                <Avatar
                  src={user.avatarUrl}
                  sx={{
                    width: 36,
                    height: 36,
                    bgcolor: '#7C4DFF',
                    fontSize: '0.875rem',
                    fontWeight: 600,
                    border: '2px solid rgba(124, 77, 255, 0.3)',
                    transition: 'border-color 0.2s ease',
                    '&:hover': {
                      borderColor: 'rgba(124, 77, 255, 0.7)',
                    },
                  }}
                >
                  {getInitials()}
                </Avatar>
              </IconButton>
            </Tooltip>
            <Menu
              anchorEl={anchorEl}
              open={Boolean(anchorEl)}
              onClose={handleMenuClose}
              transformOrigin={{ horizontal: 'right', vertical: 'top' }}
              anchorOrigin={{ horizontal: 'right', vertical: 'bottom' }}
              slotProps={{
                paper: {
                  sx: {
                    mt: 1,
                    minWidth: 180,
                    bgcolor: 'background.paper',
                    border: '1px solid rgba(255, 255, 255, 0.06)',
                    boxShadow: '0 8px 32px rgba(0, 0, 0, 0.4)',
                  },
                },
              }}
            >
              <MenuItem onClick={handleDashboard}>
                <ListItemIcon>
                  <DashboardIcon fontSize="small" />
                </ListItemIcon>
                <ListItemText>Dashboard</ListItemText>
              </MenuItem>
              <MenuItem onClick={handleLogout}>
                <ListItemIcon>
                  <LogoutIcon fontSize="small" sx={{ color: '#FF5252' }} />
                </ListItemIcon>
                <ListItemText sx={{ color: '#FF5252' }}>Wyloguj</ListItemText>
              </MenuItem>
            </Menu>
          </Box>
        )}
      </Toolbar>
    </AppBar>
  );
};

export default Navbar;
