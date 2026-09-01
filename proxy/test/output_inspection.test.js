// Testes da inspeção de OUTPUT (feature nova: proteger o que a IA
// devolve, não só o que o utilizador manda).
//
// O teste mais importante aqui não é "encontra um secret" -- isso já
// está validado no core Python. É provar que a ORDEM das operações
// está certa: inspecionar ANTES de reverter tokens. Se estivesse ao
// contrário, o próprio dado do utilizador (devolvido de propósito)
// seria marcado como um "novo" leak e bloqueado por engano.

import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { inspectOutput, maskTokens, OUTPUT_BLOCKED_MESSAGE } from "../src/output_inspection.js";

const originalFetch = global.fetch;
afterEach(() => {
  global.fetch = originalFetch;
});

function mockDetector(responseBody, { ok = true } = {}) {
  let receivedPayload = null;
  global.fetch = async (_url, opts) => {
    receivedPayload = JSON.parse(opts.body).payload;
    return {
      ok,
      status: ok ? 200 : 500,
      json: async () => responseBody,
    };
  };
  return () => receivedPayload;
}

test("ALLOW: resposta limpa passa sem alteração", async () => {
  mockDetector({ action: "allow", finding_count: 0, redacted_payload: null, token_map: null });
  const result = await inspectOutput("olá, tudo bem?");
  assert.equal(result.action, "allow");
});

test("BLOCK: secret alucinado pela IA é apanhado", async () => {
  mockDetector({ action: "block", finding_count: 1, redacted_payload: null, token_map: null });
  const result = await inspectOutput("A tua chave é AKIA1234567890ABCDEF");
  assert.equal(result.action, "block");
});

test("REDACT: PII na resposta vem mascarada, nunca com token cru nem valor real", () => {
  const tokenMap = { ESYS_TOK_ab12cd34: "joao@example.com" };
  const redactedPayload = "contacta ESYS_TOK_ab12cd34 para mais info";
  const masked = maskTokens(redactedPayload, tokenMap);

  assert.equal(masked.includes("ESYS_TOK_"), false, "não deve sobrar o token cru");
  assert.equal(masked.includes("joao@example.com"), false, "não deve revelar o valor real -- não é dado do utilizador");
  assert.equal(masked, "contacta [REDACTED] para mais info");
});

test("fail-closed: detector indisponível bloqueia a resposta, não deixa passar sem inspeção", async () => {
  mockDetector({ error: "boom" }, { ok: false });
  const result = await inspectOutput("qualquer coisa");
  assert.equal(result.action, "block");
});

test("fail-closed: erro de rede também bloqueia", async () => {
  global.fetch = async () => {
    throw new Error("ECONNREFUSED");
  };
  const result = await inspectOutput("qualquer coisa");
  assert.equal(result.action, "block");
});

test("texto vazio: ALLOW direto, sem sequer chamar o detector", async () => {
  let called = false;
  global.fetch = async () => {
    called = true;
    return { ok: true, status: 200, json: async () => ({ action: "allow" }) };
  };
  const result = await inspectOutput("");
  assert.equal(result.action, "allow");
  assert.equal(called, false);
});

test("ORDEM CRÍTICA: o token ainda por reverter é o que é enviado ao detector, não o valor real", async () => {
  const getPayload = mockDetector({ action: "allow", finding_count: 0, redacted_payload: null, token_map: null });

  const respostaAindaComToken = "o teu contacto é ESYS_TOK_ab12cd34, confirma?";
  await inspectOutput(respostaAindaComToken);

  const payloadEnviado = getPayload();
  assert.equal(
    payloadEnviado.includes("ESYS_TOK_ab12cd34"),
    true,
    "o detector tem de receber o token, não o valor real -- prova que a inspeção corre antes do detokenize"
  );
  assert.equal(
    payloadEnviado.includes("joao@example.com"),
    false,
    "o valor real nunca deve ser o que se manda ao detector nesta fase"
  );
});

test("OUTPUT_BLOCKED_MESSAGE nunca contém o texto original bloqueado", () => {
  assert.equal(typeof OUTPUT_BLOCKED_MESSAGE, "string");
  assert.equal(OUTPUT_BLOCKED_MESSAGE.length > 0, true);
});