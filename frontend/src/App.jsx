import React, { useState, useRef, useEffect } from 'react';
import { 
  Box, 
  Container, 
  TextField, 
  Button, 
  Paper, 
  Typography,
  CircularProgress,
  ThemeProvider,
  createTheme
} from '@mui/material';
import SendIcon from '@mui/icons-material/Send';
import ReactMarkdown from 'react-markdown';

// Configure console logging
const log = {
  info: (...args) => console.log('%c[INFO]', 'color: #2196f3', ...args),
  error: (...args) => console.error('%c[ERROR]', 'color: #f44336', ...args),
  warn: (...args) => console.warn('%c[WARN]', 'color: #ff9800', ...args),
  debug: (...args) => console.debug('%c[DEBUG]', 'color: #4caf50', ...args)
};

const theme = createTheme({
  palette: {
    primary: {
      main: '#2196f3',
    },
    background: {
      default: '#f5f5f5',
    },
  },
});

// Simple three dots animation component
function ThinkingDots() {
  return (
    <Box sx={{ display: 'flex', justifyContent: 'center', alignItems: 'center', height: 32 }}>
      <span style={{ fontSize: 32, letterSpacing: 2 }}>
        <span className="dot">.</span>
        <span className="dot" style={{ animationDelay: '0.2s' }}>.</span>
        <span className="dot" style={{ animationDelay: '0.4s' }}>.</span>
      </span>
      <style>{`
        .dot {
          animation: blink 1s infinite;
          opacity: 0.3;
        }
        @keyframes blink {
          0%, 80%, 100% { opacity: 0.3; }
          40% { opacity: 1; }
        }
      `}</style>
    </Box>
  );
}

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isThinking, setIsThinking] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    // Normalize the user message
    const userMessage = {
        role: 'user',
        content: input.trim()
    };
    
    log.info('Sending message:', userMessage);
    
    // Update UI state
    setMessages(prev => [...prev, userMessage]);
    setInput('');
    setIsLoading(true);
    setIsThinking(false);

    try {
        log.debug('Making API request to /api/chat');
        const response = await fetch('http://localhost:8000/api/chat', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                messages: [{
                    role: userMessage.role.toLowerCase(),
                    content: userMessage.content.trim()
                }]
            }),
        });

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        const data = await response.json();
        log.info('Received response:', data);
        
        // Split assistant messages if there are multiple (intent + outcome)
        let assistantMessages = [];
        if (data.response.includes('[TOOL RESULT]:')) {
          // If backend includes tool result as a message, split on it
          const [intent, ...rest] = data.response.split('[TOOL RESULT]:');
          if (intent.trim()) {
            assistantMessages.push({ role: 'assistant', content: intent.trim() });
          }
          if (rest.length > 0) {
            // The next message(s) are the tool result and follow-up
            const toolResultAndFollowup = rest.join('[TOOL RESULT]:').split('\n').filter(Boolean);
            if (toolResultAndFollowup.length > 0) {
              // Show thinking animation before the follow-up
              setIsThinking(true);
              // Add the tool result as a hidden message (not shown to user)
              // Add the follow-up as the next assistant message
              setTimeout(() => {
                setMessages(prev => [...prev, { role: 'assistant', content: toolResultAndFollowup.join('\n').trim() }]);
                setIsThinking(false);
                setIsLoading(false);
              }, 1200); // Simulate thinking delay
              return;
            }
          }
        }
        // If not a tool result split, just add the message
        setMessages(prev => [...prev, ...assistantMessages.length ? assistantMessages : [{ role: 'assistant', content: data.response.trim() }]]);
        setIsThinking(false);
    } catch (error) {
        log.error('Error in chat request:', error);
        setMessages(prev => [...prev, { 
            role: 'assistant', 
            content: 'Sorry, I encountered an error. Please try again.' 
        }]);
        setIsThinking(false);
    } finally {
        setIsLoading(false);
    }
};

  const handleShutdown = async () => {
    try {
      log.info('Initiating server shutdown');
      const response = await fetch('http://localhost:8000/api/shutdown', {
        method: 'POST',
      });
      const data = await response.json();
      log.info('Shutdown response:', data);
      alert(data.message);
      window.close();
    } catch (error) {
      log.error('Failed to shut down server:', error);
      alert('Failed to shut down the server.');
    }
  };

  return (
    <ThemeProvider theme={theme}>
      <Container maxWidth="md" sx={{ height: '100vh', py: 4 }}>
        <Paper 
          elevation={3} 
          sx={{ 
            height: '100%', 
            display: 'flex', 
            flexDirection: 'column',
            bgcolor: 'background.default'
          }}
        >
          <Box sx={{ p: 2, borderBottom: 1, borderColor: 'divider', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <Typography variant="h5" component="h1" gutterBottom>
              AI Personal Trainer
            </Typography>
            <Button variant="outlined" color="error" onClick={handleShutdown}>
              Shutdown
            </Button>
          </Box>

          <Box sx={{ 
            flex: 1, 
            overflow: 'auto', 
            p: 2,
            display: 'flex',
            flexDirection: 'column',
            gap: 2
          }}>
            {messages.map((message, index) => (
              <Box
                key={index}
                sx={{
                  display: 'flex',
                  justifyContent: message.role === 'user' ? 'flex-end' : 'flex-start',
                }}
              >
                <Paper
                  elevation={1}
                  sx={{
                    p: 2,
                    maxWidth: '70%',
                    bgcolor: message.role === 'user' ? 'primary.main' : 'white',
                    color: message.role === 'user' ? 'white' : 'text.primary',
                  }}
                >
                  <ReactMarkdown>
                    {message.content}
                  </ReactMarkdown>
                </Paper>
              </Box>
            ))}
            {isLoading && (
              <Box sx={{ display: 'flex', justifyContent: 'center' }}>
                <CircularProgress size={24} />
              </Box>
            )}
            {isThinking && (
              <ThinkingDots />
            )}
            <div ref={messagesEndRef} />
          </Box>

          <Box 
            component="form" 
            onSubmit={handleSubmit}
            sx={{ 
              p: 2, 
              borderTop: 1, 
              borderColor: 'divider',
              display: 'flex',
              gap: 1
            }}
          >
            <TextField
              fullWidth
              variant="outlined"
              placeholder="Type your message..."
              value={input}
              onChange={(e) => setInput(e.target.value)}
              disabled={isLoading}
            />
            <Button
              type="submit"
              variant="contained"
              color="primary"
              disabled={isLoading || !input.trim()}
              endIcon={<SendIcon />}
            >
              Send
            </Button>
          </Box>
        </Paper>
      </Container>
    </ThemeProvider>
  );
}

export default App;
