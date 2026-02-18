"""
Exotel SIP Bridge V2 — Robust version with PCMA/PCMU support and Digest Authentication.
Bridges SIP/RTP audio with a LiveKit Room.
"""

import asyncio
import logging
import socket
import struct
import uuid
import random
import os
import warnings
import json
import hashlib
import time

# audioop is deprecated in 3.11+ but still available in 3.12
with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

from dotenv import load_dotenv
from livekit import rtc
from livekit.api import AccessToken, VideoGrants

load_dotenv(override=True)

logger = logging.getLogger("sip_bridge_v2")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration (loaded from environment)
# ─────────────────────────────────────────────────────────────────────────────

EXOTEL_SIP_HOST = os.getenv("EXOTEL_SIP_HOST", "pstn.in1.exotel.com")
EXOTEL_SIP_PORT = int(os.getenv("EXOTEL_SIP_PORT", "5070"))
EXOTEL_CUSTOMER_IP = os.getenv("EXOTEL_CUSTOMER_IP", "13.234.150.174")
EXOTEL_CUSTOMER_SIP_PORT = int(os.getenv("EXOTEL_CUSTOMER_SIP_PORT", "5061"))
EXOTEL_MEDIA_IP = os.getenv("EXOTEL_MEDIA_IP", "13.234.150.174")
EXOTEL_CALLER_ID = os.getenv("EXOTEL_CALLER_ID", "08044319240")
EXOTEL_FROM_DOMAIN = os.getenv("EXOTEL_FROM_DOMAIN", "lokaviveka1m.sip.exotel.com")

# Authentication Credentials (optional, used if 401/407 is received)
EXOTEL_AUTH_USERNAME = os.getenv("EXOTEL_AUTH_USERNAME")
EXOTEL_AUTH_PASSWORD = os.getenv("EXOTEL_AUTH_PASSWORD")

LK_URL = os.getenv("LIVEKIT_URL")
LK_API_KEY = os.getenv("LIVEKIT_API_KEY")
LK_API_SECRET = os.getenv("LIVEKIT_API_SECRET")

# RTP constants
RTP_HEADER_SIZE = 12
PCMU_PAYLOAD_TYPE = 0   # G.711 μ-law
PCMA_PAYLOAD_TYPE = 8   # G.711 a-law
SAMPLE_RATE_SIP = 8000  # G.711 sample rate
SAMPLE_RATE_LK = 48000  # LiveKit sample rate


# ─────────────────────────────────────────────────────────────────────────────
# RTPMediaBridge: Handles bidirectional audio between RTP and LiveKit
# ─────────────────────────────────────────────────────────────────────────────

