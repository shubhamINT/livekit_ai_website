import json
import logging
import os
import re
import httpx

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _normalize_phone_number(phone_number: str) -> str:
	# Normalize Indian mobile numbers and return digits in 91XXXXXXXXXX format.
	digits_only = "".join(char for char in str(phone_number or "") if char.isdigit())

	# Accept 10-digit Indian mobiles and auto-prefix 91.
	if len(digits_only) == 10 and digits_only[0] in "6789":
		return f"91{digits_only}"

	# Accept 12-digit format that already includes 91 country code.
	if len(digits_only) == 12 and digits_only.startswith("91") and digits_only[2] in "6789":
		return digits_only

	# Accept local format with leading 0 and normalize to 91XXXXXXXXXX.
	if len(digits_only) == 11 and digits_only.startswith("0") and digits_only[1] in "6789":
		return f"91{digits_only[1:]}"

	return ""


def _sanitize_template_text(value: str, max_len: int = 900) -> str:
	# Meta template variables reject newlines/tabs and long repeated spacing.
	if value is None:
		return ""
	cleaned = re.sub(r"\s+", " ", str(value)).strip()
	return cleaned[:max_len]


async def send_whatsapp_template(
	to: str,
	display_name: str,
	content: str,
	template_name: str | None = None,
):
	"""
	Sends a WhatsApp template message using Meta Graph API.
	"""
	phone_number_id = os.getenv("WHATSAPP_PHONE_NUMBER_ID", "110377482141989")
	access_token = os.getenv("WHATSAPP_ACCESS_TOKEN")
	resolved_template_name = template_name or os.getenv(
		"WHATSAPP_TEMPLATE_NAME", "utility_agui_agent"
	)

	if not access_token:
		logger.error("WHATSAPP_ACCESS_TOKEN is missing.")
		raise ValueError("WhatsApp configuration missing.")

	normalized_to = _normalize_phone_number(to)
	if not normalized_to:
		logger.error("Recipient WhatsApp number is missing or invalid: %s", to)
		raise ValueError(
			"Invalid Indian WhatsApp number. Use a valid 10-digit mobile number (starting 6-9), with or without +91."
		)

	safe_display_name = _sanitize_template_text(display_name, max_len=60)
	safe_content = _sanitize_template_text(content, max_len=900)

	payload = {
		"messaging_product": "whatsapp",
		"to": normalized_to,
		"type": "template",
		"template": {
			"name": resolved_template_name,
			"language": {"code": "en_US"},
			"components": [
				{
					"type": "body",
					"parameters": [
						{"type": "text", "text": safe_display_name or "Traveler"},
						{"type": "text", "text": safe_content},
					],
				}
			],
		},
	}

	url = f"https://graph.facebook.com/v22.0/{phone_number_id}/messages"

	try:
		async with httpx.AsyncClient(timeout=20.0) as client:
			response = await client.post(
				url,
				headers={
					"Authorization": f"Bearer {access_token}",
					"Content-Type": "application/json",
				},
				json=payload,
			)
			response.raise_for_status()
			result = response.json() if response.content else {}
		logger.info("WhatsApp message sent successfully to %s", normalized_to)
		return result
	except httpx.HTTPStatusError as exc:
		error_body = exc.response.text
		logger.error(
			"Failed to send WhatsApp message to %s. HTTP %s: %s",
			normalized_to,
			exc.response.status_code,
			error_body,
		)
		raise RuntimeError(
			f"WhatsApp API request failed with HTTP {exc.response.status_code}."
		) from exc
	except httpx.RequestError as exc:
		logger.error("WhatsApp network error for %s: %s", normalized_to, str(exc))
		raise RuntimeError("WhatsApp API network error.") from exc
	except Exception as exc:
		logger.error("Unexpected WhatsApp send error for %s: %s", normalized_to, str(exc))
		raise
