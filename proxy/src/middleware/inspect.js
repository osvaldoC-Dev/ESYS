const DETECTOR_URL = process.env.DETECTOR_URL || "http://localhost:8787/inspect";
const DETECTOR_TIMEOUT_MS = Number(process.env.DETECTOR_TIMEOUT_MS) || 5000;

// Separador usado para juntar o conteúdo de várias mensagens num único
// texto a inspecionar, preservando onde cada mensagem começa/acaba para
// conseguirmos reconstruir req.body depois de uma redação.
const BOUNDARY = "\n\n---ESYS_MSG_BOUNDARY---\n\n";

/**
 * Calls the Python detector service with the outbound payload and enforces
 * the policy decision (allow / redact / block) before the request reaches
 * the provider.
 *
 * Only the actual message *content* is sent to the detector — not the full
 * JSON request body (model name, role fields, etc). Sending the raw JSON
 * would make every request "look structured" to the policy engine (because
 * it's always wrapped in `{...}`), which would make it BLOCK instead of
 * REDACT even for plain-text PII inside a normal chat message.
 */
export async function inspectMiddleware(req, res, next) {
  try {
    const messages = req.body?.messages ?? [];
    const payload = messages.map((m) => m.content ?? "").join(BOUNDARY);

    // Timeout de segurança: sem isto, um detector lento/pendurado deixa
    // o proxy à espera indefinidamente, e o pedido do cliente nunca
    // recebe resposta nenhuma. Falha fechado (bloqueia) se expirar.
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), DETECTOR_TIMEOUT_MS);

    let response;
    try {
      response = await fetch(DETECTOR_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ payload }),
        signal: controller.signal,
      });
    } finally {
      clearTimeout(timeout);
    }

    if (!response.ok) {
      // Fail closed: if the detector is unreachable, block by default.
      return res.status(503).json({ error: "detector_unavailable" });
    }

    const result = await response.json();
    const action = (result.action ?? "").toLowerCase();

    switch (action) {
      case "block":
        return res.status(403).json({ error: "blocked_by_policy", finding_count: result.finding_count });
      case "redact": {
        const redactedParts = (result.redacted_payload ?? payload).split(BOUNDARY);
        req.body.messages = messages.map((m, i) => ({ ...m, content: redactedParts[i] ?? m.content }));
        return next();
      }
      case "allow":
      default:
        return next();
    }
  } catch (err) {
    if (err.name === "AbortError") {
      console.error("inspectMiddleware timeout: detector did not respond within", DETECTOR_TIMEOUT_MS, "ms");
      return res.status(503).json({ error: "detector_timeout" });
    }
    console.error("inspectMiddleware error:", err);
    // Fail closed on unexpected errors too.
    return res.status(503).json({ error: "detector_error" });
  }
}