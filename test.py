from openai import OpenAI
from dotenv import load_dotenv
load_dotenv()
import os
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = OpenAI()

response = client.responses.create(
    model="gpt-4.1",
    tools=[{ "type": "web_search_preview" }],
    input="founder of indus net technologies",
    prompt_cache_retention = "24h",
)

print(response.output_text)
