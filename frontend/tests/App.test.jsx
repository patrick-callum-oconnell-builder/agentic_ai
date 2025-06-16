import { describe, it, beforeEach, vi, expect } from 'vitest';
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import App from '../src/App.jsx';

// Mock scrollIntoView for jsdom
window.HTMLElement.prototype.scrollIntoView = vi.fn();

// Mock react-markdown globally for all tests
vi.mock('react-markdown', () => ({
  default: ({ children }) => <div data-testid="markdown">{children}</div>,
}));

describe('App Component', () => {
  beforeEach(() => {
    // Reset fetch mock before each test
    global.fetch = vi.fn();
  });

  it('renders the chat interface', () => {
    render(<App />);
    expect(screen.getByText('AI Personal Trainer')).toBeInTheDocument();
    expect(screen.getByPlaceholderText('Type your message...')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send/i })).toBeInTheDocument();
  });

  it('sends a message and displays the response', async () => {
    global.fetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ response: 'Test response' })
    });
    render(<App />);
    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);
    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledWith(
        'http://localhost:8000/api/chat',
        expect.objectContaining({
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: expect.stringContaining('Hello')
        })
      );
    });
    expect(await screen.findByText('Test response')).toBeInTheDocument();
  });

  it('handles API errors gracefully', async () => {
    global.fetch.mockRejectedValueOnce(new Error('API Error'));
    render(<App />);
    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    fireEvent.change(input, { target: { value: 'Hello' } });
    fireEvent.click(sendButton);
    expect(await screen.findByText('Sorry, I encountered an error. Please try again.')).toBeInTheDocument();
  });

  it('maintains chat history during conversation', async () => {
    const user = userEvent.setup();
    global.fetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ response: 'First response' })
    });
    global.fetch.mockResolvedValueOnce({
      json: () => Promise.resolve({ response: 'Second response' })
    });
    render(<App />);
    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    await user.type(input, 'First message');
    await user.click(sendButton);
    await waitFor(() => {
      expect(screen.getByText('First response')).toBeInTheDocument();
    });
    await user.type(input, 'Second message');
    await user.click(sendButton);
    await waitFor(() => {
      expect(screen.getByText('Second response')).toBeInTheDocument();
    });
    expect(screen.getByText('First message')).toBeInTheDocument();
    expect(screen.getByText('First response')).toBeInTheDocument();
    expect(screen.getByText('Second message')).toBeInTheDocument();
    expect(screen.getByText('Second response')).toBeInTheDocument();
  });

  it('prevents sending empty messages', async () => {
    render(<App />);
    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    fireEvent.change(input, { target: { value: '   ' } });
    fireEvent.click(sendButton);
    expect(global.fetch).not.toHaveBeenCalled();
  });

  it('handles rapid consecutive messages and preserves order', async () => {
    const user = userEvent.setup();
    // Set up fetch to resolve in order
    global.fetch
      .mockResolvedValueOnce({ json: () => Promise.resolve({ response: 'Response 1' }) })
      .mockResolvedValueOnce({ json: () => Promise.resolve({ response: 'Response 2' }) })
      .mockResolvedValueOnce({ json: () => Promise.resolve({ response: 'Response 3' }) });
    render(<App />);
    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    await user.type(input, 'Message 1');
    await user.click(sendButton);
    await user.type(input, 'Message 2');
    await user.click(sendButton);
    await user.type(input, 'Message 3');
    await user.click(sendButton);
    // Wait for all responses
    expect(await screen.findByText('Response 1')).toBeInTheDocument();
    expect(await screen.findByText('Response 2')).toBeInTheDocument();
    expect(await screen.findByText('Response 3')).toBeInTheDocument();
    // Check order in the DOM
    const allMessages = screen.getAllByTestId('markdown');
    expect(allMessages[1]).toHaveTextContent('Response 1');
    expect(allMessages[3]).toHaveTextContent('Response 2');
    expect(allMessages[5]).toHaveTextContent('Response 3');
  });

  it('recovers from an error and can send messages after', async () => {
    const user = userEvent.setup();
    // First call fails, second call succeeds
    global.fetch
      .mockRejectedValueOnce(new Error('API Error'))
      .mockResolvedValueOnce({ json: () => Promise.resolve({ response: 'Recovered response' }) });
    render(<App />);
    const input = screen.getByPlaceholderText('Type your message...');
    const sendButton = screen.getByRole('button', { name: /send/i });
    await user.type(input, 'Failing message');
    await user.click(sendButton);
    expect(await screen.findByText('Sorry, I encountered an error. Please try again.')).toBeInTheDocument();
    await user.type(input, 'Recovery message');
    await user.click(sendButton);
    expect(await screen.findByText('Recovered response')).toBeInTheDocument();
  });
}); 