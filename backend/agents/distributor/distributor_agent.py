from livekit.agents import (Agent)
import logging
from agents.distributor.distributor_agent_prompt import DISTRIBUTOR_PROMPT
# from agents.shared.tts_humanification_framework import TTS_HUMANIFICATION_FRAMEWORK

logger = logging.getLogger("agent")

class DistributorAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            # Instructions for the agent
            instructions=DISTRIBUTOR_PROMPT,
        )
        self.room = room 

    @property
    def welcome_message(self):
        # welcome_message = f"<emotion value='content' />“Hello sir, good day. May I speak with Avi please?”"
        welcome_message = (
            "Hi i am your distributor assistant. How may I help you today?"
                            )
        return welcome_message