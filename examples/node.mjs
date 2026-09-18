import OpenAI from "openai";

const client = new OpenAI({
  apiKey: process.env.AIWAVE_API_KEY,
  baseURL: process.env.AIWAVE_BASE_URL || "https://aiwave.live/v1",
});

const response = await client.chat.completions.create({
  model: process.env.AIWAVE_MODEL || "deepseek-v4-flash",
  messages: [{ role: "user", content: "Say hello in one sentence." }],
  max_tokens: 64,
});
console.log(response.choices[0].message.content);
