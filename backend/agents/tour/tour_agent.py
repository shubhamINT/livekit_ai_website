from livekit.agents import function_tool, Agent, RunContext
from agents.tour.utility.email import send_email
from agents.tour.tour_agent_prompt import TOUR_AGENT_PROMPT
from shared_humanization_prompt.tts_humanification_cartesia import TTS_HUMANIFICATION_CARTESIA
from jinja2 import Environment, FileSystemLoader
import os
import asyncio


# Load Jinja environment once at module level
TEMPLATE_DIR = os.path.dirname(__file__)
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


class TourAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            instructions=TOUR_AGENT_PROMPT + TTS_HUMANIFICATION_CARTESIA,
        )
        self.room = room

    @property
    def welcome_message(self):
        return (
            "Welcome to the Land of Forests, "
            "I am Pratiksha, your official Jharkhand Tourism JTDC Concierge. "
            "How can I help you plan your trip today?"
        )

    @function_tool
    async def send_travel_email(
        self,
        tourist_email: str,
        payload: dict,
        ctx: RunContext,                  # must be last
    ):
        """
        Send a travel summary email to the tourist at ANY point in the conversation.
        Call this tool whenever the user asks to send an email — even mid-conversation.

        tourist_email: the recipient's email address. Always ask the user for this if not known.

        payload: collect ONLY what is known so far from the conversation. 
                 Do NOT wait for all fields — send with whatever is available.
                 All keys are optional except tourist_email.

        Payload schema (include only known keys):
        {
            "guest_name"         : str,
            "starting_city"      : str,
            "trip_duration"      : str,       e.g. "2 Days / 2 Nights"
            "travel_pace"        : str,       "Relaxed" or "Packed"
            "group_type"         : str,       "Family" / "Couple" / "Solo"

            "days": [
                {
                    "number"     : int,
                    "theme"      : str,
                    "activities" : [str],
                    "stay"       : str
                }
            ],

            "weather_advisory"   : str,
            "food_suggestion"    : str,
            "accessibility_note" : str,
            "tips"               : [str],

            "booking_id"         : str,
            "property_name"      : str,
            "check_in"           : str,
            "check_out"          : str,
            "num_guests"         : str,
            "tariff"             : str,
        }
        """
        try:
            template = jinja_env.get_template("utility/emailtemplate.html")
            html_body = template.render(**payload)

            # Build subject from whatever is available in payload
            subject_parts = ["🗺️ Your Jharkhand Travel Plan"]
            if payload.get("trip_duration"):
                subject_parts.append(f"| {payload['trip_duration']}")
            if payload.get("booking_id"):
                subject_parts.append(f"| Booking #{payload['booking_id']}")
            subject = " ".join(subject_parts)

            # Send email in background
            asyncio.create_task(
                send_email(
                    to=tourist_email,
                    subject=subject,
                    html_body=html_body,
                )
            )

            return (
                f"Email sent successfully to {tourist_email}. "
                "Tell the user: Your Jharkhand travel plan is on its way — check your inbox! 📬"
            )

        except Exception as e:
            return (
                f"Failed to send email: {str(e)}. "
                "Tell the user: Sorry, I wasn't able to send the email right now. "
                "Please try again in a moment."
            )