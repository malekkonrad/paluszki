import { useState, useRef, useEffect } from 'react';
import {
  Box,
  Typography,
  TextField,
  IconButton,
  Paper,
  List,
  ListItem,
  Avatar,
  InputAdornment,
} from '@mui/material';
import {
  Send as SendIcon,
  Chat as ChatIcon,
} from '@mui/icons-material';
import type { IChatMessage } from '../../api/interfaces/chat';

interface ChatPanelProps {
  messages: IChatMessage[];
  onSendMessage: (content: string) => void;
  currentUserId: string;
}

const ChatPanel = ({ messages, onSendMessage, currentUserId }: ChatPanelProps) => {
  const [newMessage, setNewMessage] = useState('');
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSend = () => {
    if (!newMessage.trim()) return;
    onSendMessage(newMessage.trim());
    setNewMessage('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const formatTime = (timestamp: string) => {
    const date = new Date(timestamp);
    return date.toLocaleTimeString('pl-PL', { hour: '2-digit', minute: '2-digit' });
  };

  return (
    <Paper
      elevation={0}
      sx={{
        width: { xs: '100%', md: 340 },
        height: '100%',
        display: 'flex',
        flexDirection: 'column',
        bgcolor: 'rgba(17, 24, 39, 0.7)',
        backdropFilter: 'blur(12px)',
        borderRadius: 3,
        border: '1px solid rgba(255, 255, 255, 0.06)',
        overflow: 'hidden',
      }}
    >
      {/* Header */}
      <Box
        sx={{
          px: 2.5,
          py: 2,
          borderBottom: '1px solid rgba(255, 255, 255, 0.06)',
          display: 'flex',
          alignItems: 'center',
          gap: 1,
        }}
      >
        <ChatIcon sx={{ color: '#7C4DFF', fontSize: 22 }} />
        <Typography variant="h6" sx={{ fontWeight: 600, fontSize: '0.95rem' }}>
          Czat
        </Typography>
        {messages.length > 0 && (
          <Box
            sx={{
              ml: 'auto',
              bgcolor: 'rgba(124, 77, 255, 0.15)',
              color: '#B388FF',
              fontSize: '0.7rem',
              fontWeight: 600,
              px: 1,
              py: 0.25,
              borderRadius: 10,
            }}
          >
            {messages.length}
          </Box>
        )}
      </Box>

      {/* Messages list */}
      <List
        sx={{
          flex: 1,
          overflow: 'auto',
          px: 1.5,
          py: 1,
          '&::-webkit-scrollbar': {
            width: 4,
          },
          '&::-webkit-scrollbar-thumb': {
            bgcolor: 'rgba(255, 255, 255, 0.1)',
            borderRadius: 2,
          },
        }}
      >
        {messages.length === 0 && (
          <Box
            sx={{
              textAlign: 'center',
              py: 6,
            }}
          >
            <ChatIcon sx={{ fontSize: 40, color: 'rgba(255, 255, 255, 0.08)', mb: 1 }} />
            <Typography variant="body2" color="text.disabled">
              Brak wiadomości
            </Typography>
            <Typography variant="caption" color="text.disabled">
              Napisz coś, aby rozpocząć rozmowę
            </Typography>
          </Box>
        )}

        {messages.map((msg) => {
          const isOwn = msg.senderId === currentUserId;
          return (
            <ListItem
              key={msg.id}
              sx={{
                flexDirection: 'column',
                alignItems: isOwn ? 'flex-end' : 'flex-start',
                px: 0.5,
                py: 0.5,
              }}
            >
              <Box
                sx={{
                  display: 'flex',
                  alignItems: 'flex-end',
                  gap: 1,
                  flexDirection: isOwn ? 'row-reverse' : 'row',
                  maxWidth: '85%',
                }}
              >
                {!isOwn && (
                  <Avatar
                    sx={{
                      width: 28,
                      height: 28,
                      bgcolor: '#7C4DFF',
                      fontSize: '0.7rem',
                      fontWeight: 600,
                      flexShrink: 0,
                    }}
                  >
                    {msg.senderName[0].toUpperCase()}
                  </Avatar>
                )}
                <Box>
                  {!isOwn && (
                    <Typography
                      variant="caption"
                      sx={{ color: 'text.secondary', fontWeight: 500, ml: 0.5 }}
                    >
                      {msg.senderName}
                    </Typography>
                  )}
                  <Box
                    sx={{
                      bgcolor: isOwn
                        ? 'rgba(124, 77, 255, 0.2)'
                        : 'rgba(255, 255, 255, 0.05)',
                      border: isOwn
                        ? '1px solid rgba(124, 77, 255, 0.15)'
                        : '1px solid rgba(255, 255, 255, 0.04)',
                      borderRadius: isOwn
                        ? '12px 12px 4px 12px'
                        : '12px 12px 12px 4px',
                      px: 1.5,
                      py: 1,
                      mt: 0.25,
                    }}
                  >
                    <Typography variant="body2" sx={{ fontSize: '0.8125rem', wordBreak: 'break-word' }}>
                      {msg.content}
                    </Typography>
                    <Typography
                      variant="caption"
                      sx={{
                        color: 'text.disabled',
                        fontSize: '0.65rem',
                        mt: 0.5,
                        display: 'block',
                        textAlign: isOwn ? 'right' : 'left',
                      }}
                    >
                      {formatTime(msg.timestamp)}
                    </Typography>
                  </Box>
                </Box>
              </Box>
            </ListItem>
          );
        })}
        <div ref={messagesEndRef} />
      </List>

      {/* Input */}
      <Box
        sx={{
          px: 1.5,
          py: 1.5,
          borderTop: '1px solid rgba(255, 255, 255, 0.06)',
        }}
      >
        <TextField
          fullWidth
          size="small"
          placeholder="Napisz wiadomość..."
          value={newMessage}
          onChange={(e) => setNewMessage(e.target.value)}
          onKeyDown={handleKeyDown}
          multiline
          maxRows={3}
          sx={{
            '& .MuiOutlinedInput-root': {
              borderRadius: '12px',
              bgcolor: 'rgba(255, 255, 255, 0.03)',
            },
          }}
          slotProps={{
            input: {
              endAdornment: (
                <InputAdornment position="end">
                  <IconButton
                    onClick={handleSend}
                    disabled={!newMessage.trim()}
                    size="small"
                    sx={{
                      color: newMessage.trim() ? '#7C4DFF' : 'text.disabled',
                      transition: 'all 0.2s ease',
                    }}
                  >
                    <SendIcon fontSize="small" />
                  </IconButton>
                </InputAdornment>
              ),
            },
          }}
        />
      </Box>
    </Paper>
  );
};

export default ChatPanel;
