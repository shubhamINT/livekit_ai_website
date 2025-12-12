import React, { useEffect, useRef } from 'react';

export interface ChatMessage {
  id: string;
  text: string;
  sender: 'user' | 'agent';
  isInterim?: boolean;
}

interface ChatListProps {
  messages: ChatMessage[];
}

export const ChatList: React.FC<ChatListProps> = ({ messages }) => {
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div 
      className="flex-1 w-full overflow-y-auto px-4 custom-scrollbar"
      style={{ 
        maskImage: 'linear-gradient(to bottom, transparent 0%, black 5%, black 85%, transparent 100%)',
        WebkitMaskImage: 'linear-gradient(to bottom, transparent 0%, black 5%, black 85%, transparent 100%)'
      }}
    >
      <div className="max-w-2xl mx-auto flex flex-col pt-24 pb-48"> 
        {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center min-h-[50vh] space-y-4 opacity-30">
               <div className="w-16 h-1 bg-zinc-200 rounded-full" />
               <p className="text-sm text-zinc-400 font-medium">Ready for conversation</p>
            </div>
        )}

        {messages.map((msg) => {
          const isUser = msg.sender === 'user';
          const isInterim = msg.isInterim;
          
          return (
            <div 
              key={msg.id} 
              className={`flex w-full mb-8 ${isUser ? 'justify-end' : 'justify-start'}`}
            >
              <div 
                className={`
                  relative max-w-[85%] px-7 py-5 text-[16px] leading-7 rounded-[32px]
                  border shadow-[0_2px_10px_rgba(0,0,0,0.02)] transition-all duration-300
                  ${isInterim ? 'opacity-80 scale-[0.99]' : 'opacity-100 scale-100 animate-fade-in-up'}
                  
                  /* --- COLOR LOGIC --- */
                  /* USER = BLUE (Indigo) | AI = RED (Rose) */
                  ${isUser 
                    ? `
                        bg-gradient-to-tr from-indigo-50 to-white 
                        border-indigo-100
                        text-indigo-950
                        rounded-tr-none
                      `
                    : `
                        bg-gradient-to-tr from-rose-50 to-white 
                        border-rose-100
                        text-rose-950
                        rounded-tl-none
                      `
                  }
                `}
              >
                {msg.text}
              </div>
            </div>
          );
        })}
        
        <div ref={bottomRef} className="h-4" />
      </div>
    </div>
  );
};