from livekit.agents import Agent
from agents.bandhan_banking.bandhan_banking_prompt import BANDHAN_BANKING_AGENT_PROMPT
from shared_humanization_prompt.tts_humanification_cartesia import TTS_HUMANIFICATION_CARTESIA
from shared_humanization_prompt.tts_humanificaiton_elevnlabs import TTS_HUMANIFICATION_ELEVENLABS

class BandhanBankingAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            # Instructions for the agent
            instructions=BANDHAN_BANKING_AGENT_PROMPT + TTS_HUMANIFICATION_CARTESIA,
        )
        self.room = room

    @property
    def welcome_message(self):
        return ("Hi, This is VYOM your bandhan banking agent.")