"""
Exotel SIP Bridge V2 — Fixed version.

Key fixes:
1. Fixed RTP port (env var RTP_PORT) so firewall rules can be set
2. Frame buffering: agent audio is queued while waiting for SIP answer
3. Correct execution order: SIP first, then subscribe agent audio
4. Proper asyncio socket binding for RTP receive
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
import collections

with warnings.catch_warnings():
    warnings.simplefilter("ignore", DeprecationWarning)
    import audioop

from dotenv import load_dotenv
from livekit import rtc
from livekit.api import AccessToken, VideoGrants

load_dotenv(override=True)

logger = logging.getLogger("sip_bridge_v2")

# ─────────────────────────────────────────────────────────────────────────────
# Configuration
# ─────────────────────────────────────────────────────────────────────────────

EXOTEL_SIP_HOST         = os.getenv("EXOTEL_SIP_HOST", "pstn.in1.exotel.com")
EXOTEL_SIP_PORT         = int(os.getenv("EXOTEL_SIP_PORT", "5070"))
EXOTEL_CUSTOMER_IP      = os.getenv("EXOTEL_CUSTOMER_IP", "13.234.150.174")
EXOTEL_CUSTOMER_SIP_PORT= int(os.getenv("EXOTEL_CUSTOMER_SIP_PORT", "5061"))
EXOTEL_MEDIA_IP         = os.getenv("EXOTEL_MEDIA_IP", "13.234.150.174")
EXOTEL_CALLER_ID        = os.getenv("EXOTEL_CALLER_ID", "08044319240")
EXOTEL_FROM_DOMAIN      = os.getenv("EXOTEL_FROM_DOMAIN", "lokaviveka1m.sip.exotel.com")

EXOTEL_AUTH_USERNAME    = os.getenv("EXOTEL_AUTH_USERNAME")
EXOTEL_AUTH_PASSWORD    = os.getenv("EXOTEL_AUTH_PASSWORD")

LK_URL       = os.getenv("LIVEKIT_URL")
LK_API_KEY   = os.getenv("LIVEKIT_API_KEY")
LK_API_SECRET= os.getenv("LIVEKIT_API_SECRET")

# ─── FIX 1: Use a fixed, configurable RTP port ───────────────────────────────
# Set RTP_PORT in your .env / environment to a port that is OPEN in your
# AWS Security Group for UDP traffic from Exotel's media servers.
# Example: RTP_PORT=20000
# If 0, a random port is used (NOT recommended for production — firewall will block it).
RTP_BIND_PORT = int(os.getenv("RTP_PORT", "0"))

RTP_HEADER_SIZE  = 12
PCMU_PAYLOAD_TYPE = 0
PCMA_PAYLOAD_TYPE = 8
SAMPLE_RATE_SIP  = 8000
SAMPLE_RATE_LK   = 48000

# How many outbound frames to buffer while waiting for SIP 200 OK
MAX_FRAME_BUFFER = 200


# ─────────────────────────────────────────────────────────────────────────────
# RTPMediaBridge
# ─────────────────────────────────────────────────────────────────────────────

class RTPMediaBridge:
    """Bridges RTP (G.711 PCMA/PCMU over UDP) ↔ LiveKit audio."""

    def __init__(self, bind_ip: str, bind_port: int = 0):
        self._sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Always bind to 0.0.0.0 so the OS can receive on all interfaces.
        # The SDP advertises EXOTEL_MEDIA_IP (the external/Elastic IP).
        try:
            self._sock.bind(('0.0.0.0', bind_port))
        except OSError as e:
            logger.error(f"[RTP] Failed to bind to 0.0.0.0:{bind_port}: {e}")
            raise
        self._sock.setblocking(False)

        self.local_port = self._sock.getsockname()[1]
        logger.info(f"[RTP] Bridge bound to 0.0.0.0:{self.local_port} (advertised as {bind_ip}:{self.local_port})")

        self._remote_addr: tuple[str, int] | None = None
        self._running = False
        self.negotiated_pt = PCMU_PAYLOAD_TYPE

        self._audio_source: rtc.AudioSource | None = None
        self._local_track: rtc.LocalAudioTrack | None = None

        self._rtp_seq  = random.randint(0, 0xFFFF)
        self._rtp_ts   = random.randint(0, 0xFFFFFFFF)
        self._rtp_ssrc = random.randint(0, 0xFFFFFFFF)

        self._resample_state_in  = None
        self._resample_state_out = None

        self._packets_received = 0
        self._packets_sent     = 0
        self._first_packet_logged = False
        self._first_send_logged   = False

        # ─── FIX 2: Frame buffer for agent audio before SIP is answered ───
        # Frames arriving before _remote_addr is set are queued here.
        self._frame_buffer: collections.deque = collections.deque(maxlen=MAX_FRAME_BUFFER)
        self._remote_ready = asyncio.Event()

    def set_remote_endpoint(self, ip: str, port: int, pt: int = 0):
        self._remote_addr  = (ip, port)
        self.negotiated_pt = pt
        logger.info(f"[RTP] Remote endpoint set: {ip}:{port}, Codec PT: {pt}")
        # Signal that buffered frames can now be flushed
        self._remote_ready.set()

    async def start_inbound(self, room: rtc.Room):
        loop = asyncio.get_running_loop()
        self._audio_source = rtc.AudioSource(SAMPLE_RATE_LK, 1)
        self._local_track  = rtc.LocalAudioTrack.create_audio_track(
            "sip_microphone", self._audio_source
        )
        await room.local_participant.publish_track(self._local_track)
        logger.info("[RTP] Local audio track published to LiveKit room")

        self._running = True
        asyncio.create_task(self._rtp_receive_loop(loop))

    async def _rtp_receive_loop(self, loop: asyncio.AbstractEventLoop):
        logger.info("[RTP] Inbound receive loop started — waiting for packets...")
        while self._running:
            try:
                data, addr = await loop.sock_recvfrom(self._sock, 4096)
            except (OSError, asyncio.CancelledError):
                break
            except Exception:
                await asyncio.sleep(0.001)
                continue

            if len(data) <= RTP_HEADER_SIZE:
                continue

            if not self._first_packet_logged:
                logger.info(f"[RTP] ✅ First packet RECEIVED from {addr} ({len(data)} bytes)")
                self._first_packet_logged = True

            self._packets_received += 1
            pt      = data[1] & 0x7F
            payload = data[RTP_HEADER_SIZE:]

            try:
                if pt == PCMA_PAYLOAD_TYPE:
                    pcm_8k = audioop.alaw2lin(payload, 2)
                else:
                    pcm_8k = audioop.ulaw2lin(payload, 2)

                pcm_48k, self._resample_state_in = audioop.ratecv(
                    pcm_8k, 2, 1, SAMPLE_RATE_SIP, SAMPLE_RATE_LK, self._resample_state_in
                )

                frame = rtc.AudioFrame(
                    data=pcm_48k,
                    sample_rate=SAMPLE_RATE_LK,
                    num_channels=1,
                    samples_per_channel=len(pcm_48k) // 2,
                )
                await self._audio_source.capture_frame(frame)
            except Exception as e:
                logger.error(f"[RTP] Inbound decode error: {e}")

    async def send_to_rtp(self, frame: rtc.AudioFrame):
        """Send a LiveKit audio frame to the remote RTP endpoint.
        
        If the remote endpoint is not yet set (SIP not answered),
        the frame is buffered and flushed once the call is answered.
        """
        if not self._remote_addr:
            # Buffer the frame — will be flushed when set_remote_endpoint is called
            self._frame_buffer.append(frame)
            return

        # Flush any buffered frames first (only happens once)
        while self._frame_buffer:
            buffered = self._frame_buffer.popleft()
            await self._send_frame(buffered)

        await self._send_frame(frame)

    async def _send_frame(self, frame: rtc.AudioFrame):
        if not self._remote_addr:
            return
        try:
            raw_pcm = bytes(frame.data.cast("b"))
            pcm_8k, self._resample_state_out = audioop.ratecv(
                raw_pcm, 2, 1, frame.sample_rate, SAMPLE_RATE_SIP, self._resample_state_out
            )

            if self.negotiated_pt == PCMA_PAYLOAD_TYPE:
                payload = audioop.lin2alaw(pcm_8k, 2)
            else:
                payload = audioop.lin2ulaw(pcm_8k, 2)

            self._rtp_seq = (self._rtp_seq + 1) & 0xFFFF
            self._rtp_ts  = (self._rtp_ts + len(pcm_8k) // 2) & 0xFFFFFFFF

            header = struct.pack(
                "!BBHII",
                0x80, self.negotiated_pt,
                self._rtp_seq, self._rtp_ts, self._rtp_ssrc
            )
            self._sock.sendto(header + payload, self._remote_addr)
            self._packets_sent += 1

            if not self._first_send_logged:
                logger.info(f"[RTP] ✅ First RTP packet SENT to {self._remote_addr}")
                self._first_send_logged = True
        except Exception as e:
            logger.error(f"[RTP] Outbound send error: {e}")

    def stop(self):
        self._running = False
        try:
            self._sock.close()
        except Exception:
            pass
        logger.info(
            f"[RTP] Bridge stopped. "
            f"Rx: {self._packets_received} packets, Tx: {self._packets_sent} packets"
        )
        if self._packets_received == 0:
            logger.warning(
                "[RTP] ⚠️  ZERO inbound packets received! "
                "Check that UDP port %d is open in your firewall/Security Group "
                "for Exotel's media servers.", self.local_port
            )


# ─────────────────────────────────────────────────────────────────────────────
# Digest Auth Helper
# ─────────────────────────────────────────────────────────────────────────────

def calculate_digest_auth(method, uri, username, password, auth_header):
    import re
    params = {}
    header_val = auth_header.split(' ', 1)[1]
    matches = re.findall(r'(\w+)="?([^",]+)"?', header_val)
    for k, v in matches:
        params[k] = v

    realm     = params.get('realm')
    nonce     = params.get('nonce')
    opaque    = params.get('opaque')
    qop       = params.get('qop')
    algorithm = params.get('algorithm', 'MD5').upper()

    ha1 = hashlib.md5(f"{username}:{realm}:{password}".encode()).hexdigest()
    ha2 = hashlib.md5(f"{method}:{uri}".encode()).hexdigest()

    if qop == 'auth':
        nc     = "00000001"
        cnonce = uuid.uuid4().hex[:8]
        resp   = hashlib.md5(f"{ha1}:{nonce}:{nc}:{cnonce}:{qop}:{ha2}".encode()).hexdigest()
        auth_str = (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{resp}", algorithm={algorithm}, '
            f'nc={nc}, cnonce="{cnonce}", qop={qop}'
        )
    else:
        resp     = hashlib.md5(f"{ha1}:{nonce}:{ha2}".encode()).hexdigest()
        auth_str = (
            f'Digest username="{username}", realm="{realm}", nonce="{nonce}", '
            f'uri="{uri}", response="{resp}", algorithm={algorithm}'
        )

    if opaque:
        auth_str += f', opaque="{opaque}"'
    return auth_str


# ─────────────────────────────────────────────────────────────────────────────
# ExotelSipClient
# ─────────────────────────────────────────────────────────────────────────────

class ExotelSipClient:
    def __init__(self, callee: str, rtp_port: int):
        self.callee    = callee
        self.rtp_port  = rtp_port
        self._branch   = f"z9hG4bK-{uuid.uuid4().hex}"
        self._tag      = f"trunk{random.randint(10000, 99999)}"
        self._call_id  = str(uuid.uuid4())
        self._cseq     = 1
        self._to_tag   = None
        self._reader: asyncio.StreamReader | None = None
        self._writer: asyncio.StreamWriter | None = None

    def _build_sdp(self) -> str:
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
        sdp    = self._build_sdp()
        cl     = len(sdp.encode())
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
            f"Content-Length: {cl}",
        ]

        if auth_header:
            h_name = "Proxy-Authorization" if proxy_auth else "Authorization"
            headers.insert(7, f"{h_name}: {auth_header}")

        return ("\r\n".join(headers) + "\r\n\r\n" + sdp).encode()

    def _build_ack(self) -> bytes:
        to_line = f"<sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT}>"
        if self._to_tag:
            to_line += f";tag={self._to_tag}"
        headers = [
            f"ACK sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT} SIP/2.0",
            f"Via: SIP/2.0/TCP {EXOTEL_CUSTOMER_IP}:{EXOTEL_CUSTOMER_SIP_PORT};branch={self._branch};rport",
            f"Max-Forwards: 70",
            f"From: \"{EXOTEL_CALLER_ID}\" <sip:{EXOTEL_CALLER_ID}@{EXOTEL_FROM_DOMAIN}>;tag={self._tag}",
            f"To: {to_line}",
            f"Call-ID: {self._call_id}",
            f"CSeq: {self._cseq} ACK",
            f"Content-Length: 0",
        ]
        return ("\r\n".join(headers) + "\r\n\r\n").encode()

    def _build_bye(self) -> bytes:
        to_line = f"<sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT}>"
        if self._to_tag:
            to_line += f";tag={self._to_tag}"
        self._cseq += 1
        headers = [
            f"BYE sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT} SIP/2.0",
            f"Via: SIP/2.0/TCP {EXOTEL_CUSTOMER_IP}:{EXOTEL_CUSTOMER_SIP_PORT};branch=z9hG4bK-{uuid.uuid4().hex};rport",
            f"Max-Forwards: 70",
            f"From: \"{EXOTEL_CALLER_ID}\" <sip:{EXOTEL_CALLER_ID}@{EXOTEL_FROM_DOMAIN}>;tag={self._tag}",
            f"To: {to_line}",
            f"Call-ID: {self._call_id}",
            f"CSeq: {self._cseq} BYE",
            f"Content-Length: 0",
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
                chunk = await asyncio.wait_for(self._reader.read(8192), timeout=60.0)
                if not chunk:
                    return None
                buffer += chunk

                while b"\r\n\r\n" in buffer:
                    h_end   = buffer.index(b"\r\n\r\n")
                    h_block = buffer[:h_end].decode(errors="replace")
                    remaining = buffer[h_end + 4:]
                    h_lines = h_block.split("\r\n")
                    status  = h_lines[0]
                    headers = {
                        l.split(":", 1)[0].strip().lower(): l.split(":", 1)[1].strip()
                        for l in h_lines[1:] if ":" in l
                    }

                    cl = int(headers.get("content-length", "0"))
                    if len(remaining) < cl:
                        break
                    body   = remaining[:cl].decode(errors="replace")
                    buffer = remaining[cl:]

                    logger.info(f"[SIP] Response: {status}")
                    code = int(status.split(" ")[1])

                    if code == 100:
                        continue
                    if 180 <= code <= 183:
                        continue

                    if code in (401, 407):
                        auth_h = "www-authenticate" if code == 401 else "proxy-authenticate"
                        if auth_h not in headers or not EXOTEL_AUTH_USERNAME:
                            logger.error(f"[SIP] Auth required but no credentials: {status}")
                            return None
                        self._writer.write(self._build_ack())
                        await self._writer.drain()

                        self._cseq  += 1
                        self._branch = f"z9hG4bK-{uuid.uuid4().hex}"
                        uri      = f"sip:{self.callee}@{EXOTEL_SIP_HOST}:{EXOTEL_SIP_PORT}"
                        auth_val = calculate_digest_auth(
                            "INVITE", uri,
                            EXOTEL_AUTH_USERNAME, EXOTEL_AUTH_PASSWORD,
                            headers[auth_h]
                        )
                        self._writer.write(self._build_invite(auth_header=auth_val, proxy_auth=(code == 407)))
                        await self._writer.drain()
                        logger.info("[SIP] Re-INVITE sent with auth")
                        continue

                    if code == 200:
                        self._to_tag = (
                            headers.get("to", "").split("tag=")[-1].split(";")[0]
                            if "tag=" in headers.get("to", "")
                            else None
                        )
                        self._writer.write(self._build_ack())
                        await self._writer.drain()
                        logger.info("[SIP] ✅ Call answered — ACK sent")

                        rip, rport, rpt = None, 0, PCMA_PAYLOAD_TYPE
                        for line in body.splitlines():
                            if line.startswith("c=IN IP4"):
                                rip = line.split()[-1]
                            if line.startswith("m=audio"):
                                parts = line.split()
                                rport = int(parts[1])
                                if len(parts) > 3:
                                    rpt = int(parts[3])
                        logger.info(f"[SIP] Remote media: {rip}:{rport}, PT={rpt}")
                        return {"remote_ip": rip, "remote_port": rport, "pt": rpt}

                    if code >= 400:
                        logger.error(f"[SIP] Call failed: {status}\n{h_block}")
                        return None

            except asyncio.TimeoutError:
                logger.error("[SIP] Timeout waiting for SIP response")
                return None
            except Exception as e:
                logger.error(f"[SIP] Error: {e}")
                return None

    async def wait_for_disconnection(self):
        try:
            while True:
                data = await self._reader.read(4096)
                if not data or b"BYE " in data:
                    break
        except Exception:
            pass

    async def send_bye(self):
        if self._writer:
            try:
                self._writer.write(self._build_bye())
                await self._writer.drain()
                logger.info("[SIP] BYE sent")
            except Exception as e:
                logger.warning(f"[SIP] BYE send error: {e}")

    async def close(self):
        if self._writer:
            try:
                self._writer.close()
                await self._writer.wait_closed()
            except Exception:
                pass


# ─────────────────────────────────────────────────────────────────────────────
# run_bridge — fixed execution order
# ─────────────────────────────────────────────────────────────────────────────

async def run_bridge(phone_number: str, agent_type: str = "invoice", room_name: str | None = None):
    if not room_name:
        room_name = f"sip-bridge-{phone_number}-{uuid.uuid4().hex[:6]}"

    logger.info(f"[BRIDGE] Starting for {phone_number} → room '{room_name}' | RTP port: {RTP_BIND_PORT or 'random'}")

    # ── FIX 3: Use fixed RTP port (set RTP_PORT env var!) ─────────────────
    rtp_bridge = RTPMediaBridge(bind_ip=EXOTEL_MEDIA_IP, bind_port=RTP_BIND_PORT)
    sip_client = ExotelSipClient(callee=phone_number, rtp_port=rtp_bridge.local_port)
    room        = rtc.Room()
    forward_task = None

    try:
        # ── Step 1: Subscribe to agent audio as soon as it arrives ────────
        # Frames are buffered in rtp_bridge._frame_buffer until SIP answers.
        @room.on("track_subscribed")
        def on_track_subscribed(track, publication, participant):
            nonlocal forward_task
            if (
                track.kind == rtc.TrackKind.KIND_AUDIO
                and publication.source == rtc.TrackSource.SOURCE_MICROPHONE
                and forward_task is None
            ):
                logger.info(f"[BRIDGE] Agent audio subscribed from {participant.identity} — buffering until SIP answers")
                forward_task = asyncio.create_task(_forward_agent_audio(track, rtp_bridge))

        # ── Step 2: Connect to LiveKit ─────────────────────────────────────
        token = (
            AccessToken(LK_API_KEY, LK_API_SECRET)
            .with_identity(f"sip-{phone_number}")
            .with_grants(VideoGrants(room_join=True, room=room_name))
            .to_jwt()
        )
        await room.connect(LK_URL, token)
        logger.info(f"[BRIDGE] Connected to LiveKit room: {room_name}")

        # Publish inbound RTP → LiveKit track
        await rtp_bridge.start_inbound(room)

        # ── Step 3: Make SIP call ──────────────────────────────────────────
        await sip_client.connect()
        res = await sip_client.send_invite()
        if not res:
            logger.error("[BRIDGE] SIP call failed — aborting")
            return

        # ── Step 4: Set remote endpoint — this also flushes the audio buffer
        rtp_bridge.set_remote_endpoint(res["remote_ip"], res["remote_port"], res["pt"])

        # ── Step 5: Wait until call ends ───────────────────────────────────
        sip_mon = asyncio.create_task(sip_client.wait_for_disconnection())
        while (
            room.connection_state == rtc.ConnectionState.CONN_CONNECTED
            and not sip_mon.done()
        ):
            await asyncio.sleep(2)

        logger.info("[BRIDGE] Call ended")

    finally:
        if forward_task:
            forward_task.cancel()
            try:
                await forward_task
            except asyncio.CancelledError:
                pass
        await sip_client.send_bye()
        rtp_bridge.stop()
        await sip_client.close()
        await room.disconnect()
        logger.info("[BRIDGE] Cleanup complete")


async def _forward_agent_audio(track: rtc.Track, rtp_bridge: RTPMediaBridge):
    """Forward LiveKit agent audio frames to RTP (with buffering before SIP answer)."""
    stream = rtc.AudioStream(track, sample_rate=48000, num_channels=1)
    async for event in stream:
        await rtp_bridge.send_to_rtp(event.frame)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(run_bridge("08697421450"))