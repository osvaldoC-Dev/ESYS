import "dotenv/config";
import express from "express";
import { inspectMiddleware } from "./middleware/inspect.js";
import { forwardToOpenAI } from "./providers/openai.js";
import { forwardToMockProvider } from "./providers/mock.js";
import { forwardToMockStreamProvider } from "./providers/mock_stream.js";
import { forwardToMockEchoProvider } from "./providers/mock_echo.js";

const app = express();
app.use(express.json({ limit: "5mb" }));

const PORT = process.env.PORT || 8080;

app.post("/v1/chat/completions", inspectMiddleware, forwardToOpenAI);

app.post("/bench/with-inspection", inspectMiddleware, forwardToMockProvider);
app.post("/bench/baseline", forwardToMockProvider);
app.post("/bench/stream", inspectMiddleware, forwardToMockStreamProvider);
app.post("/bench/echo", inspectMiddleware, forwardToMockEchoProvider);

app.get("/health", (_req, res) => res.json({ status: "ok" }));

app.listen(PORT, () => {
  console.log(`esys-proxy listening on :${PORT}`);
});
