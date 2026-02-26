from livekit.agents import Agent
from agents.kingston.kingston_agent_prompt import KINGSTON_ADMISSION_AGENT_PROMPT
# from shared_humanization_prompt.tts_humanification_cartesia import TTS_HUMANIFICATION_CARTESIA
# from shared_humanization_prompt.tts_humanification_sarvam import TTS_HUMANIFICATION_SARVAM

class KingstonAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            # Instructions for the agent
            instructions= KINGSTON_ADMISSION_AGENT_PROMPT,
        )
        self.room = room

    @property
    def welcome_message(self):
        return ("নমস্কার! আমি Kingston Educational Institute থেকে বলছি। আপনি কি Student এর Guardian বলছেন?")

    @property
    def welcome_instructions(self):
        return ("Start talking to user with - নমস্কার! আমি Kingston Educational Institute থেকে বলছি। আপনি কি Student এর Guardian বলছেন?")