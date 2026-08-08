import { StreamDetokenizer } from "./tokenize.js";

/**
 * Relays an SSE (Server-Sent Events) ReadableStream to the client
 * response, reversing tokens along the way (if a tokenMap is provided)
 * without ever letting a token split across chunks leak through
 * unreversed. Shared by the real OpenAI provider and the mock streaming
 * providers used for testing, so both exercise the exact same code path.
 */
export async function relaySSEStream(body, res, tokenMap) {
  const streamDetok = new StreamDetokenizer(tokenMap);
  const reader = body.getReader();
  const decoder = new TextDecoder();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value, { stream: true });
      const out = streamDetok.push(text);
      if (out) res.write(out);
    }
    const finalOut = streamDetok.end();
    if (finalOut) res.write(finalOut);
  } finally {
    res.end();
  }
}
