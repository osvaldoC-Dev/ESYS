// Testes do adaptador Anthropic (translateAnthropicStreamToOpenAIShape).
//
// Achado real desta ronda: quando a Anthropic manda um evento "error" a
// meio de um streaming em curso (ex: overloaded_error sob carga -- isto
// acontece de verdade, não é hipotético), o adaptador não tinha nenhum
// caso para esse tipo de evento. Resultado confirmado: o texto já
// recebido chegava bem ao cliente, mas o stream terminava sem [DONE] e
// sem qualquer sinal de que a resposta ficou incompleta -- parecia só
// ter "acabado", não "falhado".

import { test } from "node:test";
import assert from "node:assert/strict";
import { translateAnthropicStreamToOpenAIShape } from "../src/providers/anthropic.js";

function sseEvent(eventName, data) {
  return `event: ${eventName}\ndata: ${JSON.stringify(data)}\n\n`;
}

function fakeAnthropicBody(rawEvents) {
  let i = 0;
  return {
    getReader() {
      return {
        async read() {
          if (i >= rawEvents.length) return { done: true, value: undefined };
          const value = new TextEncoder().encode(rawEvents[i]);
          i++;
          return { done: false, value };
        },
      };
    },
  };
}

async function collect(readableStream) {
  const reader = readableStream.getReader();
  const decoder = new TextDecoder();
  let out = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    out += decoder.decode(value);
  }
  return out;
}

test("caminho normal: texto + message_stop produz [DONE] uma única vez", async () => {
  const events = [
    sseEvent("content_block_delta", {
      type: "content_block_delta",
      delta: { type: "text_delta", text: "olá" },
    }),
    sseEvent("message_stop", { type: "message_stop" }),
  ];
  const out = await collect(translateAnthropicStreamToOpenAIShape(fakeAnthropicBody(events)));

  assert.equal(out.includes('"content":"olá"'), true);
  const doneCount = (out.match(/data: \[DONE\]/g) ?? []).length;
  assert.equal(doneCount, 1);
});

test("evento error a meio do stream: emite [DONE] em vez de terminar em silêncio", async () => {
  const events = [
    sseEvent("content_block_delta", {
      type: "content_block_delta",
      delta: { type: "text_delta", text: "parte da resposta" },
    }),
    sseEvent("error", {
      type: "error",
      error: { type: "overloaded_error", message: "Overloaded" },
    }),
  ];
  const out = await collect(translateAnthropicStreamToOpenAIShape(fakeAnthropicBody(events)));

  assert.equal(out.includes('"content":"parte da resposta"'), true, "o texto antes do erro deve chegar ao cliente");
  assert.equal(out.includes("data: [DONE]"), true, "o cliente nunca deve ficar sem terminador depois de um erro");
});

test("evento error logo no início (sem texto nenhum antes): ainda assim emite [DONE]", async () => {
  const events = [
    sseEvent("error", {
      type: "error",
      error: { type: "api_error", message: "Internal error" },
    }),
  ];
  const out = await collect(translateAnthropicStreamToOpenAIShape(fakeAnthropicBody(events)));

  assert.equal(out.includes("data: [DONE]"), true);
});

test("tipos de evento sem texto (ping, message_start) são ignorados sem quebrar nada", async () => {
  const events = [
    sseEvent("message_start", { type: "message_start" }),
    sseEvent("ping", { type: "ping" }),
    sseEvent("content_block_start", { type: "content_block_start" }),
    sseEvent("content_block_delta", {
      type: "content_block_delta",
      delta: { type: "text_delta", text: "ok" },
    }),
    sseEvent("content_block_stop", { type: "content_block_stop" }),
    sseEvent("message_delta", { type: "message_delta" }),
    sseEvent("message_stop", { type: "message_stop" }),
  ];
  const out = await collect(translateAnthropicStreamToOpenAIShape(fakeAnthropicBody(events)));

  assert.equal(out.includes('"content":"ok"'), true);
  assert.equal(out.includes("data: [DONE]"), true);
});