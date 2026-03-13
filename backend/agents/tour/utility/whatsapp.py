import json
import logging
import os
import httpx

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)


def _normalize_phone_number(phone_number: str) -> str:
	# Keep only digits so API receives a valid destination number.
	return "".join(char for char in phone_number if char.isdigit())


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
		logger.error("Recipient WhatsApp number is missing or invalid.")
		raise ValueError("Recipient WhatsApp number missing.")

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
						{"type": "text", "text": display_name},
						{"type": "text", "text": content},
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
