import React from 'react';
import { ArrowLeft, Menu } from 'lucide-react';
import ambujaHeroRef from '../../assets/ambuja/ambuja_landing.webp';

interface AmbujaUIProps {
    children?: React.ReactNode;
}

export const AmbujaUI: React.FC<AmbujaUIProps> = ({ children }) => {
    return (
        <div className="relative w-full min-h-screen font-sans overflow-x-hidden overflow-y-auto text-white bg-black">
            {/* Background Image Layer - Fixed to cover detailed hero section */}
            <div
                className="fixed inset-0 bg-cover bg-center bg-no-repeat z-0"
                style={{
                    backgroundImage: `url(${ambujaHeroRef})`,
                    backgroundPosition: 'center center' // Ensure the building is centered
                }}
            >
                {/* Gradient Overlay for text readability */}
                <div className="absolute inset-0 bg-gradient-to-r from-black/70 via-black/40 to-transparent"></div>
                <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-black/50"></div>
            </div>

            {/* Header */}
            <header className="relative z-50 flex items-center justify-between px-6 md:px-16 py-6 border-b border-white/10 backdrop-blur-md pointer-events-auto">
                {/* Logo Area */}
                <div className="flex items-center gap-4">
                    <button
                        onClick={() => window.location.href = '/'}
                        className="p-2 rounded-lg hover:bg-white/10 text-white transition-all cursor-pointer group flex items-center gap-2"
                        title="Back to Home"
                    >
                        <ArrowLeft className="group-hover:-translate-x-1 transition-transform" />
                    </button>
                    <h1 className="text-xl md:text-3xl font-bold tracking-tight text-white drop-shadow-lg cursor-pointer whitespace-nowrap">
                        Ambuja Neotia
                    </h1>
                </div>

                <nav className="hidden xl:flex items-center gap-6 text-xs font-medium tracking-widest uppercase">
                    {['About Us', 'Our Business', 'Media', 'Investors', 'Sustainability', 'CSR', 'Career', 'Gallery', 'Contact'].map((item) => (
                        <a key={item} href="#" className="hover:text-[#fbaf17] transition-colors drop-shadow-md">{item}</a>
                    ))}
                </nav>

                <div className="md:hidden text-white">
                    <Menu size={28} />
                </div>
            </header>

            {/* Main Content */}
            <main className="relative z-10 flex flex-col justify-center min-h-[calc(100vh-100px)] px-6 md:px-16 py-12 md:py-20">
                <div className="max-w-4xl space-y-6 animate-fade-in-up">
                    <h2 className="text-4xl sm:text-6xl md:text-7xl lg:text-8xl font-serif font-medium leading-[1.1] md:leading-tight drop-shadow-2xl">
                        Crafting Memorable <br />
                        <span className="italic">Experiences</span>
                    </h2>

                    <p className="text-base md:text-xl text-white/90 max-w-xl font-light leading-relaxed drop-shadow-md">
                        Discover a world where luxury meets nature. Explore our exclusive properties designed for those who appreciate the finer things in life.
                    </p>

                    <div className="pt-8 flex flex-col sm:flex-row gap-4">
                        <button className="bg-[#fbaf17] hover:bg-[#e59e15] text-black font-semibold text-base md:text-lg px-6 md:px-8 py-3 rounded-md shadow-lg transition-all transform hover:-translate-y-1 flex items-center justify-center gap-2 w-full sm:w-fit">
                            Enquire Now <ArrowLeft size={20} className="rotate-180" />
                        </button>

                        <button className="border border-white/30 hover:bg-white/10 text-white font-medium text-base md:text-lg px-6 md:px-8 py-3 rounded-md backdrop-blur-md transition-colors w-full sm:w-fit">
                            View Gallery
                        </button>
                    </div>
                </div>
            </main>

            {/* "Enquire Now" Side Tab (Visual element from reference) */}
            <div className="hidden lg:block fixed right-0 top-1/2 -translate-y-1/2 z-40">
                <button className="bg-[#fbaf17] text-black font-bold text-sm py-4 px-1 rounded-l-md shadow-lg transform rotate-180 writing-vertical-rl hover:bg-[#e59e15] transition-colors tracking-widest uppercase">
                    Enquire Now
                </button>
            </div>

            {/* Children injection point for Agent Widget */}
            {children}

            <style dangerouslySetInnerHTML={{
                __html: `
          .writing-vertical-rl {
             writing-mode: vertical-rl;
          }
          @keyframes fade-in-up {
             from { opacity: 0; transform: translateY(20px); }
             to { opacity: 1; transform: translateY(0); }
          }
          .animate-fade-in-up {
             animation: fade-in-up 1s ease-out forwards;
          }
        `
            }} />

        </div>
    );
};