class RTPMediaBridge:
    """Bridges RTP (G.711 PCMA/PCMU over UDP) with a LiveKit room's audio tracks."""

    def __init__(self, bind_ip: str, bind_port: int = 0):
        actual_bind = bind_ip if bind_ip != '0.0.0.0' else '0.0.0.0'
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        try:
            self._sock.bind((bind_ip, bind_port))
        except OSError as e:
            logger.warning(f"[RTP] Cannot bind to {bind_ip}:{bind_port} ({e}), falling back to 0.0.0.0")
            self._sock.bind(('0.0.0.0', bind_port))
        self._sock.setblocking(False)

        self.local_port = self._sock.getsockname()[1]
        bound_addr = self._sock.getsockname()
        self._remote_addr: tuple[str, int] | None = None
        self._running = False
        
        # Negotiated codec (0 = PCMU, 8 = PCMA)
        self.negotiated_pt = PCMU_PAYLOAD_TYPE 

        self._audio_source: rtc.AudioSource | None = None
        self._local_track: rtc.LocalAudioTrack | None = None

        self._rtp_seq = random.randint(0, 0xFFFF)
        self._rtp_ts = random.randint(0, 0xFFFFFFFF)
        self._rtp_ssrc = random.randint(0, 0xFFFFFFFF)

        self._resample_state_in = None
        self._resample_state_out = None

        self._packets_received = 0
        self._packets_sent = 0
        self._first_packet_logged = False
        self._first_send_logged = False
        self._first_frame_logged = False

        logger.info(f"[RTP] Bridge bound to {bound_addr[0]}:{bound_addr[1]}")

    def set_remote_endpoint(self, ip: str, port: int, pt: int = 0):
        self._remote_addr = (ip, port)
        self.negotiated_pt = pt
        logger.info(f"[RTP] Remote endpoint set: {ip}:{port}, Codec PT: {pt}")

    async def start_inbound(self, room: rtc.Room):
        loop = asyncio.get_running_loop()
        self._audio_source = rtc.AudioSource(SAMPLE_RATE_LK, 1, loop=loop)
        self._local_track = rtc.LocalAudioTrack.create_audio_track(
            "sip_microphone", self._audio_source
        )
        await room.local_participant.publish_track(self._local_track)
        logger.info("[RTP] Local audio track published to LiveKit room")

        self._running = True
        asyncio.create_task(self._rtp_receive_loop(loop))

    async def _rtp_receive_loop(self, loop: asyncio.AbstractEventLoop):
        logger.info("[RTP] Inbound receive loop started")
        while self._running:
            try:
                data, addr = await loop.sock_recvfrom(self._sock, 4096)
            except (OSError, asyncio.CancelledError):
                break
            except Exception as e:
                await asyncio.sleep(0.001)
                continue

            if len(data) <= RTP_HEADER_SIZE:
                continue

            if not self._first_packet_logged:
                logger.info(f"[RTP] First packet received from {addr} ({len(data)} bytes)")
                self._first_packet_logged = True

            self._packets_received += 1
            
            # Extract PT from header (byte 1, bits 0-6)
            pt = data[1] & 0x7F
            payload = data[RTP_HEADER_SIZE:]

            try:
                # Decode based on PT
                if pt == PCMA_PAYLOAD_TYPE:
                    pcm_8k = audioop.alaw2lin(payload, 2)
                else:
                    pcm_8k = audioop.ulaw2lin(payload, 2)

                pcm_48k, self._resample_state_in = audioop.ratecv(
                    pcm_8k, 2, 1, SAMPLE_RATE_SIP, SAMPLE_RATE_LK, self._resample_state_in
                )

                samples_per_channel = len(pcm_48k) // 2
                frame = rtc.AudioFrame(
                    data=pcm_48k,
                    sample_rate=SAMPLE_RATE_LK,
                    num_channels=1,
                    samples_per_channel=samples_per_channel,
                )
                await self._audio_source.capture_frame(frame)
            except Exception as e:
                logger.error(f"[RTP] Inbound decode error: {e}")

    async def send_to_rtp(self, frame: rtc.AudioFrame):
        if not self._remote_addr:
            return

        try:
            raw_pcm = bytes(frame.data.cast("b"))
            pcm_8k, self._resample_state_out = audioop.ratecv(
                raw_pcm, 2, 1, frame.sample_rate, SAMPLE_RATE_SIP, self._resample_state_out
            )

            # Encode based on negotiated PT
            if self.negotiated_pt == PCMA_PAYLOAD_TYPE:
                payload = audioop.lin2alaw(pcm_8k, 2)
            else:
                payload = audioop.lin2ulaw(pcm_8k, 2)

            self._rtp_seq = (self._rtp_seq + 1) & 0xFFFF
            samples_in_packet = len(pcm_8k) // 2
            self._rtp_ts = (self._rtp_ts + samples_in_packet) & 0xFFFFFFFF

            header = struct.pack("!BBHII", 0x80, self.negotiated_pt, self._rtp_seq, self._rtp_ts, self._rtp_ssrc)
            packet = header + payload
            self._sock.sendto(packet, self._remote_addr)
            self._packets_sent += 1

            if not self._first_send_logged:
                logger.info(f"[RTP] First RTP packet SENT to {self._remote_addr}")
                self._first_send_logged = True
        except Exception as e:
            logger.error(f"[RTP] Outbound send error: {e}")

    def stop(self):
        self._running = False
        try:
            self._sock.close()
        except:
            pass
        logger.info(f"[RTP] Bridge stopped. Rx: {self._packets_received}, Tx: {self._packets_sent}")


