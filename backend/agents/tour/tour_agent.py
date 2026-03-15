from livekit.agents import function_tool, Agent, RunContext
from agents.tour.utility.email import send_email
from agents.tour.utility.whatsapp import send_whatsapp_template
from agents.tour.tour_agent_prompt import TOUR_AGENT_PROMPT
from shared_humanization_prompt.tts_humanification_cartesia import TTS_HUMANIFICATION_CARTESIA
# from shared_humanization_prompt.tts_humanification_sarvam import TTS_HUMANIFICATION_SARVAM
from jinja2 import Environment, FileSystemLoader
import os
import asyncio
import re
import logging

logger = logging.getLogger(__name__)
 


# Load Jinja environment once at module level
TEMPLATE_DIR = os.path.dirname(__file__)
jinja_env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))


def _run_background(coro, task_name: str) -> None:
    task = asyncio.create_task(coro)

    def _done_callback(done_task: asyncio.Task) -> None:
        try:
            done_task.result()
            logger.info("Background task succeeded: %s", task_name)
        except Exception:
            logger.exception("Background task failed: %s", task_name)

    task.add_done_callback(_done_callback)

def _build_whatsapp_content(payload: dict) -> str:
    guest_name = payload.get("guest_name") or "Traveler"
    lines = []

    lines.append(f"🌿 *Jharkhand Travel Plan*")
    lines.append("")
    lines.append(f"🙏 Johar {guest_name}!")
    lines.append("Here is your personalized travel itinerary for Jharkhand.")
    lines.append("")
    lines.append("───────────────────────")
    lines.append("🗺️ *ITINERARY*")
    lines.append("───────────────────────")

    ordinals = {
        1: "पहला दिन", 2: "दूसरा दिन", 3: "तीसरा दिन",
        4: "चौथा दिन", 5: "पाँचवाँ दिन", 6: "छठा दिन",
        7: "सातवाँ दिन"
    }

    days = payload.get("days") or []
    for day in days:
        num = day.get("number", 1)
        theme = day.get("theme", "")
        activities = day.get("activities") or []
        stay = day.get("stay", "")

        day_label = ordinals.get(num, f"दिन {num}")
        lines.append("")
        lines.append(f"*{day_label}* 🌄")
        if theme:
            lines.append(f"_{theme}_")
        if activities:
            lines.append(", ".join(activities) + ".")
        if stay:
            lines.append(f"🏨 *Stay:* {stay}")

    tips = payload.get("tips") or []
    if tips:
        lines.append("")
        lines.append("───────────────────────")
        lines.append("💡 *TRAVEL TIPS*")
        lines.append("───────────────────────")
        for tip in tips:
            lines.append(f"• {tip}")

    lines.append("")
    lines.append("───────────────────────")
    lines.append("_For bookings & more information:_")
    lines.append("🌐 tourism.jharkhand.gov.in")
    lines.append("")
    lines.append("🙏 *Happy Travels! — Team JTDC* 🌿")
    lines.append("───────────────────────")

    return "\n".join(lines)[:900]

def _sanitize_template_text(value: str, max_len: int = 900) -> str:
    if value is None:
        return ""
    # Preserve newlines for WhatsApp formatting, only collapse spaces within each line
    lines = str(value).splitlines()
    cleaned_lines = [re.sub(r" {2,}", " ", line).strip() for line in lines]
    cleaned = "\n".join(cleaned_lines).strip()
    return cleaned[:max_len]

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
 
        tourist_email: the recipient's email address. ALWAYS use "souvik.chaki@intglobal.com".
 
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
        # FIX 2: suppress ctx (consistent with send_travel_whatsapp)
        _ = ctx
 
        try:
            logger.info("send_travel_email called for: %s", tourist_email)

            template = jinja_env.get_template("utility/emailtemplate.html")
            html_body = template.render(**payload)

            # Build subject from whatever is available in payload
            subject_parts = ["🗺️ Your Jharkhand Travel Plan"]
            if payload.get("trip_duration"):
                subject_parts.append(f"| {payload['trip_duration']}")
            if payload.get("booking_id"):
                subject_parts.append(f"| Booking #{payload['booking_id']}")
            subject = " ".join(subject_parts)

            _run_background(
                send_email(
                    to=tourist_email,
                    subject=subject,
                    html_body=html_body,
                ),
                task_name=f"tour_email:{tourist_email}",
            )

            return (
                f"Email dispatch queued to {tourist_email}. "
                f"Tell the user: Perfect, I have sent your travel plan to {tourist_email}. 📬"
            )

        except Exception as e:
            logger.exception("send_travel_email FAILED before dispatch for %s: %s", tourist_email, e)
            return (
                f"Failed to queue email: {str(e)}. "
                "Tell the user: Sorry, I wasn't able to send the email right now. "
                "Please try again in a moment."
            )
 

    @function_tool
    async def send_travel_whatsapp(
        self,
        payload: dict | None = None,
        tourist_whatsapp: str | None = None,
        *,
        ctx: RunContext,
    ):
        """
        Send travel details on WhatsApp at any point in the conversation.

        tourist_whatsapp: recipient WhatsApp number (country code + number).
        payload: send whatever context is known so far.
        """
        _ = ctx
        payload = payload or {}

        try:
            whatsapp_number = tourist_whatsapp or os.getenv("TOUR_DEFAULT_WHATSAPP_TO")
            if not whatsapp_number:
                raise ValueError("Tourist WhatsApp number is required.")

            display_name = payload.get("guest_name") or "Traveler"
            content = _build_whatsapp_content(payload)
            print("Composed WhatsApp content:", content)
            _run_background(
                send_whatsapp_template(
                    to=whatsapp_number,
                    display_name=display_name,
                    content=content,
                ),
                task_name=f"tour_whatsapp:{whatsapp_number}",
            )

            return (
                f"WhatsApp dispatch queued to {whatsapp_number}. "
                "Tell the user: Perfect, I have shared your travel details on WhatsApp."
            )

        except Exception as e:
            return (
                f"Failed to send WhatsApp details: {str(e)}. "
                "Tell the user: Sorry, I could not send the WhatsApp message right now. "
                "Please try again in a moment."
            )