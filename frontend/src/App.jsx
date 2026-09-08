import React, { useState } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  VoiceAssistantControlBar,
  useVoiceAssistant,
  useTranscriptions,
} from '@livekit/components-react';
import { PhoneCall, PhoneOff, Activity, MessageSquare, AlertCircle } from 'lucide-react';

export default function App() {
  const [url, setUrl] = useState('');
  const [token, setToken] = useState('');
  const [roomName, setRoomName] = useState('quickcue-room');
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [showAdvanced, setShowAdvanced] = useState(false);

  const handleConnect = async () => {
    setLoading(true);
    setError(null);
    try {
      // If user provided manual inputs, connect directly
      if (url && token) {
        setConnected(true);
        setLoading(false);
        return;
      }

      // Automatically fetch room URL & Token from agent backend helper endpoint
      let res;
      try {
        res = await fetch(`/api/token?roomName=${encodeURIComponent(roomName)}`);
      } catch {
        res = await fetch(`http://localhost:8080/api/token?roomName=${encodeURIComponent(roomName)}`);
      }

      if (!res.ok) {
        throw new Error(`Token server error (status ${res.status}). Ensure python agent.py dev is running.`);
      }

      const data = await res.json();
      if (!data.token || !data.url) {
        throw new Error("Invalid token response from server.");
      }

      setUrl(data.url);
      setToken(data.token);
      setConnected(true);
    } catch (err) {
      console.warn("Auto-connect warning:", err);
      setError(
        "Could not connect to Python backend. Please make sure 'python agent.py dev' is actively running in your terminal!"
      );
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
            <div className="subtitle">Hands-Free Voice Assistant Copilot</div>
          </div>
        </div>
        <div className="status-indicator">
          <div className={`dot ${connected ? 'connected' : loading ? 'connecting' : ''}`} />
          <span>{connected ? 'Live Voice Session' : loading ? 'Connecting...' : 'Disconnected'}</span>
        </div>
      </header>

      {!connected ? (
        <div className="card" style={{ textAlign: 'center', padding: '2.5rem 1.5rem' }}>
          <h2 style={{ fontSize: '1.4rem', fontWeight: 700, marginBottom: '0.5rem' }}>
            Ready for Hands-Free Guidance
          </h2>
          <p style={{ color: 'var(--text-muted)', fontSize: '0.95rem', marginBottom: '2rem', maxWidth: '550px', margin: '0 auto 2rem' }}>
            Click below to establish a live voice link with Quickcue. Make sure <code>python agent.py dev</code> is running in your terminal.
          </p>

          {error && (
            <div style={{
              display: 'flex',
              alignItems: 'center',
              gap: '0.75rem',
              maxWidth: '600px',
              margin: '0 auto 1.5rem',
              padding: '1rem',
              background: '#451A1A',
              border: '1px solid #7F1D1D',
              borderRadius: '10px',
              color: '#FCA5A5',
              fontSize: '0.9rem',
              textAlign: 'left'
            }}>
              <AlertCircle size={22} style={{ flexShrink: 0 }} />
              <div>{error}</div>
            </div>
          )}

          <div style={{ display: 'flex', justifyContent: 'center', marginBottom: '1.5rem' }}>
            <button
              className="btn btn-primary"
              onClick={handleConnect}
              disabled={loading}
              style={{ fontSize: '1.1rem', padding: '1rem 2.5rem', borderRadius: '12px' }}
            >
              <PhoneCall size={22} />
              {loading ? 'Connecting to Agent...' : 'Start Voice Assistant'}
            </button>
          </div>

          <div style={{ marginTop: '1rem' }}>
            <button
              type="button"
              style={{ background: 'none', border: 'none', color: 'var(--text-muted)', fontSize: '0.85rem', cursor: 'pointer', textDecoration: 'underline' }}
              onClick={() => setShowAdvanced(!showAdvanced)}
            >
              {showAdvanced ? 'Hide Advanced Credentials' : 'Show Advanced Credentials (Manual Override)'}
            </button>
          </div>

          {showAdvanced && (
            <div style={{ marginTop: '1.5rem', padding: '1rem', background: 'var(--bg-accent)', borderRadius: '10px', textAlign: 'left' }}>
              <div className="inputs-row">
                <div className="form-group">
                  <label>LiveKit WSS URL</label>
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
              <div className="form-group">
                <label>Access Token</label>
                <input
                  type="text"
                  placeholder="Paste manual access token..."
                  value={token}
                  onChange={(e) => setToken(e.target.value)}
                />
              </div>
            </div>
          )}
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
  const { state, agentTranscriptions } = useVoiceAssistant();
  const transcriptions = useTranscriptions();

  const allTranscriptions = transcriptions.length > 0
    ? transcriptions
    : (agentTranscriptions || []).map((seg) => ({
        text: seg.text,
        participantInfo: { identity: 'Agent' },
      }));

  return (
    <div className="card transcript-section">
      <div className="controls-bar">
        <button className="btn btn-danger" onClick={onDisconnect}>
          <PhoneOff size={18} />
          Disconnect Session
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
        {allTranscriptions.length === 0 ? (
          <div className="empty-state">
            <Activity size={36} color="var(--primary)" style={{ opacity: 0.7 }} />
            <p style={{ fontSize: '1.1rem', fontWeight: 600 }}>Quickcue is listening...</p>
            <span style={{ fontSize: '0.85rem' }}>Speak your field or lab question into your microphone.</span>
          </div>
        ) : (
          allTranscriptions.map((t, idx) => {
            const isAgent =
              t.participantInfo?.identity?.toLowerCase().includes('agent') ||
              t.streamInfo?.attributes?.['livekit.agent.state'] !== undefined;
            return (
              <div
                key={idx}
                className={`transcript-item ${isAgent ? 'agent' : 'user'}`}
              >
                <span className="speaker-label">
                  {isAgent ? 'Quickcue Copilot' : t.participantInfo?.identity || 'Technician'}
                </span>
                <span className="speech-text">{t.text}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