# ─────────────────────────────────────────────────────────────────────────────
# Digest Auth Helper
# ─────────────────────────────────────────────────────────────────────────────

def calculate_digest_auth(method, uri, username, password, auth_header):
    """Parses WWW-Authenticate/Proxy-Authenticate and calculates Response."""
    params = {}
    # Remove 'Digest ' prefix
    header_val = auth_header.split(' ', 1)[1]
    # Simple parser for comma-separated key="value"
    import re
    matches = re.findall(r'(\w+)="?([^",]+)"?', header_val)
    for k, v in matches:
        params[k] = v

    realm = params.get('realm')
    nonce = params.get('nonce')
    opaque = params.get('opaque')
    qop = params.get('qop')
    algorithm = params.get('algorithm', 'MD5').upper()

    # HA1 = MD5(username:realm:password)
    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
    # HA2 = MD5(method:uri)
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()

    if qop == 'auth':
        nc = "00000001"
        cnonce = uuid.uuid4().hex[:8]
        # response = MD5(HA1:nonce:nc:cnonce:qop:HA2)
        resp = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()
        auth_str = (f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
                    f'uri="{uri}", response="{resp}", algorithm={algorithm}, '
                    f'nc={nc}, cnonce="{cnonce}", qop={qop}')
    else:
        # response = MD5(HA1:nonce:HA2)
        resp = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        auth_str = (f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
                    f'uri="{uri}", response="{resp}", algorithm={algorithm}')
    
    if opaque:
        auth_str += f', opaque="{opaque}"'
    
    return auth_str


# ─────────────────────────────────────────────────────────────────────────────
# ExotelSipClient: Handles SIP signaling with Auth support
# ─────────────────────────────────────────────────────────────────────────────

