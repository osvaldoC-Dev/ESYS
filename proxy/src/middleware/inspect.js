const DETECTOR_URL = process.env.DETECTOR_URL || "http://localhost:8787/inspect";

// Separador usado para juntar o conteúdo de várias mensagens num único
// texto a inspecionar, preservando onde cada mensagem começa/acaba para
// conseguirmos reconstruir req.body depois de uma redação.
const BOUNDARY = "\n\n---ESYS_MSG_BOUNDARY---\n\n";

/**
 * Calls the Python detector service with the outbound payload and enforces
 * the policy decision (allow / redact / block) before the request reaches
 * the provider.
 *
 * Only the actual message content is sent to the detector — not the full
 * JSON request body — so plain-text PII inside a normal chat message
 * doesn't get misread as "structured data" just because the outer request
 * happens to be JSON.
 */
export async function inspectMiddleware(req, res, next) {
  try {
    const messages = req.body?.messages ?? [];
    const payload = messages.map((m) => m.content ?? "").join(BOUNDARY);

    const response = await fetch(DETECTOR_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload }),
    });

    if (!response.ok) {
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
    console.error("inspectMiddleware error:", err);
    return res.status(503).json({ error: "detector_error" });
  }
}
