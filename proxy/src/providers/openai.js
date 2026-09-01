import { detokenize } from "../tokenize.js";
import { relaySSEStream } from "../stream_relay.js";
import { inspectOutput, maskTokens, OUTPUT_BLOCKED_MESSAGE } from "../output_inspection.js";

const OPENAI_BASE_URL = process.env.OPENAI_BASE_URL || "https://api.openai.com/v1";

/**
 * Forwards an already-inspected request body to OpenAI.
 *
 * Non-streaming responses are now also inspected on the way OUT, before
 * any token reversal — see output_inspection.js for why that order
 * matters. Streaming output inspection is a separate, harder problem
 * (can't "un-send" already-streamed chunks) and is intentionally out of
 * scope here; streaming responses still only get token reversal, same
 * as before.
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
      if (data?.choices) {
        for (const choice of data.choices) {
          if (typeof choice.message?.content === "string") {
            const outputDecision = await inspectOutput(choice.message.content);
            if (outputDecision.action === "block") {
              choice.message.content = OUTPUT_BLOCKED_MESSAGE;
            } else if (outputDecision.action === "redact") {
              choice.message.content = maskTokens(outputDecision.redacted_payload, outputDecision.token_map);
            } else if (tokenMap) {
              choice.message.content = detokenize(choice.message.content, tokenMap);
            }
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