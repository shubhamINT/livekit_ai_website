from livekit.agents import Agent
from agents.ambuja.ambuja_agent_prompt import AMBUJA_AGENT_PROMPT
from shared_humanization_prompt.tts_humanification_cartesia import TTS_HUMANIFICATION_CARTESIA

class AmbujaAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            # Instructions for the agent
            instructions=AMBUJA_AGENT_PROMPT + TTS_HUMANIFICATION_CARTESIA,
        )
        self.room = room

    @property
    def welcome_message(self):
        return ("Namaskar! I'm Pratiksha from Ambuja Neotia. Main aapko Utalika Luxury ke regarding call kar rahi hoon ... I saw you had some queries earlier, toh socha ek baar clarify kar loon. Do you have a moment to chat?")