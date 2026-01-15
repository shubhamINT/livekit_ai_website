from livekit.agents import (Agent)
import logging
from agents.realestate.realestate_agent_prompt import REALESTATE_PROMOPT
from agents.shared.tts_humanification_framework import TTS_HUMANIFICATION_FRAMEWORK

logger = logging.getLogger("agent")

class RealestateAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            # Instructions for the agent
            instructions=REALESTATE_PROMOPT + TTS_HUMANIFICATION_FRAMEWORK,
        )
        self.room = room 

    @property
    def welcome_message(self):
        return ("<emotion value='content' />Hi, This is VYOM, your realestate calling agent from The House of Abhinandan Lodha. How can I help you today?")