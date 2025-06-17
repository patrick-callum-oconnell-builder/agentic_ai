import React, { useState } from 'react';
import Chat from './components/Chat';
import './App.css';

const KnowledgeGraphTab: React.FC = () => (
  <div className="kg-graph-area">
    {/* The entire area is now dedicated to the knowledge graph visualization */}
    <div className="kg-placeholder">
      Knowledge Graph Visualization Area
    </div>
  </div>
);

const App: React.FC = () => {
  const [activeTab, setActiveTab] = useState<'chat' | 'kg'>('chat');

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
            {activeTab === 'chat' ? <Chat /> : <KnowledgeGraphTab />}
          </main>
        </div>
      </div>
    </div>
  );
};

export default App; 