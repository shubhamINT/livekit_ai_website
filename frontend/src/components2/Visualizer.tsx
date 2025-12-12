import React from 'react';
import { BarVisualizer } from "@livekit/components-react";
import type { TrackReferenceOrPlaceholder } from '@livekit/components-core';

interface VisualizerSectionProps {
  state: 'speaking' | 'listening' | 'connected' | 'disconnected';
  trackRef?: TrackReferenceOrPlaceholder;
}

export const VisualizerSection: React.FC<VisualizerSectionProps> = ({ state, trackRef }) => {
  // Logic: AI Speaking = Red (Rose), User Listening = Blue (Indigo)
  const isAgent = state === 'speaking';
  
  // Premium Colors: Rose for AI, Indigo for User
  const themeColor = isAgent ? '#8eed6fff' : '#7174eeff'; 
  return (
    <div className="w-[200px] flex flex-col items-center justify-center -space-y-1">
      
      {/* 1. Visualizer Bars */}
      <div className="relative w-full h-[32px] flex items-center justify-center">
         {/* Glow Effect */}
         <div 
            className="absolute inset-0 blur-[15px] opacity-30 transition-colors duration-500 pointer-events-none"
            style={{ backgroundColor: themeColor }}
         />
         
         {trackRef ? (
            <BarVisualizer
              barCount={5}
              track={trackRef}
              style={{ height: '100%', width: '100%' }}
              options={{ minHeight: 4, maxHeight: 28 }} 
            >
             <style>{`
                .lk-audio-visualizer > rect { 
                    fill: ${themeColor} !important; 
                    rx: 2px !important;
                    transition: height 0.1s ease, fill 0.5s ease;
                } 
             `}</style>
            </BarVisualizer>
         ) : (
           <div className="flex gap-1 items-center justify-center h-full opacity-30">
              <div className="w-1 h-1 bg-zinc-500 rounded-full" />
              <div className="w-1 h-1 bg-zinc-500 rounded-full" />
              <div className="w-1 h-1 bg-zinc-500 rounded-full" />
           </div>
         )}
      </div>
      
      {/* 2. Status Text (Centered Flex Item - No Absolute Positioning) */}
      <div className="h-[14px] flex items-center justify-center w-full">
        <span className={`
            text-[9px] uppercase tracking-[0.2em] font-bold transition-colors duration-500 text-center
            ${isAgent ? 'text-rose-600' : 'text-indigo-600'}
        `}>
          {isAgent ? 'AI Speaking' : 'Listening'}
        </span>
      </div>

    </div>
  );
};