class ExotelSipClient:
    def __init__(self, callee: str, rtp_port: int):
        self.callee = callee
        self.rtp_port = rtp_port
        self._branch = f"z9hG4bK-{uuid.uuid4().hex}"
        self._tag = f"trunk{random.randint(10000, 99999)}"
        self._call_id = str(uuid.uuid4())
        self._cseq = 1
        self._to_tag = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    def _build_sdp(self) -> str:
        # Offering PCMA (8) and PCMU (0)
        return (
            f"v=0\r\n"
            f"o=- {int(time.time())} {int(time.time())} IN IP4 {EXOTEL_MEDIA_IP}\r\n"
            f"s=-\r\n"
            f"c=IN IP4 {EXOTEL_MEDIA_IP}\r\n"
            f"t=0 0\r\n"
            f"m=audio {self.rtp_port} RTP/AVP 8 0 101\r\n"
            f"a=rtpmap:8 PCMA/8000\r\n"
            f"a=rtpmap:0 PCMU/8000\r\n"
            f"a=rtpmap:101 telephone-event/8000\r\n"
            f"a=fmtp:101 0-15\r\n"
            f"a=ptime:20\r\n"
            f"a=sendrecv\r\n"
        )

    def _build_invite(self, auth_header: str | None = None, proxy_auth: bool = False) -> bytes:
        sdp = self._build_sdp()
        cl = len(sdp.encode())
        req_uri = f"sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT}"
        
        headers = [
            f"INVITE {req_uri} SIP/2.0",
            f"Via: SIP/2.0/TCP {EXOTEL_CUSTOMER_IP}:{EXOTEL_CUSTOMER_SIP_PORT};branch={self._branch};rport",
            f"Max-Forwards: 70",
            f"From: \"{EXOTEL_CALLER_ID}\" <sip:{EXOTEL_CALLER_ID}@{EXOTEL_FROM_DOMAIN}>;tag={self._tag}",
            f"To: <sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT}>",
            f"Call-ID: {self._call_id}",
            f"CSeq: {self._cseq} INVITE",
            f"Contact: <sip:{EXOTEL_CALLER_ID}@{EXOTEL_CUSTOMER_IP}:{EXOTEL_CUSTOMER_SIP_PORT};transport=tcp>",
            f"Supported: 100rel, timer",
            f"Allow: INVITE, ACK, CANCEL, BYE, OPTIONS, UPDATE",
            f"Content-Type: application/sdp",
            f"Content-Length: {cl}"
        ]
        
        if auth_header:
            h_name = "Proxy-Authorization" if proxy_auth else "Authorization"
            headers.insert(7, f"{h_name}: {auth_header}")

        msg = "\r\n".join(headers) + "\r\n\r\n" + sdp
        return msg.encode()

    def _build_ack(self) -> bytes:
        to_line = f"<sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT}>"
        if self._to_tag: to_line += f";tag={self._to_tag}"
        
        headers = [
            f"ACK sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT} SIP/2.0",
            f"Via: SIP/2.0/TCP {EXOTEL_CUSTOMER_IP}:{EXOTEL_CUSTOMER_SIP_PORT};branch={self._branch};rport",
            f"Max-Forwards: 70",
            f"From: \"{EXOTEL_CALLER_ID}\" <sip:{EXOTEL_CALLER_ID}@{EXOTEL_FROM_DOMAIN}>;tag={self._tag}",
            f"To: {to_line}",
            f"Call-ID: {self._call_id}",
            f"CSeq: {self._cseq} ACK",
            f"Content-Length: 0"
        ]
        return ("\r\n".join(headers) + "\r\n\r\n").encode()

    def _build_bye(self) -> bytes:
        to_line = f"<sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT}>"
        if self._to_tag: to_line += f";tag={self._to_tag}"
        self._cseq += 1
        headers = [
            f"BYE sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT} SIP/2.0",
            f"Via: SIP/2.0/TCP {EXOTEL_CUSTOMER_IP}:{EXOTEL_CUSTOMER_SIP_PORT};branch=z9hG4bK-{uuid.uuid4().hex};rport",
            f"Max-Forwards: 70",
            f"From: \"{EXOTEL_CALLER_ID}\" <sip:{EXOTEL_CALLER_ID}@{EXOTEL_FROM_DOMAIN}>;tag={self._tag}",
            f"To: {to_line}",
            f"Call-ID: {self._call_id}",
            f"CSeq: {self._cseq} BYE",
            f"Content-Length: 0"
        ]
        return ("\r\n".join(headers) + "\r\n\r\n").encode()

    async def connect(self):
        logger.info(f"[SIP] Connecting to {EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT}...")
        self._reader, self._writer = await asyncio.wait_for(
            asyncio.open_connection(EXOTEL_SIP_HOST, EXOTEL_SIP_PORT), timeout=10.0
        )

    async def send_invite(self) -> dict | None:
        invite = self._build_invite()
        self._writer.write(invite)
        await self._writer.drain()
        logger.info("[SIP] INVITE sent")
        
        return await self._wait_for_answer()

    async def _wait_for_answer(self) -> dict | None:
        buffer = b""
        while True:
            try:
                chunk = await asyncio.wait_for(self._reader.read(8192), timeout=30.0)
                if not chunk: return None
                buffer += chunk
                
                while b"\r\n\r\n" in buffer:
                    h_end = buffer.index(b"\r\n\r\n")
                    h_block = buffer[:h_end].decode(errors="replace")
                    remaining = buffer[h_end+4:]
                    h_lines = h_block.split("\r\n")
                    status = h_lines[0]
                    headers = {l.split(":", 1)[0].strip().lower(): l.split(":", 1)[1].strip() for l in h_lines[1:] if ":" in l}
                    
                    cl = int(headers.get("content-length", "0"))
                    if len(remaining) < cl: break
                    body = remaining[:cl].decode(errors="replace")
                    buffer = remaining[cl:]
                    
                    logger.info(f"[SIP] Response: {status}")
                    
                    code = int(status.split(" ")[1])
                    
                    if code == 100: continue
                    if 180 <= code <= 183: continue
                    
                    if code == 401 or code == 407:
                        auth_h = "www-authenticate" if code == 401 else "proxy-authenticate"
                        if auth_h not in headers or not EXOTEL_AUTH_USERNAME:
                            logger.error(f"[SIP] Auth required but no credentials or header: {status}")
                            return None
                        
                        # Send ACK for the failed INVITE
                        self._writer.write(self._build_ack())
                        await self._writer.drain()
                        
                        # Retrying with Auth
                        logger.info(f"[SIP] Retrying with {auth_h}...")
                        self._cseq += 1
                        self._branch = f"z9hG4bK-{uuid.uuid4().hex}"
                        uri = f"sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT}"
                        auth_val = calculate_digest_auth("INVITE", uri, EXOTEL_AUTH_USERNAME, EXOTEL_AUTH_PASSWORD, headers[auth_h])
                        
                        invite = self._build_invite(auth_header=auth_val, proxy_auth=(code == 407))
                        self._writer.write(invite)
                        await self._writer.drain()
                        continue

                    if code == 200:
                        self._to_tag = headers.get("to", "").split("tag=")[-1].split(";")[0] if "tag=" in headers.get("to", "") else None
                        self._writer.write(self._build_ack())
                        await self._writer.drain()
                        
                        # Simple SDP parse for IP/Port and PT
                        rip, rport, rpt = None, 0, 0
                        for line in body.splitlines():
                            if line.startswith("c=IN IP4"): rip = line.split()[-1]
                            if line.startswith("m=audio"): 
                                rport = int(line.split()[1])
                                rpt = int(line.split()[3]) # First PT
                        return {"remote_ip": rip, "remote_port": rport, "pt": rpt, "to_tag": self._to_tag}
                    
                    if code >= 400:
                        logger.error(f"[SIP] Call Failed: {status}\n{h_block}")
                        return None
            except Exception as e:
                logger.error(f"[SIP] Error in receive loop: {e}")
                return None

    async def wait_for_disconnection(self):
        try:
            while True:
                data = await self._reader.read(4096)
                if not data or b"BYE " in data: break
        except: pass

    async def close(self):
        if self._writer:
            self._writer.close()
            await self._writer.wait_closed()

