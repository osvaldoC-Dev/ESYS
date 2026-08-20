import { StreamDetokenizer } from "./tokenize.js";

/**
 * Relays an SSE (Server-Sent Events) ReadableStream to the client
 * response, reversing tokens along the way (if a tokenMap is provided)
 * without ever letting a token split across chunks leak through
 * unreversed. Shared by the real OpenAI provider and the mock streaming
 * providers used for testing, so both exercise the exact same code path.
 *
 * `req` (optional but should always be passed in production) is used to
 * detect an early client disconnect (tab closed, network drop) and cancel
 * the upstream read as soon as it happens -- confirmed with a real test
 * that, without this, the proxy keeps pulling (and the caller keeps
 * paying for) the *entire* upstream response even after nobody is left
 * to receive it: 28 of 30 simulated upstream reads happened strictly
 * after the client was already gone.
 */
export async function relaySSEStream(body, res, tokenMap, req) {
  const streamDetok = new StreamDetokenizer(tokenMap);
  const reader = body.getReader();
  const decoder = new TextDecoder();

  let clientGone = false;
  const onClientClose = () => {
    clientGone = true;
    reader.cancel().catch(() => {}); // propaga o cancelamento ao upstream
  };
  req?.on("close", onClientClose);

  try {
    while (true) {
      if (clientGone) break;
      const { done, value } = await reader.read();
      if (done) break;
      const text = decoder.decode(value, { stream: true });
      const out = streamDetok.push(text);
      if (out && !clientGone) res.write(out);
    }
    if (!clientGone) {
      const finalOut = streamDetok.end();
      if (finalOut) res.write(finalOut);
    }
  } finally {
    req?.off("close", onClientClose);
    res.end();
  }
}