// Inspeção de OUTPUT — a resposta da IA, antes de chegar ao utilizador.
//
// Até agora a ESYS só protegia o que sai do utilizador PARA a IA. Isto
// cobre a direção oposta: e se o próprio modelo devolver algo sensível
// que não devia (uma chave alucinada, dados vazados de outro contexto)?
//
// Reusa o mesmo endpoint /inspect e o mesmo core validado (secrets +
// PII + prompt_injection) já usado no lado do pedido — sem duplicar
// lógica de deteção.
//
// ORDEM IMPORTANTE: isto tem de correr ANTES de reverter os tokens
// (detokenize) da resposta. Se corresse depois, voltaria a marcar como
// "PII encontrada" o próprio dado do utilizador que foi devolvido de
// propósito -- nesse ponto ainda está disfarçado como ESYS_TOK_xxxx,
// que não bate com nenhum regex de secret/PII, então só dispara em
// conteúdo genuinamente novo que o modelo produziu por conta própria.

const DETECTOR_URL = process.env.DETECTOR_URL || "http://localhost:8787/inspect";
const DETECTOR_TIMEOUT_MS = Number(process.env.DETECTOR_TIMEOUT_MS) || 5000;

/**
 * @param {string} text - o conteúdo da resposta da IA, ANTES de
 *   qualquer detokenize.
 * @returns {Promise<{action: "allow"|"redact"|"block", redacted_payload?: string, token_map?: object}>}
 */
export async function inspectOutput(text) {
  if (!text) return { action: "allow" };

  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), DETECTOR_TIMEOUT_MS);

  try {
    const response = await fetch(DETECTOR_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ payload: text }),
      signal: controller.signal,
    });

    if (!response.ok) {
      // Fail closed: mesma filosofia usada no lado do pedido -- se o
      // detector está em baixo, não deixamos passar uma resposta não
      // inspecionada.
      return { action: "block", reason: "detector_unavailable" };
    }

    const result = await response.json();
    return {
      action: (result.action ?? "block").toLowerCase(),
      redacted_payload: result.redacted_payload,
      token_map: result.token_map,
    };
  } catch (err) {
    const reason = err.name === "AbortError" ? "detector_timeout" : "detector_error";
    console.error("inspectOutput error:", reason, err.message);
    return { action: "block", reason };
  } finally {
    clearTimeout(timeout);
  }
}

/**
 * Substitui cada token pelo texto "[REDACTED]", nunca pelo valor real.
 * Usado só para findings encontrados na SAÍDA -- ao contrário do
 * detokenize() (que reverte tokens do próprio utilizador), aqui não há
 * razão para reversibilidade: se o modelo produziu isto por conta
 * própria, não é o dado do utilizador, e não faz sentido devolvê-lo.
 */
export function maskTokens(text, tokenMap) {
  if (!tokenMap || typeof text !== "string") return text;
  let result = text;
  for (const token of Object.keys(tokenMap)) {
    result = result.split(token).join("[REDACTED]");
  }
  return result;
}

export const OUTPUT_BLOCKED_MESSAGE =
  "[response blocked by ESYS: the AI's reply appeared to contain sensitive data that shouldn't leave this system]";