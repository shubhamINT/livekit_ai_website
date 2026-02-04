
from pydantic import BaseModel
from typing import Literal

class OutboundTrunkCreate(BaseModel):
    trunk_name: str
    trunk_address: str
    trunk_numbers: list
    trunk_auth_username: str
    trunk_auth_password: str
    trunk_type: Literal["exotel", "twilio"]


# OUTBOUND CALL
class OutboundCallRequest(BaseModel):
    phone_number: str
    agent_type: str = "invoice"
    call_from: Literal["exotel", "twilio"] = "exotel"

# SIP TEST
class SIPTestRequest(BaseModel):
    exotel_ip: str
    exotel_port: int
    customer_ip: str
    customer_port: int
    media_ip: str
    rtp_port: int
    caller: str
    callee: str
