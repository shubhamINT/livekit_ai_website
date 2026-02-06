from livekit.agents import Agent
from agents.distributor.distributor_agent_prompt import DISTRIBUTOR_PROMPT
from shared_humanization_prompt.tts_humanificaiton_elevnlabs import TTS_HUMANIFICATION_ELEVENLABS

class DistributorAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            # Instructions for the agent
            instructions=DISTRIBUTOR_PROMPT + TTS_HUMANIFICATION_ELEVENLABS,
        )
        self.room = room

    @property
    def welcome_message(self):
        # welcome_message = f"<emotion value='content' />"Hello sir, good day. May I speak with Avi please?""
        welcome_message = 'नमस्ते, this is Vilok from आर्य वेद. Am I speaking with सुरेश अग्रवाल?'
        return welcome_message