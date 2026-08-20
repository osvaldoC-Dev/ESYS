import { detokenize } from "../tokenize.js";
import { relaySSEStream } from "../stream_relay.js";

const OPENAI_BASE_URL = process.env.OPENAI_BASE_URL || "https://api.openai.com/v1";

/**
 * Forwards an already-inspected request body to OpenAI.
 *
 * V1 does not inspect the response for NEW findings (see docs: Non-goals)
 * — but if the outbound request was tokenized (redact), we do reverse
 * those specific tokens back to their real values in the response, so the
 * user sees a normal, coherent reply instead of literal "ESYS_TOK_xxxx"
 * strings. The real values never left this process.
 *
 * Handles both response shapes:
 *   - req.body.stream === true  -> OpenAI replies as Server-Sent Events
 *     (text/event-stream); relaySSEStream reverses tokens chunk-safely.
 *   - otherwise                 -> a single JSON response; token reversal
 *     is applied directly, since we have the full text at once.
 */
export async function forwardToOpenAI(req, res) {
  const isStreaming = req.body?.stream === true;
  const tokenMap = req.esysTokenMap ?? null;

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
      if (tokenMap && data?.choices) {
        for (const choice of data.choices) {
          if (choice.message?.content) {
            choice.message.content = detokenize(choice.message.content, tokenMap);
          }
        }
      }
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

await relaySSEStream(response.body, res, tokenMap, req);
  } catch (err) {
    console.error("forwardToOpenAI error:", err);
    if (!res.headersSent) {
      res.status(502).json({ error: "provider_unreachable" });
    } else {
      res.end();
    }
  }
}
