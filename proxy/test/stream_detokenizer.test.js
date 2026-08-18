// Fuzzing adversarial do StreamDetokenizer.
//
// Contexto: docs/07-current-status.md e docs/09-next-steps.md
// documentavam "streaming + redação" como um gap conhecido — um token
// ESYS_TOK_xxxx podia, em teoria, ser cortado ao meio por um chunk de
// rede e vazar por inteiro (ou parcialmente) para o cliente. Este teste
// confirma, com centenas de combinações adversariais de corte, que o
// StreamDetokenizer (tokenize.js) já resolve isto corretamente — o gap
// nos docs estava desatualizado face ao código.
//
// Duas estratégias de corte são testadas, porque representam ameaças
// diferentes:
//   1. Um único evento SSE gigante, cortado byte a byte pela rede
//      (pior caso possível de fragmentação de rede).
//   2. Conteúdo dividido em vários eventos SSE pequenos (o que um LLM
//      real faz — cada delta é só um pedacinho do texto), com cortes de
//      rede adicionais por cima disso.

import { test } from "node:test";
import assert from "node:assert/strict";
import { StreamDetokenizer, detokenize } from "../src/tokenize.js";

function sseEvent(content) {
  return `data: ${JSON.stringify({ choices: [{ delta: { content } }] })}\n\n`;
}

function reconstruct(rawOutput) {
  let text = "";
  for (const block of rawOutput.split("\n\n")) {
    if (!block.startsWith("data: ")) continue;
    const payload = block.slice(6);
    if (payload.trim() === "[DONE]") continue;
    if (!payload.trim()) continue;
    const parsed = JSON.parse(payload); // lança se algum evento ficou JSON inválido
    text += parsed.choices[0].delta.content;
  }
  return text;
}

function runSingleEventCut(tokenMap, fullContent, chunkSizes) {
  const streamDetok = new StreamDetokenizer(tokenMap);
  const rawEvent = sseEvent(fullContent);
  let out = "";
  let i = 0;
  for (const size of chunkSizes) {
    out += streamDetok.push(rawEvent.slice(i, i + size));
    i += size;
  }
  if (i < rawEvent.length) out += streamDetok.push(rawEvent.slice(i));
  out += streamDetok.end();
  return out;
}

function runMultiEventCut(tokenMap, fullContent, pieceLen, networkChunkSize) {
  const pieces = [];
  for (let i = 0; i < fullContent.length; i += pieceLen) {
    pieces.push(fullContent.slice(i, i + pieceLen));
  }
  const rawStream = pieces.map(sseEvent).join("");

  const streamDetok = new StreamDetokenizer(tokenMap);
  let out = "";
  for (let i = 0; i < rawStream.length; i += networkChunkSize) {
    out += streamDetok.push(rawStream.slice(i, i + networkChunkSize));
  }
  out += streamDetok.end();
  return out;
}

test("single-event: corte byte a byte nunca deixa vazar um token nem corrompe o conteúdo", () => {
  const tokenMap = { ESYS_TOK_ab12cd34: "joao@example.com" };
  const fullContent =
    "o meu email é ESYS_TOK_ab12cd34, pode confirmar ESYS_TOK_ab12cd34 outra vez?";
  const expected = detokenize(fullContent, tokenMap);

  const rawLen = sseEvent(fullContent).length;
  const byteSizes = new Array(rawLen).fill(1);
  const out = runSingleEventCut(tokenMap, fullContent, byteSizes);
  const got = reconstruct(out);

  assert.equal(got, expected);
  assert.equal(got.includes("ESYS_TOK_"), false);
});

test("single-event: 200 combinações aleatórias de tamanho de chunk", () => {
  const tokenMap = { ESYS_TOK_ab12cd34: "joao@example.com" };
  const fullContent =
    "o meu email é ESYS_TOK_ab12cd34, pode confirmar ESYS_TOK_ab12cd34 outra vez?";
  const expected = detokenize(fullContent, tokenMap);
  const rawLen = sseEvent(fullContent).length;

  for (let trial = 0; trial < 200; trial++) {
    const sizes = [];
    let remaining = rawLen;
    while (remaining > 0) {
      const size = 1 + Math.floor(Math.random() * 8);
      sizes.push(size);
      remaining -= size;
    }
    const out = runSingleEventCut(tokenMap, fullContent, sizes);
    const got = reconstruct(out);
    assert.equal(got, expected, `trial ${trial} falhou com sizes=${JSON.stringify(sizes)}`);
    assert.equal(got.includes("ESYS_TOK_"), false, `trial ${trial} vazou um token`);
  }
});

test("multi-event: deltas pequenos (como um LLM real manda) cruzados com vários tamanhos de corte de rede", () => {
  const tokenMap = { ESYS_TOK_ab12cd34: "joao@example.com" };
  const fullContent = "o meu email e ESYS_TOK_ab12cd34, confirma?";
  const expected = detokenize(fullContent, tokenMap);

  for (let pieceLen = 1; pieceLen <= 20; pieceLen++) {
    for (const networkChunkSize of [1, 3, 7, 15, 50, 500]) {
      const out = runMultiEventCut(tokenMap, fullContent, pieceLen, networkChunkSize);
      const got = reconstruct(out);
      assert.equal(
        got,
        expected,
        `pieceLen=${pieceLen} networkChunkSize=${networkChunkSize} falhou`
      );
      assert.equal(got.includes("ESYS_TOK_"), false, "vazou um token");
    }
  }
});

test("múltiplos tokens diferentes na mesma mensagem, adjacentes, sobrevivem a corte byte a byte", () => {
  const tokenMap = {
    ESYS_TOK_aaaa1111: "joao@example.com",
    ESYS_TOK_bbbb2222: "+244 923 456 789",
  };
  const fullContent = "contacto: ESYS_TOK_aaaa1111ESYS_TOK_bbbb2222 (sem espaço entre eles)";
  const expected = detokenize(fullContent, tokenMap);

  const rawLen = sseEvent(fullContent).length;
  const out = runSingleEventCut(tokenMap, fullContent, new Array(rawLen).fill(1));
  const got = reconstruct(out);

  assert.equal(got, expected);
  assert.equal(got.includes("ESYS_TOK_"), false);
});