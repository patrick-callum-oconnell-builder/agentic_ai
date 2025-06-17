import React from 'react';
import Chat from './components/Chat';
import './App.css';

const App: React.FC = () => {
  return (
    <div className="App">
      <header className="App-header">
        <div className="container">
          <h1>
            <span className="text-accent">AI</span> Personal Trainer
          </h1>
        </div>
      </header>
      <main className="App-main">
        <Chat />
      </main>
    </div>
  );
};

export default App; 