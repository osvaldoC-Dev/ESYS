const DETECTOR_URL = process.env.DETECTOR_URL || "http://localhost:8787/inspect";

/**
 * Calls the Python detector service with the outbound payload and enforces
 * the policy decision (allow / redact / block) before the request reaches
 * the provider.
 */
export async function inspectMiddleware(req, res, next) {
  try {
    const payload = JSON.stringify(req.body);

    const response = await fetch(DETECTOR_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload }),
    });

    if (!response.ok) {
      // Fail closed: if the detector is unreachable, block by default.
      return res.status(503).json({ error: "detector_unavailable" });
    }

    const result = await response.json();

    switch (result.decision) {
      case "block":
        return res.status(403).json({ error: "blocked_by_policy", finding_count: result.finding_count });
      case "redact":
        // TODO: replace req.body with the redacted payload once
        // service.py returns redacted_payload for structured JSON bodies.
        req.body = JSON.parse(result.redacted_payload ?? payload);
        return next();
      case "allow":
      default:
        return next();
    }
  } catch (err) {
    console.error("inspectMiddleware error:", err);
    // Fail closed on unexpected errors too.
    return res.status(503).json({ error: "detector_error" });
  }
}
