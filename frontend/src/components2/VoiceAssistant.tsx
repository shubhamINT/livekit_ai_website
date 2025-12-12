import React, { useEffect, useState, useMemo } from 'react';
import {
  useVoiceAssistant,
  useLocalParticipant,
  useRoomContext,
  useTranscriptions,
} from '@livekit/components-react';
import { Track, Participant } from 'livekit-client';
import { Mic, MicOff, PhoneOff } from 'lucide-react';

import { Header } from './Header';
import { VisualizerSection } from './Visualizer';
import { ChatList } from './Chatlist';
import type { ChatMessage } from './Chatlist';

interface VoiceEvent {
  id: string;
  text: string;
  final: boolean;
  participant?: Participant;
  fromParticipant?: Participant;
}

type VisualizerState = 'speaking' | 'listening' | 'connected' | 'disconnected';

function mapAgentToVisualizerState(s: string): VisualizerState {
  if (s === 'connecting') return 'connected';
  if (s === 'speaking' || s === 'listening' || s === 'connected' || s === 'disconnected') return s;
  return 'connected';
}

const VoiceAssistant: React.FC = () => {
  const { state, audioTrack: agentTrack } = useVoiceAssistant();
  const { localParticipant, microphoneTrack } = useLocalParticipant();
  const room = useRoomContext();
  const transcriptions = useTranscriptions() as unknown as VoiceEvent[];

  const [history, setHistory] = useState<ChatMessage[]>([]);
  const [isMicMuted, setIsMicMuted] = useState(false);

  // Track logic
  const userTrackRef = useMemo(() => {
    if (!localParticipant || !microphoneTrack) return undefined;
    return {
      participant: localParticipant,
      source: Track.Source.Microphone,
      publication: microphoneTrack,
    };
  }, [localParticipant, microphoneTrack]);

  const agentTrackRef = useMemo(() => {
    if (!agentTrack || !agentTrack.participant || !agentTrack.publication) return undefined;
    return {
      participant: agentTrack.participant,
      source: Track.Source.Unknown,
      publication: agentTrack.publication,
    };
  }, [agentTrack]);

  const isAgentSpeaking = state === 'speaking';
  const activeTrack = isAgentSpeaking ? agentTrackRef : userTrackRef;
  const visualizerState = mapAgentToVisualizerState(state as string);

  // Chat History Logic
  const uiMessages = useMemo(() => {
    const liveMessages: ChatMessage[] = transcriptions
      .filter(t => !t.final)
      .map(t => {
        const p = t.participant || t.fromParticipant;
        const isAgent = p?.identity?.includes('agent') || (p && p.identity !== localParticipant?.identity);
        return { id: t.id, text: t.text, sender: isAgent ? 'agent' : 'user', isInterim: true };
      });
    return [...history, ...liveMessages];
  }, [history, transcriptions, localParticipant]);

  useEffect(() => {
    transcriptions.forEach(seg => {
      if (seg.final) {
        setHistory(prev => {
          if (prev.some(m => m.id === seg.id)) return prev;
          const p = seg.participant || seg.fromParticipant;
          const isAgent = p?.identity?.includes('agent') || (p && p.identity !== localParticipant?.identity);
          return [...prev, { id: seg.id, text: seg.text, sender: isAgent ? 'agent' : 'user', isInterim: false }];
        });
      }
    });
  }, [transcriptions, localParticipant]);

  const toggleMic = () => {
    if (!localParticipant) return;
    localParticipant.setMicrophoneEnabled(!isMicMuted);
    setIsMicMuted(!isMicMuted);
  };

  return (
    <div className="fixed inset-0 w-full h-[100dvh] bg-zinc-50 text-zinc-900 overflow-hidden flex flex-col font-sans">
      
      {/* 1. Header (Minimal, Top Left) */}
      <Header status={visualizerState} />

      {/* 2. Chat List (NOW TAKES FULL HEIGHT) */}
      <div className="flex-1 w-full relative overflow-hidden flex flex-col">
        {/* We add a gradient mask at the bottom so text fades nicely behind the dock */}
        <ChatList messages={uiMessages} />
      </div>

      {/* 3. THE DYNAMIC BOTTOM DOCK */}
      <div className="fixed bottom-8 left-0 right-0 flex justify-center z-50 pointer-events-none">
        <div 
          className="
            flex items-center gap-4 px-3 py-3 rounded-[28px] pointer-events-auto
            bg-white/90 backdrop-blur-xl 
            border border-white/40 shadow-[0_20px_40px_rgba(0,0,0,0.1)]
            transition-all duration-500
          "
        >
           
          {/* Left: Mic Toggle */}
          <button 
            onClick={toggleMic}
            className={`
              w-12 h-12 flex items-center justify-center rounded-full transition-all duration-300 shadow-sm
              ${isMicMuted 
                ? 'bg-zinc-100 text-zinc-400 hover:bg-zinc-200' 
                : 'bg-zinc-900 text-white hover:bg-zinc-800 hover:scale-105'}
            `}
          >
            {isMicMuted ? <MicOff size={20}/> : <Mic size={20}/>}
          </button>

          {/* Center: The Visualizer (Divider Lines included) */}
          <div className="h-8 w-[1px] bg-zinc-200 mx-2" />
          
          <VisualizerSection 
            state={visualizerState}
            trackRef={activeTrack}
          />
          
          <div className="h-8 w-[1px] bg-zinc-200 mx-2" />

          {/* Right: End Call */}
          <button 
            onClick={() => room?.disconnect()}
            className="w-12 h-12 flex items-center justify-center rounded-full bg-rose-50 text-rose-500 hover:bg-rose-100 hover:scale-105 transition-all duration-300"
          >
            <PhoneOff size={20}/>
          </button>

        </div>
      </div>
    </div>
  );
};

export default VoiceAssistant;