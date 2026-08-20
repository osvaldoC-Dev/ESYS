// Robustez do inspectMiddleware contra req.body malformado ou inesperado.
//
// Motivação: um pedido com messages em falta, null, não-array, ou itens
// sem content, é exatamente o tipo de coisa que alguém (ou um bug noutro
// sítio da cadeia) pode mandar por acidente. Nenhum destes casos deve
// deixar passar dados sem inspecionar por engano (bypass silencioso), nem
// deve fazer o processo cair -- deve inspecionar corretamente, ou falhar
// fechado (503), nunca falhar aberto.
//
// Testado manualmente primeiro contra o servidor real (proxy + mock
// detector) antes de escrever isto -- os 6 casos abaixo replicam
// exatamente o que foi confirmado a correr de verdade.

import { test, afterEach } from "node:test";
import assert from "node:assert/strict";
import { inspectMiddleware } from "../src/middleware/inspect.js";

const originalFetch = global.fetch;
afterEach(() => {
  global.fetch = originalFetch;
});

function mockAllowIfEmpty() {
  // Réplica do policy.py real: payload vazio -> ALLOW, sem findings.
  global.fetch = async (_url, opts) => {
    const { payload } = JSON.parse(opts.body);
    const action = payload.trim() === "" ? "allow" : "block"; // qualquer conteúdo não-vazio bloqueia, só para tornar o teste sensível a bypass
    return {
      ok: true,
      status: 200,
      json: async () => ({
        action,
        finding_count: action === "block" ? 1 : 0,
        redacted_payload: null,
        token_map: null,
        audit_id: null,
      }),
    };
  };
}

function makeRes() {
  const res = {
    statusCode: null,
    body: null,
    status(c) { this.statusCode = c; return this; },
    json(p) { this.body = p; return this; },
  };
  return res;
}

function makeNext() {
  let called = false;
  const next = () => { called = true; };
  next.wasCalled = () => called;
  return next;
}

test("messages em falta: payload vazio, ALLOW, sem crash", async () => {
  mockAllowIfEmpty();
  const req = { body: {} };
  const res = makeRes();
  const next = makeNext();
  await inspectMiddleware(req, res, next);
  assert.equal(next.wasCalled(), true);
  assert.equal(res.statusCode, null);
});

test("messages: null, payload vazio, ALLOW, sem crash", async () => {
  mockAllowIfEmpty();
  const req = { body: { messages: null } };
  const res = makeRes();
  const next = makeNext();
  await inspectMiddleware(req, res, next);
  assert.equal(next.wasCalled(), true);
});

test("mensagem sem campo content: tratado como vazio, ALLOW, sem crash", async () => {
  mockAllowIfEmpty();
  const req = { body: { messages: [{ role: "user" }] } };
  const res = makeRes();
  const next = makeNext();
  await inspectMiddleware(req, res, next);
  assert.equal(next.wasCalled(), true);
});

test("messages não é array (ex: string): falha FECHADO, não crasha o processo", async () => {
  // Não precisa de mock de fetch -- nunca chega a chamar o detector,
  // rebenta antes, no .map(). O que importa é que o catch apanha isto.
  const req = { body: { messages: "não sou um array" } };
  const res = makeRes();
  const next = makeNext();
  await inspectMiddleware(req, res, next);
  assert.equal(next.wasCalled(), false, "nunca deve deixar passar quando a estrutura é inesperada");
  assert.equal(res.statusCode, 503);
  assert.equal(res.body.error, "detector_error");
});

test("content é um número em vez de string: não bypassa a inspeção", async () => {
  // JS coage number->string no .join(), então isto deve continuar a ser
  // enviado ao detector como texto normal -- confirma que não maquina um
  // bypass silencioso (ex: alguém a tentar contornar o detector mandando
  // tipos inesperados no content).
  global.fetch = async (_url, opts) => {
    const { payload } = JSON.parse(opts.body);
    assert.equal(payload.includes("12345"), true, "o número devia ter chegado ao detector como texto");
    return {
      ok: true,
      status: 200,
      json: async () => ({ action: "allow", finding_count: 0, redacted_payload: null, token_map: null, audit_id: null }),
    };
  };
  const req = { body: { messages: [{ role: "user", content: 12345 }] } };
  const res = makeRes();
  const next = makeNext();
  await inspectMiddleware(req, res, next);
  assert.equal(next.wasCalled(), true);
});