async def run_bridge(phone_number: str, agent_type: str = "invoice", room_name: str | None = None):
    if not room_name: room_name = f"sip-bridge-{phone_number}-{uuid.uuid4().hex[:6]}"
    logger.info(f"[BRIDGE] Starting v2 bridge for {phone_number} in {room_name}")

    rtp_bridge = RTPMediaBridge(bind_ip=EXOTEL_MEDIA_IP)
    sip_client = ExotelSipClient(callee=phone_number, rtp_port=rtp_bridge.local_port)
    room = rtc.Room()
    forward_task = None

    try:
        @room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            nonlocal forward_task
            if track.kind == rtc.TrackKind.KIND_AUDIO and publication.source == rtc.TrackSource.SOURCE_MICROPHONE:
                if not forward_task:
                    logger.info(f"[BRIDGE] Agent audio subscribed: {participant.identity}")
                    forward_task = asyncio.create_task(_forward_agent_audio(track, rtp_bridge))

        # LiveKit Connect
        token = AccessToken(LK_API_KEY, LK_API_SECRET).with_identity(f"sip-{phone_number}").with_grants(VideoGrants(room_join=True, room=room_name)).to_jwt()
        await room.connect(LK_URL, token)
        await rtp_bridge.start_inbound(room)

        # SIP Call
        await sip_client.connect()
        res = await sip_client.send_invite()
        if not res: return

        rtp_bridge.set_remote_endpoint(res["remote_ip"], res["remote_port"], res["pt"])
        
        # Keep alive
        sip_mon = asyncio.create_task(sip_client.wait_for_disconnection())
        while room.connection_state == rtc.ConnectionState.CONN_CONNECTED and not sip_mon.done():
            await asyncio.sleep(2)
    finally:
        if forward_task: forward_task.cancel()
        rtp_bridge.stop()
        await sip_client.close()
        await room.disconnect()

async def _forward_agent_audio(track, rtp_bridge):
    stream = rtc.AudioStream(track, sample_rate=48000, num_channels=1)
    async for event in stream:
        await rtp_bridge.send_to_rtp(event.frame)

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_bridge("08697421450"))
