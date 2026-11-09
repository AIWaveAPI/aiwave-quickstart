import OpenAI from "openai";

const apiKey = process.env.AIWAVE_API_KEY;
if (!apiKey?.trim()) {
  console.error("Set AIWAVE_API_KEY to your own AIWave key before running this example.");
  process.exit(2);
}

const client = new OpenAI({
  apiKey,
  baseURL: process.env.AIWAVE_BASE_URL || "https://aiwave.live/v1",
});

const response = await client.chat.completions.create({
  model: process.env.AIWAVE_MODEL || "deepseek-v4-flash",
  messages: [{ role: "user", content: "Say hello in one sentence." }],
  max_tokens: 64,
});
console.log(response.choices[0].message.content);
