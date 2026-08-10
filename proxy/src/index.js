import "dotenv/config";
import express from "express";
import { inspectMiddleware } from "./middleware/inspect.js";
import { forwardToOpenAI } from "./providers/openai.js";
import { forwardToAnthropic } from "./providers/anthropic.js";
import { forwardToMockAnthropicEcho, forwardToMockAnthropicStreamEcho } from "./providers/mock_anthropic_echo.js";
import { forwardToMockProvider } from "./providers/mock.js";
import { forwardToMockStreamProvider } from "./providers/mock_stream.js";
import { forwardToMockEchoProvider } from "./providers/mock_echo.js";
import { forwardToMockStreamEchoProvider } from "./providers/mock_stream_echo.js";

const app = express();
app.use(express.json({ limit: "5mb" }));

const PORT = process.env.PORT || 8080;

app.post("/v1/chat/completions", inspectMiddleware, forwardToOpenAI);

app.post("/bench/with-inspection", inspectMiddleware, forwardToMockProvider);
app.post("/bench/baseline", forwardToMockProvider);
app.post("/bench/stream", inspectMiddleware, forwardToMockStreamProvider);
app.post("/bench/echo", inspectMiddleware, forwardToMockEchoProvider);
app.post("/bench/stream-echo", inspectMiddleware, forwardToMockStreamEchoProvider);
app.post("/v1/anthropic/messages", inspectMiddleware, forwardToAnthropic);
app.post("/bench/anthropic-echo", inspectMiddleware, forwardToMockAnthropicEcho);
app.post("/bench/anthropic-stream-echo", inspectMiddleware, forwardToMockAnthropicStreamEcho);
app.get("/health", (_req, res) => res.json({ status: "ok" }));

// Error handler central: sem isto, um erro não tratado (ex: JSON
// malformado no pedido) faz o Express devolver uma página HTML com o
// stack trace completo, incluindo caminhos internos do servidor — uma
// fuga de informação para qualquer chamador externo. Isto garante que a
// resposta é sempre JSON, sem detalhes internos.
app.use((err, _req, res, _next) => {
  console.error("unhandled error:", err.message);
  if (res.headersSent) return;
  res.status(400).json({ error: "invalid_request" });
});

app.listen(PORT, () => {
  console.log(`esys-proxy listening on :${PORT}`);
});