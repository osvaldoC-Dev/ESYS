import { detokenize } from "../tokenize.js";
import { relaySSEStream } from "../stream_relay.js";

const ANTHROPIC_BASE_URL = process.env.ANTHROPIC_BASE_URL || "https://api.anthropic.com/v1";
const ANTHROPIC_VERSION = "2023-06-01";
const DEFAULT_MAX_TOKENS = 1024;

/**
 * Anthropic's Messages API has a different shape than OpenAI's:
 *   - "system" is a top-level string field, not a message with role
 *     "system" inside the messages array.
 *   - "max_tokens" is REQUIRED (no default on their side).
 *   - Streaming uses named SSE events (event: content_block_delta, etc.)
 *     with text under delta.text, not choices[0].delta.content.
 *
 * To keep the rest of the pipeline (detection, tokenization, the client
 * experience) provider-agnostic, this adapter:
 *   1. Translates an incoming OpenAI-shaped request into Anthropic's shape.
 *   2. Translates Anthropic's response back into OpenAI's shape before
 *      returning it — so token reversal (which expects OpenAI-shaped
 *      JSON/SSE) works unmodified, and so does everything upstream of
 *      this file.
 */

export function toAnthropicRequest(body) {
  const messages = body.messages ?? [];
  const systemParts = messages.filter((m) => m.role === "system").map((m) => m.content);
  const nonSystem = messages.filter((m) => m.role !== "system");

  const anthropicBody = {
    model: body.model,
    max_tokens: body.max_tokens ?? DEFAULT_MAX_TOKENS,
    messages: nonSystem.map((m) => ({ role: m.role, content: m.content })),
    stream: body.stream === true,
  };
  if (systemParts.length > 0) {
    anthropicBody.system = systemParts.join("\n\n");
  }
  return anthropicBody;
}

export function toOpenAIResponse(anthropicData) {
  // LIMITAÇÃO CONHECIDA: só blocos type:"text" são extraídos. Se a
  // Anthropic devolver um bloco tool_use (chamada de ferramenta —
  // comum em uso real do Claude), esse conteúdo é descartado
  // silenciosamente aqui, não só ignorado por acidente. Isto não
  // quebra nada (testado: não há crash, o texto normal continua a
  // funcionar), mas é uma perda real de informação para quem use tool
  // calling através da ESYS. Não é escopo do V1 (ver docs: Non-goals),
  // mas fica documentado para não ser uma surpresa mais tarde.
  const text = (anthropicData.content ?? [])
    .filter((block) => block.type === "text")
    .map((block) => block.text)
    .join("");
  return {
    id: anthropicData.id,
    choices: [{ message: { role: "assistant", content: text } }],
  };
}

/**
 * Reads Anthropic's raw SSE stream and produces a plain ReadableStream
 * emitting OpenAI-shaped SSE text ("data: {choices:[{delta:{content}}]}\n\n"),
 * so it can be fed straight into the existing, already-validated
 * relaySSEStream/StreamDetokenizer without either of them needing to know
 * Anthropic's event format exists.
 */
export function translateAnthropicStreamToOpenAIShape(anthropicBody) {
  return new ReadableStream({
    async start(controller) {
      const reader = anthropicBody.getReader();
      const decoder = new TextDecoder();
      const encoder = new TextEncoder();
      let rawBuffer = "";

      function emit(text) {
        controller.enqueue(encoder.encode(`data: ${JSON.stringify({ choices: [{ delta: { content: text } }] })}\n\n`));
      }

      try {
        while (true) {
          const { done, value } = await reader.read();
          if (done) break;
          rawBuffer += decoder.decode(value, { stream: true });

          let idx;
          while ((idx = rawBuffer.indexOf("\n\n")) !== -1) {
            const block = rawBuffer.slice(0, idx);
            rawBuffer = rawBuffer.slice(idx + 2);

            const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
            if (!dataLine) continue;

            let parsed;
            try {
              parsed = JSON.parse(dataLine.slice(6));
            } catch {
              continue;
            }

            if (parsed.type === "content_block_delta" && parsed.delta?.type === "text_delta") {
              emit(parsed.delta.text);
            } else if (parsed.type === "message_stop") {
              controller.enqueue(encoder.encode("data: [DONE]\n\n"));
            }
            // Mesma limitação conhecida do lado streaming: deltas do tipo
            // "input_json_delta" (chamadas de ferramentas) não são
            // extraídos, ficam silenciosamente sem efeito no output.
            // outros tipos (message_start, content_block_start/stop,
            // message_delta, ping) não transportam texto -- ignorados.
          }
        }
        controller.close();
      } catch (err) {
        controller.error(err);
      }
    },
  });
}

export async function forwardToAnthropic(req, res) {
  const isStreaming = req.body?.stream === true;
  const tokenMap = req.esysTokenMap ?? null;
  const anthropicBody = toAnthropicRequest(req.body ?? {});

  try {
    const response = await fetch(`${ANTHROPIC_BASE_URL}/messages`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-api-key": process.env.ANTHROPIC_API_KEY,
        "anthropic-version": ANTHROPIC_VERSION,
      },
      body: JSON.stringify(anthropicBody),
    });

    if (!isStreaming) {
      const data = await response.json();
      if (!response.ok) {
        return res.status(response.status).json(data);
      }
      const openaiShaped = toOpenAIResponse(data);
      if (tokenMap) {
        for (const choice of openaiShaped.choices) {
          choice.message.content = detokenize(choice.message.content, tokenMap);
        }
      }
      return res.status(response.status).json(openaiShaped);
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

    const translated = translateAnthropicStreamToOpenAIShape(response.body);
await relaySSEStream(translated, res, tokenMap, req);
  } catch (err) {
    console.error("forwardToAnthropic error:", err);
    if (!res.headersSent) {
      res.status(502).json({ error: "provider_unreachable" });
    } else {
      res.end();
    }
  }
}