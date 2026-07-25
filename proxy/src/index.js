import "dotenv/config";
import express from "express";
import { inspectMiddleware } from "./middleware/inspect.js";
import { forwardToOpenAI } from "./providers/openai.js";

const app = express();
app.use(express.json({ limit: "5mb" }));

const PORT = process.env.PORT || 8080;

// V1: single provider (OpenAI), single endpoint.
// Request flow: client -> inspectMiddleware (allow/redact/block) -> provider
app.post("/v1/chat/completions", inspectMiddleware, forwardToOpenAI);

app.get("/health", (_req, res) => res.json({ status: "ok" }));

app.listen(PORT, () => {
  console.log(`esys-proxy listening on :${PORT}`);
});
