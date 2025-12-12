import logging
from dotenv import load_dotenv
from livekit import rtc
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    cli,
    inference,
    room_io,
    BackgroundAudioPlayer, 
    AudioConfig,           
    BuiltinAudioClip       
)
from livekit.plugins import noise_cancellation, silero, openai
from livekit.plugins.turn_detector.multilingual import MultilingualModel
from agents.web_agent import Webagent
from livekit.plugins.openai import realtime
from openai.types.beta.realtime.session import TurnDetection
import os


logger = logging.getLogger("agent")
load_dotenv(override=True)

# initialize the agent
server = AgentServer(
    api_key=os.getenv("LIVEKIT_API_KEY"),
    api_secret=os.getenv("LIVEKIT_API_SECRET"),
    ws_url=os.getenv("LIVEKIT_URL"),
)

@server.rtc_session()
async def my_agent(ctx: JobContext):

    # session = AgentSession(
    #     stt=inference.STT(model="assemblyai/universal-streaming", language="en"),
    #     llm=inference.LLM(model="openai/gpt-4.1-mini"),
    #     tts=inference.TTS(model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
    #     turn_detection=MultilingualModel(),
    #     vad=silero.VAD.load(min_speech_duration=0.3, activation_threshold=0.6),
    #     preemptive_generation=True, # True = tarts talking immediately.
    # )

    session = AgentSession(
        llm=realtime.RealtimeModel(
            model = "gpt-realtime",
            voice="marin",
            turn_detection=TurnDetection(
                type="semantic_vad",
                eagerness="high",
                create_response=True,
                interrupt_response=True,
            ),
            modalities = ['text']
        ),
        tts=inference.TTS(model="cartesia/sonic-3", voice="9626c31c-bec5-4cca-baa8-f8ba9e84c8bc"),
        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(min_speech_duration=0.3, activation_threshold=0.6),
        preemptive_generation=True,
        use_tts_aligned_transcript=True,
    )

    # --- Background Audio Setup ---
    background_audio = BackgroundAudioPlayer(
        ambient_sound=AudioConfig(BuiltinAudioClip.OFFICE_AMBIENCE, volume=0.25),
        thinking_sound=[
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.6),
        ],
    )
      

    # Start the session
    await session.start(
        agent=Webagent(),
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )

    # # --- Background Audio Setup --- 
    try:
        await background_audio.start(room=ctx.room, agent_session=session)
        logger.info("Background audio started")
    except Exception as e:
        logger.warning(f"Could not start background audio: {e}", exc_info=True)
        
    # --- INITIATING SPEECH (The Agent Speaks First) ---
    welcome_message = "Welcome to Indus Net Technologies. I am marin. How can I help you today?"
    await session.say(text=welcome_message, allow_interruptions=True)

    #await ctx.wait_until_done()

if __name__ == "__main__":
    cli.run_app(server)