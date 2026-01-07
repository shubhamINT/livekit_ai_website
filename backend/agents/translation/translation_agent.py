from livekit.agents import (Agent)
import logging
from agents.translation.translation_agent_prompt import TRANSLATION_AGENT_PROMPT

logger = logging.getLogger("agent")

class TranslationAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            # Instructions for the agent
            instructions=TRANSLATION_AGENT_PROMPT,
        )
        self.room = room 

    @property
    def welcome_message(self):
        return ("Hello John! Happy New Year to you and your family. I heard that you are seeking some services near you. I can help you with that.")