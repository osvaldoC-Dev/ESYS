const OPENAI_BASE_URL = process.env.OPENAI_BASE_URL || "https://api.openai.com/v1";

/**
 * Forwards an already-inspected request body to OpenAI.
 *
 * V1 does not inspect the response (see docs: Non-goals) — only the
 * outbound request is inspected. This function just needs to correctly
 * relay whatever shape of response the client asked for:
 *   - req.body.stream === true  -> OpenAI replies as Server-Sent Events
 *     (text/event-stream); we must keep the connection open and forward
 *     each chunk as it arrives, not buffer the whole thing.
 *   - otherwise                 -> a single JSON response, as before.
 *
 * Before this fix, the code always called response.json() regardless of
 * whether streaming was requested — which breaks (or silently returns
 * garbage) the moment a client sends stream: true, since OpenAI's actual
 * response in that case isn't JSON, it's an SSE stream.
 */
export async function forwardToOpenAI(req, res) {
  const isStreaming = req.body?.stream === true;

  try {
    const response = await fetch(`${OPENAI_BASE_URL}/chat/completions`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        Authorization: `Bearer ${process.env.OPENAI_API_KEY}`,
      },
      body: JSON.stringify(req.body),
    });

    if (!isStreaming) {
      const data = await response.json();
      return res.status(response.status).json(data);
    }

    if (!response.ok) {
      const data = await response.json().catch(() => ({ error: "provider_error" }));
      return res.status(response.status).json(data);
    }

    res.status(response.status);
    res.setHeader("Content-Type", "text/event-stream");
    res.setHeader("Cache-Control", "no-cache");
    res.setHeader("Connection", "keep-alive");
    res.flushHeaders?.();

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    try {
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        res.write(decoder.decode(value, { stream: true }));
      }
    } finally {
      res.end();
    }
  } catch (err) {
    console.error("forwardToOpenAI error:", err);
    if (!res.headersSent) {
      res.status(502).json({ error: "provider_unreachable" });
    } else {
      res.end();
    }
  }
}
