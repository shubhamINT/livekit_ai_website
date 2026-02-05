import uuid
import random
import socket


def make_exotel_call(
    exotel_ip: str,
    exotel_port: int,
    customer_ip: str,
    customer_port: int,
    media_ip: str,
    rtp_port: int,
    caller: str,      # Exophone (CLI)
    callee: str       # Destination number
) -> dict:
    """
    Makes an outbound SIP call through Exotel.
    
    Returns dict with 'invite_sent' and 'response_received'.
    """
    
    # ─── SIP Header Helpers ─────────────────────────────────────────────
    def _generate_branch() -> str:
        return f"z9hG4bK-{uuid.uuid4().hex}"
    
    def _generate_call_id(domain: str) -> str:
        return f"{uuid.uuid4()}@{domain}"
    
    def _generate_tag() -> str:
        return str(random.randint(100000, 999999))
    
    # ─── SDP Builder ────────────────────────────────────────────────────
    def _build_sdp(media_ip: str, rtp_port: int) -> str:
        return f"""v=0
o=root 1002281923 1002281923 IN IP4 {media_ip}
c=IN IP4 {media_ip}
t=0 0
m=audio {rtp_port} RTP/AVP 8 0 101
a=rtpmap:8 PCMA/8000
a=rtpmap:0 PCMU/8000
a=rtpmap:101 telephone-event/8000
a=fmtp:101 0-16
a=ptime:20
a=maxptime:150
a=sendrecv
"""
    
    # ─── INVITE Builder ─────────────────────────────────────────────────
    def _build_invite() -> bytes:
        branch = _generate_branch()
        tag = _generate_tag()
        call_id = _generate_call_id("lokaviveka1m.pstn.exotel.com")
        
        sdp = _build_sdp(media_ip, rtp_port)
        content_length = len(sdp.encode())
        
        invite = f"""INVITE sip:{callee}@{exotel_ip}:{exotel_port} SIP/2.0
Via: SIP/2.0/TCP {customer_ip}:{customer_port};branch={branch}
Max-Forwards: 70
From: "{caller}" <sip:{caller}@lokaviveka1m.pstn.exotel.com>;tag={tag}
To: <sip:{callee}@{exotel_ip}>
Contact: <sip:{caller}@{customer_ip}:{customer_port};transport=tcp>
Call-ID: {call_id}
CSeq: 1 INVITE
Allow: INVITE, ACK, CANCEL, OPTIONS, BYE
Supported: replaces, timer
Content-Type: application/sdp
Content-Length: {content_length}

{sdp}"""
        
        return invite.encode()
    
    # ─── TCP Transport ──────────────────────────────────────────────────
    def _send_tcp(message: bytes) -> str:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        
        try:
            sock.connect((exotel_ip, exotel_port))
            sock.sendall(message)
            response = sock.recv(4096)
            return response.decode(errors="ignore")
        finally:
            sock.close()
    
    # ─── Execute ────────────────────────────────────────────────────────
    invite_msg = _build_invite()
    response = _send_tcp(invite_msg)
    
    return {
        "invite_sent": invite_msg.decode(),
        "response_received": response
    }


# ─── Example Usage ──────────────────────────────────────────────────────
if __name__ == "__main__":
    result = make_exotel_call(
        exotel_ip="pstn.in4.exotel.com",              # Provided by Exotel
        exotel_port=5070,
        customer_ip="13.234.150.174",
        customer_port=5061,
        media_ip="13.234.150.174",
        rtp_port=18232,
        caller="+918044319240",           # Exophone
        callee="+918697421450"            # Destination number
    )
    
    print("===== SIP INVITE =====")
    print(result["invite_sent"])
    
    print("\n===== SIP RESPONSE =====")
    print(result["response_received"])