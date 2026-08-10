import { detokenize } from "../tokenize.js";
import { relaySSEStream } from "../stream_relay.js";
import { translateAnthropicStreamToOpenAIShape, toOpenAIResponse } from "./anthropic.js";

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export function forwardToMockAnthropicEcho(req, res) {
  const lastMessage = req.body?.messages?.[req.body.messages.length - 1];
  const content = `You said: ${lastMessage?.content ?? ""}`;
  const tokenMap = req.esysTokenMap ?? null;

  const fakeAnthropicResponse = {
    id: "msg_mock",
    type: "message",
    role: "assistant",
    content: [{ type: "text", text: content }],
  };

  const openaiShaped = toOpenAIResponse(fakeAnthropicResponse);
  if (tokenMap) {
    for (const choice of openaiShaped.choices) {
      choice.message.content = detokenize(choice.message.content, tokenMap);
    }
  }
  res.json(openaiShaped);
}

export async function forwardToMockAnthropicStreamEcho(req, res) {
  const lastMessage = req.body?.messages?.[req.body.messages.length - 1];
  const content = `You said: ${lastMessage?.content ?? ""}`;
  const tokenMap = req.esysTokenMap ?? null;

  const CHUNK_SIZE = 3;
  const anthropicSSE = new ReadableStream({
    async start(controller) {
      const enc = new TextEncoder();
      controller.enqueue(enc.encode('event: message_start\ndata: {"type":"message_start"}\n\n'));
      controller.enqueue(enc.encode('event: content_block_start\ndata: {"type":"content_block_start","index":0}\n\n'));

      for (let i = 0; i < content.length; i += CHUNK_SIZE) {
        const piece = content.slice(i, i + CHUNK_SIZE);
        const event = `event: content_block_delta\ndata: ${JSON.stringify({
          type: "content_block_delta",
          delta: { type: "text_delta", text: piece },
        })}\n\n`;
        controller.enqueue(enc.encode(event));
        await sleep(5);
      }

      controller.enqueue(enc.encode('event: content_block_stop\ndata: {"type":"content_block_stop","index":0}\n\n'));
      controller.enqueue(enc.encode('event: message_stop\ndata: {"type":"message_stop"}\n\n'));
      controller.close();
    },
  });

  res.status(200);
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders?.();

  const translated = translateAnthropicStreamToOpenAIShape(anthropicSSE);
  await relaySSEStream(translated, res, tokenMap);
}
