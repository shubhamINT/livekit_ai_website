import logging
from dotenv import load_dotenv
from livekit import rtc
from livekit.plugins import silero
from livekit.agents import (
    AgentServer,
    AgentSession,
    JobContext,
    cli,
    room_io,
    BackgroundAudioPlayer,
    AudioConfig,
)
from agents.invoice.invoice_agent import InvoiceAgent
from agents.restaurant.restaurant_agent import RestaurantAgent
from agents.banking.banking_agent import BankingAgent
from agents.tour.tour_agent import TourAgent
from agents.realestate.realestate_agent import RealestateAgent
from agents.distributor.distributor_agent import DistributorAgent
from agents.bandhan_banking.bandhan_banking import BandhanBankingAgent
from agents.ambuja.ambuja_agent import AmbujaAgent
from openai.types.beta.realtime.session import TurnDetection
from livekit.plugins import cartesia
from livekit.plugins.openai import realtime
from utils.elevenlabs_nonstream_tts import ElevenLabsNonStreamingTTS
from openai.types.realtime import AudioTranscription
import os
import json
import asyncio
from typing import cast
from inbound.config_manager import get_agent_for_number

logger = logging.getLogger("agent")
load_dotenv(override=True)


# Register multiple agent
AGENT_TYPES = {
    "invoice": InvoiceAgent,
    "restaurant": RestaurantAgent,
    "bank": BankingAgent,
    "tour": TourAgent,
    "realestate": RealestateAgent,
    "distributor": DistributorAgent,
    "bandhan_banking": BandhanBankingAgent,
    "ambuja": AmbujaAgent,
}


# initialize the agent
server = AgentServer(
    api_key=os.getenv("LIVEKIT_API_KEY"),
    api_secret=os.getenv("LIVEKIT_API_SECRET"),
    ws_url=os.getenv("LIVEKIT_URL"),
    job_memory_warn_mb=1024,
)


