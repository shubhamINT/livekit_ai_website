import os
import wave
import asyncio
import subprocess
from livekit import rtc

async def record_audio_track(track: rtc.Track, participant_identity: str, room_name: str, agent_name: str, type_label: str):
    """ Records a single track (user or agent) to a .wav file """
    # Folder: output-recordings/bank/room_name/
    local_output_dir = os.path.join("output-recordings", agent_name, room_name)
    os.makedirs(local_output_dir, exist_ok=True)
    
    # Filename: user_identity.wav OR agent_voice.wav
    file_path = os.path.join(local_output_dir, f"{type_label}_{participant_identity}.wav")
    
    print(f"!!! Starting {type_label} recording: {file_path}")
    audio_stream = rtc.AudioStream(track)

    try:
        with wave.open(file_path, "wb") as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2) # 16-bit PCM
            wav_file.setframerate(48000)

            async for frame_event in audio_stream:
                wav_file.writeframes(frame_event.frame.data)
    except Exception as e:
        print(f"Error recording {type_label}: {e}")
    finally:
        print(f"!!! Finished {type_label} recording: {file_path}")

def merge_audio_files(room_name: str, agent_name: str):
    """ Mixes the recorded user and agent files into one final file using FFmpeg """
    room_dir = os.path.join("output-recordings", agent_name, room_name)
    
    if not os.path.exists(room_dir):
        return

    user_file = None
    agent_file = None

    # Identify the files
    for f in os.listdir(room_dir):
        if f.startswith("user_"): user_file = os.path.join(room_dir, f)
        if f.startswith("agent_"): agent_file = os.path.join(room_dir, f)

    if not user_file or not agent_file:
        print(f"Merge failed: Missing files in {room_dir}")
        return

    output_file = os.path.join(room_dir, "full_conversation.wav")
    
    # FFmpeg command to mix two mono files into one mono/stereo mix
    cmd = [
        'ffmpeg', '-y', 
        '-i', user_file, 
        '-i', agent_file, 
        '-filter_complex', 'amix=inputs=2:duration=longest', 
        output_file
    ]

    try:
        print(f"Merging audio for {room_name}...")
        # Capture stdout and stderr for debugging
        process = subprocess.run(cmd, check=False, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if process.returncode == 0:
            print(f"SUCCESS: Created combined recording at {output_file}")
        else:
            print(f"FFmpeg Merge Error (exit code {process.returncode}): {process.stderr}")
    except Exception as e:
        print(f"FFmpeg Merge Exception: {e}")