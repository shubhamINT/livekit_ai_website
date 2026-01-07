from livekit.agents import (Agent)
import logging
from agents.banking.banking_agent_prompt import BANKING_AGENT_PROMPT

logger = logging.getLogger("agent")

class BankingAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            # Instructions for the agent
            instructions=BANKING_AGENT_PROMPT,
        )
        self.room = room 

    @property
    def welcome_message(self):
        return ("Hi, This is VYOM your banking agent.")