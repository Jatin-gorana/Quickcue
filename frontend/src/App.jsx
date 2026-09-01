import React, { useState } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VoiceAssistantControlBar,
  useVoiceAssistant,
  useTranscripts,
} from '@livekit/components-react';
import { PhoneCall, PhoneOff, Activity, MessageSquare } from 'lucide-react';

export default function App() {
  const [url, setUrl] = useState('');
  const [token, setToken] = useState('');
  const [roomName, setRoomName] = useState('quickcue-room');
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  // Fetch token from local agent token server or use manual inputs
  const handleFetchTokenAndConnect = async () => {
    setLoading(true);
    setError(null);
    try {
      // If token & url are manually provided, connect directly
      if (url && token) {
        setConnected(true);
        setLoading(false);
        return;
      }

      // Try local token server helper
      const res = await fetch(`http://localhost:8080/api/token?roomName=${encodeURIComponent(roomName)}`);
      if (!res.ok) {
        throw new Error(`Token server returned status ${res.status}`);
      }
      const data = await res.json();
      if (!data.token || !data.url) {
        throw new Error("Invalid token server payload");
      }
      
      setUrl(data.url);
      setToken(data.token);
      setConnected(true);
    } catch (err) {
      console.warn("Auto-token generation notice:", err);
      if (url && token) {
        setConnected(true);
      } else {
        setError(
          "Could not auto-generate token from http://localhost:8080/api/token. " +
          "Ensure 'python agent.py token-server' is running in another terminal, or fill in LiveKit URL & Token manually."
        );
      }
    } finally {
      setLoading(false);
    }
  };

  const handleDisconnect = () => {
    setConnected(false);
  };

  return (
    <div className="container">
      <header>
        <div className="logo-badge">
          <div className="logo-icon">Q</div>
          <div>
            <h1>Quickcue</h1>
            <div className="subtitle">Hands-Free Voice Assistant Baseline</div>
          </div>
        </div>
        <div className="status-indicator">
          <div className={`dot ${connected ? 'connected' : loading ? 'connecting' : ''}`} />
          <span>{connected ? 'Live Session' : loading ? 'Connecting...' : 'Disconnected'}</span>
        </div>
      </header>

      {!connected ? (
        <div className="card">
          <h2 style={{ fontSize: '1.1rem', marginBottom: '1rem' }}>Connection & Credentials</h2>
          
          {error && (
            <div style={{ padding: '0.75rem', background: '#451A1A', border: '1px solid #7F1D1D', borderRadius: '8px', color: '#FCA5A5', marginBottom: '1rem', fontSize: '0.85rem' }}>
              {error}
            </div>
          )}

          <div className="inputs-row">
            <div className="form-group">
              <label>LiveKit Cloud WSS URL (optional if using token-server)</label>
              <input
                type="text"
                placeholder="wss://your-project.livekit.cloud"
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </div>
            <div className="form-group">
              <label>Room Name</label>
              <input
                type="text"
                value={roomName}
                onChange={(e) => setRoomName(e.target.value)}
              />
            </div>
          </div>

          <div className="form-group" style={{ marginBottom: '1.25rem' }}>
            <label>Access Token (optional if using token-server)</label>
            <input
              type="text"
              placeholder="Paste token or leave empty to fetch via token-server"
              value={token}
              onChange={(e) => setToken(e.target.value)}
            />
          </div>

          <div className="controls-bar">
            <button className="btn btn-primary" onClick={handleFetchTokenAndConnect} disabled={loading}>
              <PhoneCall size={18} />
              {loading ? 'Connecting...' : 'Connect to Voice Assistant'}
            </button>
          </div>
        </div>
      ) : (
        <LiveKitRoom
          serverUrl={url}
          token={token}
          connect={connected}
          onDisconnected={handleDisconnect}
          audio={true}
          video={false}
          className="transcript-section"
        >
          <RoomAudioRenderer />
          <VoiceAssistantSession onDisconnect={handleDisconnect} />
        </LiveKitRoom>
      )}
    </div>
  );
}

function VoiceAssistantSession({ onDisconnect }) {
  const { state } = useVoiceAssistant();
  const transcripts = useTranscripts();

  return (
    <div className="card transcript-section">
      <div className="controls-bar">
        <button className="btn btn-danger" onClick={onDisconnect}>
          <PhoneOff size={18} />
          Disconnect
        </button>
        <VoiceAssistantControlBar controls={{ leave: false }} />
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.85rem', color: 'var(--text-muted)' }}>
          <Activity size={16} color="var(--primary)" />
          <span>Status: <strong>{state || 'listening'}</strong></span>
        </div>
      </div>

      <div className="transcript-header">
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontWeight: 600 }}>
          <MessageSquare size={18} color="var(--primary)" />
          <span>Live Conversation Transcript</span>
        </div>
      </div>

      <div className="transcript-list">
        {transcripts.length === 0 ? (
          <div className="empty-state">
            <Activity size={32} color="var(--primary)" style={{ opacity: 0.6 }} />
            <p>Start speaking into your microphone.</p>
            <span style={{ fontSize: '0.8rem' }}>Quickcue will listen and respond with spoken audio.</span>
          </div>
        ) : (
          transcripts.map((t, idx) => (
            <div
              key={idx}
              className={`transcript-item ${t.participant?.isAgent ? 'agent' : 'user'}`}
            >
              <span className="speaker-label">
                {t.participant?.isAgent ? 'Quickcue Copilot' : 'Technician'}
              </span>
              <span className="speech-text">{t.text}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
