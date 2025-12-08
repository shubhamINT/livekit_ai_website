// import { useState } from 'react'
// import './App.css'
// import LiveKitModal from './compotents/LiveKitModel';

// function App() {
//   const [showSupport, setShowSupport] = useState(false);

//   const handleSupportClick = () => {
//     setShowSupport(true)
//   }

//   return (
//     <div className="app">
//       <header className="header">
//         <div className="logo">AutoZone</div>
//       </header>

//       <main>
//         <section className="hero">
//           <h1>Get the Right Parts. Right Now</h1>
//           <p>Free Next Day Delivery on Eligible Orders</p>
//           <div className="search-bar">
//             <input type="text" placeholder='Enter vehicle or part number'></input>
//             <button>Search</button>
//           </div>
//         </section>

//         <button className="support-button" onClick={handleSupportClick}>
//           Talk to an Agent!
//         </button>
//       </main>

//       {showSupport && <LiveKitModal setShowSupport={setShowSupport}/>}
//     </div>
//   )
// }

// export default App


'use client';
import { useEffect, useRef } from 'react';
import {
  ControlBar,
  RoomAudioRenderer,
  useSession,
  SessionProvider,
  useAgent,
  BarVisualizer,
} from '@livekit/components-react';
import { TokenSource, TokenSourceConfigurable } from 'livekit-client';
import type { TokenSourceFetchOptions } from 'livekit-client';
import '@livekit/components-styles';

export default function App() {
  const tokenSource: TokenSourceConfigurable = useRef(
  TokenSource.url('http://localhost:8000/api/token')
  ).current;
  const tokenOptions: TokenSourceFetchOptions = {
    roomName: 'your-room', // replace with your actual room name
    agentName: 'your-agent-name', // replace with your agent name
  };

  const session = useSession(tokenSource, tokenOptions);

  // Connect to session
  useEffect(() => {
    session.start();
    return () => {
      session.end();
    };
  }, []);

  return (
    <SessionProvider session={session}>
      <div data-lk-theme="default" style={{ height: '100vh' }}>
        {/* Your custom component with basic video agent functionality. */}
        <MyAgentView />
        {/* Controls for the user to start/stop audio and disconnect from the session */}
        <ControlBar controls={{ microphone: true, camera: false, screenShare: false }} />
        {/* The RoomAudioRenderer takes care of room-wide audio for you. */}
        <RoomAudioRenderer />
      </div>
    </SessionProvider>
  );
}

function MyAgentView() {
  const agent = useAgent();
  return (
    <div style={{ height: '350px' }}>
      <p>Agent state: {agent.state}</p>
      {/* Renders a visualizer for the agent's audio track */}
      {agent.canListen && (
        <BarVisualizer track={agent.microphoneTrack} state={agent.state} barCount={5} />
      )}
    </div>
  );
}