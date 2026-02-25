from livekit.agents import Agent
from agents.kingston.kingston_agent_prompt import KINGSTON_PROMPT
from shared_humanization_prompt.tts_humanification_cartesia import TTS_HUMANIFICATION_CARTESIA

class KingstonAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            # Instructions for the agent
            instructions= KINGSTON_PROMPT + TTS_HUMANIFICATION_CARTESIA,
        )
        self.room = room

    @property
    def welcome_message(self):
        return ("Hello, আমি কিংস্টন এডুকেশনাল ইনস্টিটিউট থেকে ফোন করছি।")