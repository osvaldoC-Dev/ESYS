import { relaySSEStream } from "../stream_relay.js";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function forwardToMockStreamEchoProvider(req, res) {
  const lastMessage = req.body?.messages?.[req.body.messages.length - 1];
  const content = `You said: ${lastMessage?.content ?? ""}`;
  const tokenMap = req.esysTokenMap ?? null;

  const CHUNK_SIZE = 3;
  const body = new ReadableStream({
    async start(controller) {
      for (let i = 0; i < content.length; i += CHUNK_SIZE) {
        const piece = content.slice(i, i + CHUNK_SIZE);
        const event = `data: ${JSON.stringify({ choices: [{ delta: { content: piece } }] })}\n\n`;
        controller.enqueue(new TextEncoder().encode(event));
        await sleep(5);
      }
      controller.enqueue(new TextEncoder().encode("data: [DONE]\n\n"));
      controller.close();
    },
  });

  res.status(200);
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders?.();

  await relaySSEStream(body, res, tokenMap);
}
