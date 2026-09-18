import os

from openai import OpenAI


client = OpenAI(
    api_key=os.environ["AIWAVE_API_KEY"],
    base_url=os.getenv("AIWAVE_BASE_URL", "https://aiwave.live/v1"),
)

response = client.chat.completions.create(
    model=os.getenv("AIWAVE_MODEL", "deepseek-v4-pro"),
    messages=[{"role": "user", "content": "Say hello in one sentence."}],
    max_tokens=32,
)
print(response.choices[0].message.content)
