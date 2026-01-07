from livekit import api, rtc
import os
from datetime import timedelta
from dotenv import load_dotenv
import asyncio
import wave

load_dotenv(override=True)

# livekit secrets
LIVEKIT_EGRESS_URL = os.getenv("LIVEKIT_EGRESS_URL")
LIVEKIT_API_KEY = os.getenv("LIVEKIT_API_KEY")
LIVEKIT_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# # Local parth for transcription
# LOCAL_PATH = os.path.join(os.getcwd(), "output-recordings")

# # Ensure the output directory exists
# os.makedirs(LOCAL_PATH, exist_ok=True)

# async def record_transcription_srt(room_name: str, srt_path: str):
#     room = rtc.Room()
#     counter = 1 # SRT requires an incrementing index

#     @room.on("transcription_received")
#     def on_transcription(segments: list[rtc.TranscriptionSegment], participant: rtc.Participant, publication: rtc.TrackPublication):
#         nonlocal counter
        
#         # NOTE: 'segments' is already the list, so we loop through it directly
#         with open(srt_path, "a", encoding="utf-8") as f:
#             for segment in segments:
#                 # Format timestamps for SRT (00:00:00,000)
#                 start = format_srt_time(segment.start_time)
#                 end = format_srt_time(segment.end_time)
                
#                 f.write(f"{counter}\n")
#                 f.write(f"{start} --> {end}\n")
#                 f.write(f"{segment.text}\n\n")
#                 f.flush()
#                 counter += 1

#     # Connect to room as a logger
#     token = api.AccessToken(LIVEKIT_API_KEY, LIVEKIT_API_SECRET) \
#         .with_identity(f"recorder_{room_name}") \
#         .with_grants(api.VideoGrants(room_join=True, room=room_name))
    
#     await room.connect(LIVEKIT_EGRESS_URL, token.to_jwt())
    
#     # Updated connection check
#     # We check if connection_state is CONN_CONNECTED
#     while room.connection_state == rtc.ConnectionState.CONN_CONNECTED:
#         await asyncio.sleep(1)

# def format_srt_time(ms: int) -> str:
#     """Helper to convert milliseconds to SRT timestamp format: HH:MM:SS,mmm"""
#     td = timedelta(milliseconds=ms)
#     total_seconds = int(td.total_seconds())
#     hours, remainder = divmod(total_seconds, 3600)
#     minutes, seconds = divmod(remainder, 60)
#     milliseconds = int(td.microseconds / 1000)
#     return f"{hours:02}:{minutes:02}:{seconds:02},{milliseconds:03}"

async def start_audio_recording(room_name: str, agent_name: str):

    # Ensure the folder exists on your computer host
    local_output_dir = os.path.join("output-recordings", agent_name)
    if not os.path.exists(local_output_dir):
        os.makedirs(local_output_dir)
        print(f"Created directory: {local_output_dir}")

    client = api.LiveKitAPI(url=LIVEKIT_EGRESS_URL,api_key=LIVEKIT_API_KEY,api_secret=LIVEKIT_API_SECRET)

    try:
        output_path = f"/out/{agent_name}/{room_name}.ogg"
        # srt_path = os.path.join(LOCAL_PATH, f"{room_name}.srt")

        # Record the audio of the room
        req = api.RoomCompositeEgressRequest(
            room_name=room_name,
            audio_only=True,
            file_outputs=[api.EncodedFileOutput(
                file_type=api.EncodedFileType.OGG,
                filepath=output_path
                )]
        )
        
        result = await client.egress.start_room_composite_egress(req)
        # asyncio.create_task(record_transcription_srt(room_name, srt_path))

        return {
            "room_name": room_name,
            "output_path": output_path,
            "engess_id": result.egress_id
        }

    except Exception as e:
        print(f"Error starting audio recording: {e}")
        return None
    


# This function will run in the background and save the audio
async def record_participant_audio2(participant: rtc.RemoteParticipant, agent_name: str, room_name: str):
    # Ensure folder exists
    local_output_dir = os.path.join("output-recordings", agent_name)
    os.makedirs(local_output_dir, exist_ok=True)
    
    file_path = os.path.join(local_output_dir, f"{room_name}_{participant.identity}.wav")
    
    # We will subscribe to the participant's audio track
    audio_stream = None
    
    # Wait for the audio track to be published
    for track_pub in participant.track_publications.values():
        if track_pub.track and track_pub.track.kind == rtc.TrackKind.KIND_AUDIO:
            audio_stream = rtc.AudioStream(track_pub.track)
            break

    if not audio_stream:
        return

    print(f"Started local recording for {participant.identity} at {file_path}")

    # Open a Wave file to save the raw audio
    with wave.open(file_path, "wb") as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2) # 16-bit
        wav_file.setframerate(48000)

        async for frame in audio_stream:
            wav_file.writeframes(frame.data)


async def start_audio_recording2(room_name: str, agent_name: str):
    # Ensure folder exists
    local_output_dir = os.path.join("output-recordings", agent_name)
    os.makedirs(local_output_dir, exist_ok=True)

    file_path = os.path.join(local_output_dir, f"/{agent_name}/{room_name}.ogg")
    request = api.RoomCompositeEgressRequest(
        room_name=room_name,
        audio_only=True,   # only audio
        file_outputs=[
            api.EncodedFileOutput(
                file_type=api.EncodedFileType.OGG, 
                filepath=file_path,  # local path
            )
        ],
    )

    lkapi = api.LiveKitAPI()
    response = await lkapi.egress.start_room_composite_egress(request)
    await lkapi.aclose()



async def record_participant_audio(track: rtc.RemoteAudioTrack, participant: rtc.RemoteParticipant, room_name: str, agent_name: str):
    # 1. Setup the folder (D:\code\...\output-recordings\bank\)
    local_output_dir = os.path.join("output-recordings", agent_name)
    os.makedirs(local_output_dir, exist_ok=True)
    
    # 2. Setup the file name
    timestamp = int(asyncio.get_event_loop().time())
    file_path = os.path.join(local_output_dir, f"{room_name}_{participant.identity}_{timestamp}.wav")
    
    print(f"!!! STARTING LOCAL DISK RECORDING: {file_path}")

    # 3. Create the stream (standard LiveKit 48kHz, Mono)
    audio_stream = rtc.AudioStream(track)

    try:
        # Open the file in 'write binary' mode
        with wave.open(file_path, "wb") as wav_file:
            wav_file.setnchannels(1)  # Mono
            wav_file.setsampwidth(2) # 16-bit PCM (2 bytes)
            wav_file.setframerate(48000)

            # This loop runs as long as the participant is talking/connected
            async for frame_event in audio_stream:
                # 'frame_event.frame.data' contains the raw audio bytes
                wav_file.writeframes(frame_event.frame.data)
                
    except Exception as e:
        print(f"Recording Error: {e}")
    finally:
        print(f"!!! RECORDING CLOSED: {file_path}")
