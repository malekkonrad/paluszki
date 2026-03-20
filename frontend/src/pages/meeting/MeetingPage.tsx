import { useState, useEffect, useCallback } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Box, Snackbar, Alert } from '@mui/material';
import { useAuth } from '../../hooks/useAuth';
import { useWebRTC } from '../../hooks/useWebRTC';
import { useDebugStream } from '../../hooks/useDebugStream';
import VideoGrid from './VideoGrid';
import ChatPanel from './ChatPanel';
import MeetingControls from './MeetingControls';
import WaitingRoom from './WaitingRoom';
import WebSocketService from '../../api/ws/websocketService';
import MeetingService from '../../api/services/meetingService';
import type { IChatMessage } from '../../api/interfaces/chat';
import type { IParticipant } from '../../api/interfaces/meeting';

const MeetingPage = () => {
  const { code } = useParams<{ code: string }>();
  const { user, token } = useAuth();
  const navigate = useNavigate();

  const {
    localStream,
    remoteStreams,
    peerNames,
    isMuted,
    isCameraOff,
    toggleMute,
    toggleCamera,
    startLocalStream,
    stopLocalStream,
  } = useWebRTC({
    meetingCode: code || '',
    token: token || '',
    userId: user?.id || '',
  });

  const { debugStream, isDebugActive, toggleDebug } = useDebugStream(code || '');

  const [messages, setMessages] = useState<IChatMessage[]>([]);
  const [waitingParticipants, setWaitingParticipants] = useState<IParticipant[]>([]);
  const [isHost, setIsHost] = useState(false);
  const [isWaiting, setIsWaiting] = useState(false);
  const [snackbar, setSnackbar] = useState<{ open: boolean; message: string; severity: 'success' | 'info' | 'error' }>({
    open: false,
    message: '',
    severity: 'info',
  });

  useEffect(() => {
    if (!code || !token) return;

    const initMeeting = async () => {
      try {
        const meeting = await MeetingService.getByCode(code);
        setIsHost(meeting.hostId === user?.id);

        const myParticipant = meeting.participants.find(p => p.userId === user?.id);
        if (myParticipant?.status === 'waiting') {
          setIsWaiting(true);
        }

        setWaitingParticipants(meeting.participants.filter(p => p.status === 'waiting'));
      } catch {
        // Backend not available yet, simulate as host
        setIsHost(true);
      }

      try {
        await startLocalStream();
      } catch {
        setSnackbar({
          open: true,
          message: 'Nie udało się pobrać dostępu do kamery/mikrofonu',
          severity: 'error',
        });
      }
    };

    initMeeting();

    return () => {
      stopLocalStream();
    };
  }, [code, token]);

  // Listen for WS chat messages & participant events
  useEffect(() => {
    if (!code) return;

    const ws = WebSocketService.getInstance();

    const unsubChat = ws.on('chat_message', (msg) => {
      const payload = msg.payload as { content: string; senderName: string; senderId?: string };
      const chatMsg: IChatMessage = {
        id: Date.now().toString(),
        meetingCode: code,
        senderId: msg.senderId || payload.senderId || '',
        senderName: payload.senderName,
        content: payload.content,
        timestamp: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, chatMsg]);
    });

    const unsubApproved = ws.on('participant_approved', (msg) => {
      const payload = msg.payload as { userId: string };
      if (payload.userId === user?.id) {
        setIsWaiting(false);
      }
      setWaitingParticipants((prev) => prev.filter(p => p.userId !== payload.userId));
    });

    const unsubRejected = ws.on('participant_rejected', (msg) => {
      const payload = msg.payload as { userId: string };
      if (payload.userId === user?.id) {
        navigate('/');
        setSnackbar({ open: true, message: 'Twoja prośba o dołączenie została odrzucona.', severity: 'error' });
      }
      setWaitingParticipants((prev) => prev.filter(p => p.userId !== payload.userId));
    });

    const unsubJoined = ws.on('participant_joined', (msg) => {
      const payload = msg.payload as { userId: string; firstName: string; lastName: string; status?: string };
      if (payload.status === 'waiting') {
        setWaitingParticipants((prev) => [
          ...prev,
          {
            userId: payload.userId,
            firstName: payload.firstName,
            lastName: payload.lastName,
            status: 'waiting' as const,
            joinedAt: new Date().toISOString(),
            isHost: false,
          },
        ]);
      }
    });

    return () => {
      unsubChat();
      unsubApproved();
      unsubRejected();
      unsubJoined();
    };
  }, [code, user?.id, navigate]);

  const handleSendMessage = useCallback((content: string) => {
    if (!user || !code) return;

    const ws = WebSocketService.getInstance();
    ws.sendChat(content, `${user.firstName} ${user.lastName}`);

    // Add local message immediately
    const chatMsg: IChatMessage = {
      id: Date.now().toString(),
      meetingCode: code,
      senderId: user.id,
      senderName: `${user.firstName} ${user.lastName}`,
      content,
      timestamp: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, chatMsg]);
  }, [user, code]);

  const handleApprove = useCallback(async (userId: string) => {
    if (!code) return;
    try {
      await MeetingService.approveParticipant(code, userId);
    } catch {
      // Fallback: remove from waiting list locally
    }
    setWaitingParticipants((prev) => prev.filter(p => p.userId !== userId));
  }, [code]);

  const handleReject = useCallback(async (userId: string) => {
    if (!code) return;
    try {
      await MeetingService.rejectParticipant(code, userId);
    } catch {
      // Fallback
    }
    setWaitingParticipants((prev) => prev.filter(p => p.userId !== userId));
  }, [code]);

  const handleScreenShare = useCallback(async () => {
    try {
      await navigator.mediaDevices.getDisplayMedia({ video: true });
      setSnackbar({ open: true, message: 'Udostępnianie ekranu aktywne', severity: 'info' });
    } catch {
      setSnackbar({ open: true, message: 'Nie udało się udostępnić ekranu', severity: 'error' });
    }
  }, []);

  const handleEndCall = useCallback(() => {
    stopLocalStream();
    const ws = WebSocketService.getInstance();
    ws.disconnect();
    navigate('/');
  }, [stopLocalStream, navigate]);

  const handleCopyLink = useCallback(() => {
    navigator.clipboard.writeText(window.location.href);
    setSnackbar({ open: true, message: 'Link skopiowany do schowka', severity: 'success' });
  }, []);

  // If waiting for approval
  if (isWaiting) {
    return (
      <WaitingRoom
        isHost={false}
        waitingParticipants={[]}
        onApprove={() => {}}
        onReject={() => {}}
        isWaiting
      />
    );
  }

  const currentUserName = user ? `${user.firstName} ${user.lastName}` : 'Ty';

  return (
    <Box
      sx={{
        height: '100vh',
        display: 'flex',
        flexDirection: 'column',
        background: 'linear-gradient(135deg, #0A0E1A 0%, #111827 100%)',
        overflow: 'hidden',
      }}
    >
      {/* Main content */}
      <Box
        sx={{
          flex: 1,
          display: 'flex',
          flexDirection: { xs: 'column', md: 'row' },
          overflow: 'hidden',
          pt: '64px',
        }}
      >
        {/* Chat Panel - Left side */}
        <Box
          sx={{
            order: { xs: 2, md: 1 },
            height: { xs: '40%', md: '100%' },
            flexShrink: 0,
            p: 1.5,
          }}
        >
          <ChatPanel
            messages={messages}
            onSendMessage={handleSendMessage}
            currentUserId={user?.id || ''}
          />
        </Box>

        {/* Video Area - Right side */}
        <Box
          sx={{
            flex: 1,
            order: { xs: 1, md: 2 },
            display: 'flex',
            flexDirection: 'column',
            overflow: 'hidden',
          }}
        >
          <VideoGrid
            localStream={localStream}
            remoteStreams={remoteStreams}
            peerNames={peerNames}
            isCameraOff={isCameraOff}
            isMuted={isMuted}
            debugStream={debugStream}
            isDebugActive={isDebugActive}
            currentUserName={currentUserName}
          />

          {/* Controls */}
          <Box
            sx={{
              borderTop: '1px solid rgba(255, 255, 255, 0.06)',
              bgcolor: 'rgba(10, 14, 26, 0.8)',
              backdropFilter: 'blur(12px)',
            }}
          >
            <MeetingControls
              isMuted={isMuted}
              isCameraOff={isCameraOff}
              isDebugActive={isDebugActive}
              onToggleMute={toggleMute}
              onToggleCamera={toggleCamera}
              onToggleDebug={toggleDebug}
              onScreenShare={handleScreenShare}
              onEndCall={handleEndCall}
              onCopyLink={handleCopyLink}
            />
          </Box>
        </Box>
      </Box>

      {/* Waiting room for host */}
      <WaitingRoom
        isHost={isHost}
        waitingParticipants={waitingParticipants}
        onApprove={handleApprove}
        onReject={handleReject}
      />

      {/* Snackbar for notifications */}
      <Snackbar
        open={snackbar.open}
        autoHideDuration={4000}
        onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
        anchorOrigin={{ vertical: 'bottom', horizontal: 'center' }}
      >
        <Alert
          onClose={() => setSnackbar((prev) => ({ ...prev, open: false }))}
          severity={snackbar.severity}
          variant="filled"
          sx={{ borderRadius: 2 }}
        >
          {snackbar.message}
        </Alert>
      </Snackbar>
    </Box>
  );
};

export default MeetingPage;
