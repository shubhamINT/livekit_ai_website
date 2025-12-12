import React from 'react';
import { Sparkles, Activity } from 'lucide-react';

interface HeaderProps {
  status: 'speaking' | 'listening' | 'connected' | 'disconnected';
}

export const Header: React.FC<HeaderProps> = ({ status }) => {
  // Logic: AI Speaking = Red, User/Listening = Blue
  const isAgent = status === 'speaking';
  const isListening = status === 'listening';

  return (
    <div className="fixed top-6 left-6 z-50 pointer-events-none select-none">
      <div 
        className={`
          pointer-events-auto backdrop-blur-xl border shadow-sm px-4 py-2 rounded-full flex items-center gap-3 transition-all duration-500
          ${isAgent 
             ? 'bg-rose-50/80 border-rose-200/50' 
             : isListening 
                ? 'bg-indigo-50/80 border-indigo-200/50' 
                : 'bg-white/80 border-white/40'}
        `}
      >
        <div className={`
          relative flex items-center justify-center w-6 h-6 rounded-full transition-colors duration-500
          ${isAgent ? 'bg-rose-100 text-rose-500' : isListening ? 'bg-indigo-100 text-indigo-500' : 'bg-zinc-100 text-zinc-400'}
        `}>
           {isAgent ? (
             <Sparkles className="w-3.5 h-3.5 animate-pulse" />
           ) : (
             <Activity className="w-3.5 h-3.5" />
           )}
        </div>
        
        <div className="flex flex-col">
           <span className={`font-bold text-xs tracking-wider uppercase transition-colors duration-500 ${isAgent ? 'text-rose-700' : isListening ? 'text-indigo-700' : 'text-zinc-600'}`}>
             INT. AI
           </span>
           <span className="text-[9px] text-zinc-400 font-medium leading-none">
             {isAgent ? 'Transmitting' : isListening ? 'Receiving' : 'Standby'}
           </span>
        </div>
      </div>
    </div>
  );
};