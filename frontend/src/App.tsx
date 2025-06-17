import React, { useState } from 'react';
import Chat from './components/Chat';
import KnowledgeGraph from './components/KnowledgeGraph';
import './App.css';

export interface Message {
  role: 'user' | 'assistant';
  content: string;
  timestamp: Date;
}

const KnowledgeGraphTab: React.FC = () => (
  <div className="kg-graph-area">
    <KnowledgeGraph />
  </div>
);

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'kg'>('chat');
  const [messages, setMessages] = useState<Message[]>([]);

  return (
    <div className="App">
      <header className="App-header">
        <div className="container">
          <h1>
            <span className="text-accent">AI</span> Personal Trainer
          </h1>
        </div>
      </header>
      <div className="centered-content">
        <div className="main-layout">
          <aside className="sidebar-tabs">
            <button
              className={activeTab === 'chat' ? 'side-tab active' : 'side-tab'}
              onClick={() => setActiveTab('chat')}
              aria-label="Agent Chat"
            >
              <span role="img" aria-label="Chat">💬</span> Agent Chat
            </button>
            <button
              className={activeTab === 'kg' ? 'side-tab active' : 'side-tab'}
              onClick={() => setActiveTab('kg')}
              aria-label="Knowledge Graph"
            >
              <span role="img" aria-label="Graph">🧠</span> Knowledge Graph
            </button>
          </aside>
          <main className="App-main">
            {activeTab === 'chat' ? <Chat messages={messages} setMessages={setMessages} /> : <KnowledgeGraphTab />}
          </main>
        </div>
      </div>
    </div>
  );
};

export default App; 