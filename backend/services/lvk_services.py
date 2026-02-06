import os
import json
import logging
from contextlib import asynccontextmanager
from typing import Optional
from livekit.api import (
    LiveKitAPI,
    CreateRoomRequest,
    CreateAgentDispatchRequest,
    CreateSIPParticipantRequest,
    ListRoomsRequest
)
from livekit.protocol.sip import (
    CreateSIPOutboundTrunkRequest,
    SIPOutboundTrunkInfo,
    ListSIPOutboundTrunkRequest
)
from google.protobuf.json_format import MessageToDict

logger = logging.getLogger(__name__)


@asynccontextmanager
async def get_livekit_api():
    """
    Context manager for LiveKitAPI that handles initialization and cleanup.
    
    Usage:
        async with get_livekit_api() as lkapi:
            # Use lkapi here
            rooms = await lkapi.room.list_rooms(...)
    """
    lkapi = LiveKitAPI(
        os.getenv("LIVEKIT_URL"),
        os.getenv("LIVEKIT_API_KEY"),
        os.getenv("LIVEKIT_API_SECRET"),
    )
    try:
        yield lkapi
    finally:
        await lkapi.aclose()


async def create_room(
    room_name: str,
    agent: str,
    empty_timeout: int = 30,
    max_participants: int = 2,
    metadata: Optional[dict] = None
):
    """
    Create a LiveKit room with the specified parameters.
    
    Args:
        room_name: Unique name for the room
        agent: Agent type/name
        empty_timeout: Timeout in seconds after last participant leaves
        max_participants: Maximum number of participants allowed
        metadata: Optional metadata dictionary to attach to the room
        
    Returns:
        Room object from LiveKit API
        
    Raises:
        Exception: If room creation fails
    """
    logger.info(f"Creating room: {room_name} with agent: {agent}")
    
    if metadata is None:
        metadata = {"agent": agent}
    elif "agent" not in metadata:
        metadata["agent"] = agent
    
    async with get_livekit_api() as lkapi:
        room = await lkapi.room.create_room(
            CreateRoomRequest(
                name=room_name,
                empty_timeout=empty_timeout,
                max_participants=max_participants,
                metadata=json.dumps(metadata)
            )
        )
        logger.info(f"Created room: {room.name} (sid: {room.sid})")
        return room


async def list_rooms() -> list[str]:
    """
    Get a list of all active room names.
    
    Returns:
        List of room names
    """
    logger.info("Fetching list of rooms")
    
    async with get_livekit_api() as lkapi:
        rooms = await lkapi.room.list_rooms(ListRoomsRequest())
        room_names = [room.name for room in rooms.rooms]
        logger.info(f"Retrieved {len(room_names)} rooms")
        return room_names


async def create_agent_dispatch(
    room: str,
    agent_name: str,
    metadata: Optional[dict] = None
):
    """
    Create an agent dispatch request for a room.
    
    Args:
        room: Room name to dispatch agent to
        agent_name: Name of the agent to dispatch
        metadata: Optional metadata dictionary for the dispatch
        
    Returns:
        Dispatch object from LiveKit API
        
    Raises:
        Exception: If dispatch creation fails
    """
    logger.info(f"Creating dispatch for agent={agent_name} in room={room}")
    
    if metadata is None:
        metadata = {}
    
    async with get_livekit_api() as lkapi:
        dispatch = await lkapi.agent_dispatch.create_dispatch(
            CreateAgentDispatchRequest(
                room=room,
                agent_name=agent_name,
                metadata=json.dumps(metadata)
            )
        )
        logger.info(f"Agent dispatched | agent={agent_name} room={room}")
        return dispatch


async def create_sip_participant(
    room_name: str,
    trunk_id: str,
    call_to: str,
    identity: str,
    metadata: Optional[dict] = None,
    krisp_enabled: bool = True
):
    """
    Create a SIP participant in a room to make an outbound call.
    
    Args:
        room_name: Room to add the SIP participant to
        trunk_id: SIP trunk ID to use for the call
        call_to: Phone number to call
        identity: Participant identity
        metadata: Optional metadata dictionary for the participant
        krisp_enabled: Whether to enable Krisp noise cancellation
        
    Returns:
        SIP participant object from LiveKit API
        
    Raises:
        Exception: If SIP participant creation fails
    """
    logger.info(f"Creating SIP participant: calling {call_to} in room {room_name}")
    
    if metadata is None:
        metadata = {}
    
    async with get_livekit_api() as lkapi:
        sip_participant = await lkapi.sip.create_sip_participant(
            CreateSIPParticipantRequest(
                room_name=room_name,
                sip_trunk_id=trunk_id,
                sip_call_to=call_to,
                participant_identity=identity,
                participant_metadata=json.dumps(metadata),
                krisp_enabled=krisp_enabled,
            )
        )
        logger.info(f"SIP participant created for {call_to}")
        return sip_participant


async def create_sip_outbound_trunk(
    trunk_name: str,
    trunk_address: str,
    trunk_numbers: list,
    trunk_auth_username: str,
    trunk_auth_password: str
):
    """
    Create a SIP outbound trunk configuration.
    
    Args:
        trunk_name: Name for the trunk
        trunk_address: SIP server address
        trunk_numbers: List of phone numbers associated with trunk
        trunk_auth_username: Authentication username
        trunk_auth_password: Authentication password
        
    Returns:
        Created trunk info from LiveKit API
        
    Raises:
        Exception: If trunk creation fails
    """
    logger.info(f"Creating SIP outbound trunk: {trunk_name}")
    
    async with get_livekit_api() as lkapi:
        trunk_info = SIPOutboundTrunkInfo(
            name=trunk_name,
            address=trunk_address,
            numbers=trunk_numbers,
            auth_username=trunk_auth_username,
            auth_password=trunk_auth_password
        )
        
        request = CreateSIPOutboundTrunkRequest(trunk=trunk_info)
        trunk = await lkapi.sip.create_sip_outbound_trunk(request)
        
        logger.info(f"Successfully created trunk: {trunk_name}")
        return trunk


async def list_sip_outbound_trunks():
    """
    List all configured SIP outbound trunks.
    
    Returns:
        Dictionary containing list of trunks
        
    Raises:
        Exception: If listing fails
    """
    logger.info("Listing SIP outbound trunks")
    
    async with get_livekit_api() as lkapi:
        trunks = await lkapi.sip.list_sip_outbound_trunk(
            ListSIPOutboundTrunkRequest()
        )
        trunks_dict = MessageToDict(trunks)
        logger.info(f"Successfully listed outbound trunks")
        return trunks_dict


def format_success_response(message: str, data: dict) -> dict:
    """
    Format a standardized success response.
    
    Args:
        message: Success message
        data: Response data
        
    Returns:
        Formatted response dictionary
    """
    return {
        "status": 0,
        "message": message,
        "data": data
    }


def format_error_response(message: str, error: Exception = None) -> dict:
    """
    Format a standardized error response.
    
    Args:
        message: Error message
        error: Optional exception object
        
    Returns:
        Formatted error response dictionary
    """
    error_msg = f"{message}: {error}" if error else message
    return {
        "status": -1,
        "message": error_msg,
        "data": {}
    }
