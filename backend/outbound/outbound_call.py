import asyncio
import json
import os
import logging
import sys
from dotenv import load_dotenv
from livekit import api
from livekit.protocol.sip import CreateSIPOutboundTrunkRequest, SIPOutboundTrunkInfo
import random

load_dotenv(override=True)

logger = logging.getLogger("make-call")
logger.setLevel(logging.INFO)

room_name = "outbound-call"
# outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID_TWILIO")
outbound_trunk_id = os.getenv("SIP_OUTBOUND_TRUNK_ID_EXOTEL")

# Make outbout call
async def make_call(phone_number: str, agent_type: str = "invoice"):
    """Create a dispatch and add a SIP participant to call the phone number"""
    
    lkapi = api.LiveKitAPI()

    # Ensure unique room name
    unique_room_name = f"{room_name}-{phone_number[-4:]}-{random.randint(1000, 9999)}"
    
    metadata = json.dumps({"agent": agent_type, "phone": phone_number, "call_type": "outbound"})
    
    logger.info(f"Creating dispatch for agent {agent_type} in room {unique_room_name} trunk id {outbound_trunk_id}")
    dispatch = await lkapi.agent_dispatch.create_dispatch(
        api.CreateAgentDispatchRequest(
            agent_name=agent_type, room=unique_room_name, metadata=metadata
        )
    )
    logger.info(f"Created dispatch: {dispatch}")

    # if not outbound_trunk_id or not outbound_trunk_id.startswith("ST_"):
    #     logger.error("SIP_OUTBOUND_TRUNK_ID is not set or invalid")
    #     await lkapi.aclose()
    #     return

    logger.info(f"Dialing {phone_number} to room {unique_room_name}")

    try:
        sip_participant = await lkapi.sip.create_sip_participant(
            api.CreateSIPParticipantRequest(
                room_name=unique_room_name,
                sip_trunk_id=outbound_trunk_id,
                sip_call_to=phone_number,
                participant_identity="phone_user",
                participant_metadata=metadata,
                krisp_enabled=True
            )
        )
        logger.info(f"Created SIP participant: {sip_participant}")
    except Exception as e:
        logger.error(f"Error creating SIP participant: {e}")

    await lkapi.aclose()

# Create outbound trunk
async def create_outbound_trunk( trunk_name: str = "", 
                                trunk_address: str = "", 
                                trunk_numbers: list = [], 
                                trunk_auth_username: str = "", 
                                trunk_auth_password: str = ""
                                ):
    lkapi = api.LiveKitAPI()
    try:
        trunk = SIPOutboundTrunkInfo(
            name = trunk_name,
            address = trunk_address,
            numbers = trunk_numbers,
            auth_username = trunk_auth_username,
            auth_password = trunk_auth_password
        )

        request = CreateSIPOutboundTrunkRequest(
            trunk = trunk
        )

        trunk = await lkapi.sip.create_sip_outbound_trunk(request)

        print(f"Successfully created {trunk}")

        await lkapi.aclose()
        
        payload = {
            "status" : "success",
            "message" : f"Successfully created {trunk}"
        }
        return payload
    except Exception as e:
        logger.error(f"Error creating outbound trunk: {e}")
        await lkapi.aclose()
        payload = {
            "status" : "error",
            "message" : f"Error creating outbound trunk: {e}"
        }
        return payload
