from livekit.agents import function_tool, Agent, RunContext
from agents.tour.utility.email import send_email
from agents.tour.utility.whatsapp import send_whatsapp_template
from agents.tour.tour_agent_prompt import TOUR_AGENT_PROMPT
from shared_humanization_prompt.tts_humanification_cartesia import TTS_HUMANIFICATION_CARTESIA
from jinja2 import Environment, FileSystemLoader
import os
import asyncio


# Load Jinja environment once at module level
TEMPLATE_DIR = os.path.dirname(__file__)
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def _build_whatsapp_content(payload: dict) -> str:
    # Keep content concise for template variable limits.
    lines = ["Your Jharkhand travel details:"]

    if payload.get("starting_city"):
        lines.append(f"Starting city: {payload['starting_city']}")
    if payload.get("trip_duration"):
        lines.append(f"Duration: {payload['trip_duration']}")
    if payload.get("travel_pace"):
        lines.append(f"Pace: {payload['travel_pace']}")
    if payload.get("group_type"):
        lines.append(f"Group: {payload['group_type']}")

    days = payload.get("days") or []
    if days:
        lines.append("Itinerary:")
        for day in days:
            day_number = day.get("number", "?")
            theme = day.get("theme", "")
            activities = day.get("activities") or []
            day_line = f"Day {day_number}"
            if theme:
                day_line += f": {theme}"
            if activities:
                day_line += f" | {', '.join(activities)}"
            lines.append(day_line)

    if payload.get("property_name"):
        lines.append(f"Stay: {payload['property_name']}")
    if payload.get("check_in") and payload.get("check_out"):
        lines.append(f"Dates: {payload['check_in']} to {payload['check_out']}")
    if payload.get("booking_id"):
        lines.append(f"Booking ID: {payload['booking_id']}")

    composed_content = "\n".join(lines)
    return composed_content[:900]


class TourAgent(Agent):
    def __init__(self, room) -> None:
        super().__init__(
            instructions=TOUR_AGENT_PROMPT + TTS_HUMANIFICATION_CARTESIA,
        )
        self.room = room

    @property
    def welcome_message(self):
        return (
            "वनों की धरती में आपका स्वागत है, "
            "मैं प्रतीक्षा, आपकी आधिकारिक झारखंड पर्यटन JTDC कंसीयर्ज हूं। "
            "आज आपकी यात्रा की योजना बनाने में मैं आपकी कैसे मदद कर सकती हूं?"
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

    @function_tool
    async def send_travel_whatsapp(
        self,
        payload: dict,
        tourist_whatsapp: str | None,
        ctx: RunContext,
    ):
        """
        Send travel details on WhatsApp at any point in the conversation.

        tourist_whatsapp: recipient WhatsApp number (country code + number).
        payload: send whatever context is known so far.
        """
        _ = ctx

        try:
            whatsapp_number = tourist_whatsapp or os.getenv("TOUR_DEFAULT_WHATSAPP_TO")
            if not whatsapp_number:
                raise ValueError("Tourist WhatsApp number is required.")

            display_name = payload.get("guest_name") or "Traveler"
            content = _build_whatsapp_content(payload)
            print("Composed WhatsApp content:", content)
            # Run in background so voice conversation does not block.
            asyncio.create_task(
                send_whatsapp_template(
                    to=whatsapp_number,
                    display_name=display_name,
                    content=content,
                )
            )

            return (
                f"WhatsApp details sent successfully to {whatsapp_number}. "
                "Tell the user: Perfect, I have shared your travel details on WhatsApp."
            )

        except Exception as e:
            return (
                f"Failed to send WhatsApp details: {str(e)}. "
                "Tell the user: Sorry, I could not send the WhatsApp message right now. "
                "Please try again in a moment."
            )