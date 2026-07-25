const OPENAI_BASE_URL = process.env.OPENAI_BASE_URL || "https://api.openai.com/v1";

/**
 * Forwards an already-inspected request body to OpenAI and streams the
 * response back untouched. V1 does not inspect the response.
 */
export async function forwardToOpenAI(req, res) {
  try {
    const response = await fetch(`${OPENAI_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify(req.body),
    });

    const data = await response.json();
    res.status(response.status).json(data);
  } catch (err) {
    console.error("forwardToOpenAI error:", err);
    res.status(502).json({ error: "provider_unreachable" });
  }
}
