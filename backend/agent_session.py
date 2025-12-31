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
from agents.invoice_agent import InvoiceAgent
from livekit.plugins.openai import realtime
from livekit.plugins import cartesia
from openai.types.beta.realtime.session import TurnDetection
import os
import json

logger = logging.getLogger("agent")
load_dotenv(override=True)


# Register multiple agent
AGENT_TYPES = {
    "web": Webagent,
    "invoice": InvoiceAgent,
}


# initialize the agent
server = AgentServer(
    api_key=os.getenv("LIVEKIT_API_KEY"),
    api_secret=os.getenv("LIVEKIT_API_SECRET"),
    ws_url=os.getenv("LIVEKIT_URL"),
)

@server.rtc_session()
async def my_agent(ctx: JobContext):

    # Determine agent type based on room metadata or fallback to "web"
    agent_type = "web"
    participant = await ctx.wait_for_participant()
    print(participant.identity, participant.metadata)
    if ctx.room.metadata:
        try:
            agent_type = json.loads(ctx.room.metadata).get("agent", "web")
        except Exception:
            logger.error("Error parsing agent type from metadata. Getting default agent.")

    AgentClass = AGENT_TYPES.get(agent_type, Webagent)
  

    session = AgentSession(
        llm=realtime.RealtimeModel(
            turn_detection=TurnDetection(
                type="semantic_vad",
                eagerness="medium",
                create_response=True,
                interrupt_response=True,
                idle_timeout_ms=30000
            ),
            modalities = ['text'],
            api_key=os.getenv("OPENAI_API_KEY")
        ),
        #tts=inference.TTS(model="cartesia/sonic-3", voice="209d9a43-03eb-40d8-a7b7-51a6d54c052f"), # Anita
        tts=cartesia.TTS(model="sonic-3", voice="209d9a43-03eb-40d8-a7b7-51a6d54c052f",api_key=os.getenv("CARTESIA_API_KEY")),

        turn_detection=MultilingualModel(),
        vad=silero.VAD.load(min_speech_duration=0.3, activation_threshold=0.7),
        preemptive_generation=False,
        use_tts_aligned_transcript=True,
    )

    # --- Background Audio Setup ---
    background_audio = BackgroundAudioPlayer(
        ambient_sound=AudioConfig(BuiltinAudioClip.OFFICE_AMBIENCE, volume=0.9),
        thinking_sound=[
            AudioConfig(BuiltinAudioClip.KEYBOARD_TYPING, volume=0.8),
        ],
    )
                
    # ---- START SESSION ----
    agent_instance = AgentClass(room=ctx.room)
    # Start the session
    await session.start(
        agent=agent_instance,
        room=ctx.room,
        room_options=room_io.RoomOptions(
            audio_input=room_io.AudioInputOptions(
                noise_cancellation=lambda params: noise_cancellation.BVCTelephony()
                if params.participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP
                else noise_cancellation.BVC(),
            ),
        ),
    )

    # --- Background Audio Setup --- 
    try:
        await background_audio.start(room=ctx.room, agent_session=session)
        logger.info("Background audio started")
    except Exception as e:
        logger.warning(f"Could not start background audio: {e}", exc_info=True)
        
    # --- INITIATING SPEECH (Dynamically canged based on agent) ---
    welcome_message = agent_instance.welcome_message
    await session.say(text=welcome_message, allow_interruptions=True)

if __name__ == "__main__":
    cli.run_app(server)