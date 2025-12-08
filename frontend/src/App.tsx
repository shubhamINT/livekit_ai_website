import React, { useEffect, useState } from 'react';
import {
  LiveKitRoom,
  RoomAudioRenderer,
  ControlBar,
  useTracks,
  useTranscriptions,
  TrackLoop,
  ParticipantTile,
} from '@livekit/components-react';
import '@livekit/components-styles';
import { Track } from 'livekit-client';

// 1. Configuration
const LIVEKIT_URL = 'wss://aiewebsitetest-4ewipk42.livekit.cloud'; // Replace with your actual LiveKit WebSocket URL
const TOKEN_ENDPOINT = 'http://localhost:8000/api/getToken'; // Your local backend endpoint

export default function App() {
  const [token, setToken] = useState('');

  // 2. Fetch the token from your backend
  useEffect(() => {
    const fetchToken = async () => {
      try {
        // We assume your backend expects a room name and participant identity
        const response = await fetch(`${TOKEN_ENDPOINT}?room=my-room&identity=user-1`, {
          method: 'GET',
        });
        const token = await response.text();
        console.log('Token response:', token);
        setToken(token);
      } catch (error) {
        console.error('Error fetching token:', error);
      }
    };

    fetchToken();
  }, []);

  if (!token) {
    return <div>Loading LiveKit...</div>;
  }

  // 3. Connect to the Room
  return (
    <LiveKitRoom
      video={true}
      audio={true}
      token={token}
      serverUrl={LIVEKIT_URL}
      // Use the new simplified connection logic
      connect={true}
      data-lk-theme="default"
      style={{ height: '100vh', display: 'flex', flexDirection: 'column' }}
    >
      <div style={{ flex: 1, display: 'flex' }}>
        {/* Video Grid Area */}
        <div style={{ flex: 3 }}>
          <VideoGrid />
        </div>

        {/* Transcription / Chat Area */}
        <div style={{ flex: 1, borderLeft: '1px solid #333', background: '#111', padding: '1rem' }}>
          <h3>Transcriptions</h3>
          <TranscriptionView />
        </div>
      </div>

      {/* Basic Controls (Mute, Video, etc.) */}
      <ControlBar />
      
      {/* Renders incoming audio (essential for hearing others) */}
      <RoomAudioRenderer />
    </LiveKitRoom>
  );
}

// 4. Component to Render Video Tiles
function VideoGrid() {
  const tracks = useTracks([Track.Source.Camera, Track.Source.ScreenShare]);

  return (
    <TrackLoop tracks={tracks}>
      <ParticipantTile />
    </TrackLoop>
  );
}

// 5. Component to Handle Real-time Transcription
function TranscriptionView() {
  // The useTranscriptions hook automatically listens for transcription events
  const transcriptionSegments = useTranscriptions();

  return (
    <div style={{ overflowY: 'auto', maxHeight: '80vh', display: 'flex', flexDirection: 'column', gap: '8px' }}>
      {transcriptionSegments.length === 0 && <p style={{ color: '#888' }}>Waiting for speech...</p>}
      
      {transcriptionSegments.map((segment, index) => (
        <div 
          key={index} 
          style={{ 
            background: '#222', 
            padding: '8px', 
            borderRadius: '6px',
            color: 'white'
          }}
        >
          <div style={{ fontSize: '0.8rem', color: '#aaa', marginBottom: '4px' }}>
            {segment.participant?.identity || 'Unknown'} 
            {segment.final ? '' : ' (speaking...)'}
          </div>
          <div>{segment.text}</div>
        </div>
      ))}
    </div>
  );
}