@server.rtc_session()
async def my_agent(ctx: JobContext):

    # READ FROM ROOM METADATA IMMEDIATELY - no waiting needed!
    room_metadata = json.loads(ctx.room.metadata or "{}")
    logger.info(f"Room metadata: {room_metadata}")
    agent_type = room_metadata.get("agent", "invoice")

    logger.info(f"Agent type from room metadata: {agent_type}")

    # Initialize correct agent from the start
    AgentClass = AGENT_TYPES.get(agent_type, InvoiceAgent)
    agent_instance = AgentClass(room=ctx.room)

    logger.info(f"Initialized {AgentClass.__name__} for room")


    llm = realtime.RealtimeModel(
        model="gpt-realtime",
        input_audio_transcription=AudioTranscription(
            model="gpt-4o-mini-transcribe",
            prompt=(
                "The speaker is multilingual and switches between different languages dynamically. "
                "Transcribe exactly what is spoken without translating."
            ),
        ),
        input_audio_noise_reduction="near_field",
        turn_detection=TurnDetection(
            type="semantic_vad",
            eagerness="low",
            create_response=True,
            interrupt_response=True,
        ),
        modalities=["text"],
        api_key=cast(str, os.getenv("OPENAI_API_KEY")),
    )
    tts = cartesia.TTS(
        model="sonic-3", 
        voice="f6141af3-5f94-418c-80ed-a45d450e7e2e",
        api_key=os.getenv("CARTESIA_API_KEY"),
        )
    # tts=ElevenLabsNonStreamingTTS(
    #     voice_id="kL8yauEAuyf6botQt9wa",  # Monika - Indian Female
    #     model="eleven_v3",
    #     api_key=cast(str, os.getenv("ELEVENLABS_API_KEY")),
    # )
    
    session = AgentSession(
        llm=llm,
        tts=tts,
        preemptive_generation=True,
        use_tts_aligned_transcript=False,
    )

    # # --- Custom Background Audio Setup ---
    # background_audio = BackgroundAudioPlayer(
    #     ambient_sound=AudioConfig(
    #         os.path.join(
    #             os.path.dirname(__file__), "bg_audio", "office-ambience_48k.wav"
    #         ),
    #         volume=0.4,
    #     ),
    #     thinking_sound=AudioConfig(
    #         os.path.join(os.path.dirname(__file__), "bg_audio", "typing-sound_48k.wav"),
    #         volume=0.5,
    #     ),
    # )

    # --- START SESSION ---
    logger.info("Starting AgentSession...")
    try:

        # Configure room options
        room_options = room_io.RoomOptions(
            text_input=True,
            audio_input=True,
            audio_output=True,
            close_on_disconnect=True,
            delete_room_on_close=True,
        )
        
        await session.start(
            agent=agent_instance,
            room=ctx.room,
            room_options=room_options,
        )
        logger.info("AgentSession started successfully")

        # WAIT for participant
        logger.info("Waiting for participant...")
        participant = await ctx.wait_for_participant()
        logger.info(
            f"Participant joined: {participant.identity}, kind={participant.kind}, metadata={participant.metadata}"
        )

        # # Determine agent type based on room metadata or fallback to "invoice"
        # agent_type = "invoice"
        
        # # Check if SIP call
        # if participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP:
        #     logger.info("SIP Participant detected")
        #     if participant.metadata and participant.metadata.strip():
        #         try:
        #             metadata = json.loads(participant.metadata)
        #             if metadata.get("call_type") == "outbound":
        #                 agent_type = metadata.get("agent", "invoice")
        #                 logger.info(f"Outbound SIP call, agent_type={agent_type}")
        #         except Exception as e:
        #             logger.error(f"Error parsing SIP metadata: {e}")
        #     else:
        #         called_number = participant.attributes.get("sip.trunkPhoneNumber")
        #         logger.info(f"Inbound SIP call to: {called_number}")
        #         if called_number:
        #             mapped_agent = get_agent_for_number(called_number)
        #             if mapped_agent:
        #                 agent_type = mapped_agent
        #                 logger.info(f"Mapped SIP number to agent: {agent_type}")
        # else:
        #     # Web call
        #     try:
        #         agent_type = json.loads(participant.metadata).get("agent", "invoice")
        #         logger.info(f"Web call, agent_type={agent_type}")
        #     except Exception:
        #         logger.warning("Could not parse agent_type from web participant metadata, defaulting to 'invoice'")

        # # Initialize the specific Agent Class
        # AgentClass = AGENT_TYPES.get(agent_type, InvoiceAgent)
        # logger.info(f"Initializing Agent instance for: {agent_type} ({AgentClass.__name__})")
        # agent_instance = AgentClass(room=ctx.room)

        # Attach the agent to the session
        # session.update_agent(agent=agent_instance)
        # logger.info(f"Agent session updated with {agent_type} instance")

        # --- Background Audio Start ---
        background_audio = BackgroundAudioPlayer(
            ambient_sound=AudioConfig(
                os.path.join(os.path.dirname(__file__), "bg_audio", "office-ambience_48k.wav"),
                volume=0.4,
            ),
            thinking_sound=AudioConfig(
                os.path.join(os.path.dirname(__file__), "bg_audio", "typing-sound_48k.wav"),
                volume=0.5,
            ),
        )
        try:
            asyncio.create_task(
                background_audio.start(room=ctx.room, agent_session=session)
            )
            logger.info("Background audio task spawned")
        except Exception as e:
            logger.warning(f"Could not start background audio: {e}")

        # --- INITIATING SPEECH ---
        if agent_type != "ambuja":
            welcome_message = agent_instance.welcome_message
            logger.info(f"Sending welcome message: '{welcome_message}'")
            try:
                await session.say(text=welcome_message, allow_interruptions=True)
                logger.info("Welcome message sent successfully")
            except Exception as e:
                logger.error(f"Failed to send welcome message: {e}", exc_info=True)

        # --- KEEP ALIVE LOOP ---
        participant_left = asyncio.Event()

        @ctx.room.on("participant_disconnected")
        def on_participant_disconnected(p: rtc.RemoteParticipant):
            if p.identity == participant.identity:
                logger.info(f"Participant {p.identity} disconnected, ending session.")
                participant_left.set()

        # Keep the task running until the participant leaves or the room is closed
        try:
            while (
                ctx.room.connection_state == rtc.ConnectionState.CONN_CONNECTED 
                and not participant_left.is_set()
            ):
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            logger.info("Keep-alive loop cancelled")
        logger.info("Session ended.")
    finally:
        # --- PROPER CLEANUP ---
        logger.info("Cleaning up resources...")
        
        # Cancel background audio first
        bg_task.cancel()
        try:
            await bg_task
        except asyncio.CancelledError:
            pass
        
        # Close in dependency order
        await session.aclose()
        await llm.aclose()
        await tts.aclose()
        logger.info("Cleanup complete")


if __name__ == "__main__":
    cli.run_app(server)
