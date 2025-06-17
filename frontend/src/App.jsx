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
        log.debug('Making streaming API request to /api/chat/stream');
        
        // Use streaming endpoint for real-time responses
        const response = await fetch('http://localhost:8000/api/chat/stream', {
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

        // Handle Server-Sent Events
        const reader = response.body.getReader();
        const decoder = new TextDecoder();
        
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            const chunk = decoder.decode(value);
            const lines = chunk.split('\n');
            
            for (const line of lines) {
                if (line.trim() && line.startsWith('data: ')) {
                    try {
                        const data = JSON.parse(line.slice(6)); // Remove 'data: ' prefix
                        log.info('Received streaming response:', data);
                        
                        if (data.response) {
                            // Add the response as a new assistant message
                            setMessages(prev => [...prev, { 
                                role: 'assistant', 
                                content: data.response.trim() 
                            }]);
                        }
                    } catch (parseError) {
                        log.error('Error parsing SSE data:', parseError);
                    }
                }
            }
        }
        
        setIsThinking(false);
    } catch (error) {
        log.error('Error in streaming chat request:', error);
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
