// Reverte os tokens ESYS_TOK_xxxxxxxx numa string de resposta, substituindo
// cada um pelo valor sensível original -- usado depois de o provider
// responder, para o modelo poder ter "visto" um valor coerente durante o
// processamento, sem que o valor real alguma vez saísse desta máquina.

export function detokenize(text, tokenMap) {
  if (!tokenMap || typeof text !== "string") return text;
  let result = text;
  for (const [token, original] of Object.entries(tokenMap)) {
    result = result.split(token).join(original);
  }
  return result;
}

// Comprimento fixo de um token ESYS_TOK_xxxxxxxx: "ESYS_TOK_" (9) + 8
// caracteres hex = 17. Usado para saber quantos caracteres reter em
// reserva, para nunca libertar um token cortado a meio.
const TOKEN_LENGTH = "ESYS_TOK_".length + 8;
const RESERVE = TOKEN_LENGTH - 1;

/**
 * Reverte tokens num stream SSE (Server-Sent Events) chunk a chunk, sem
 * nunca deixar passar um token cortado a meio entre dois chunks.
 *
 * Problema que isto resolve: um chunk de rede não respeita as fronteiras
 * do token — "ESYS_TOK_abc123" pode chegar dividido em "ESYS_T" num
 * chunk e "OK_abc123" no seguinte. Se substituíssemos token a token
 * chunk a chunk, nunca encontraríamos o token completo, e o valor
 * sensível nunca seria revertido — o cliente veria o token literal.
 *
 * Estratégia: mantém um buffer do texto acumulado (`pendingContent`) e só
 * liberta a parte "seguramente completa" — tudo menos os últimos
 * RESERVE caracteres, que podem ainda ser o início de um token que
 * continua no próximo chunk. Ao chegar mais texto, tenta detokenizar de
 * novo sobre o buffer acumulado (agora talvez completo) antes de decidir
 * o que libertar.
 */
export class StreamDetokenizer {
  constructor(tokenMap) {
    this.tokenMap = tokenMap;
    this.rawBuffer = ""; // texto SSE bruto ainda sem um evento completo (\n\n)
    this.pendingContent = ""; // conteúdo de texto acumulado, ainda não libertado
  }

  /** Alimenta um pedaço de texto bruto recebido do provider. Devolve o
   * texto (já em formato SSE) pronto a escrever no cliente agora, ou ""
   * se nada estiver pronto ainda. */
  push(rawChunk) {
    if (!this.tokenMap) return rawChunk; // nada a fazer, passa tudo direto
    this.rawBuffer += rawChunk;
    let output = "";
    let idx;
    while ((idx = this.rawBuffer.indexOf("\n\n")) !== -1) {
      const rawEvent = this.rawBuffer.slice(0, idx);
      this.rawBuffer = this.rawBuffer.slice(idx + 2);
      output += this._handleEvent(rawEvent);
    }
    return output;
  }

  _handleEvent(rawEvent) {
    const dataLine = rawEvent.startsWith("data: ") ? rawEvent.slice(6) : rawEvent;

    if (dataLine.trim() === "[DONE]") {
      return this._flushPending() + rawEvent + "\n\n";
    }

    let parsed;
    try {
      parsed = JSON.parse(dataLine);
    } catch {
      return this._flushPending() + rawEvent + "\n\n";
    }

    const content = parsed?.choices?.[0]?.delta?.content;
    if (typeof content !== "string") {
      return this._flushPending() + rawEvent + "\n\n";
    }

    this.pendingContent += content;
    const detokenized = detokenize(this.pendingContent, this.tokenMap);
    const safeLen = Math.max(0, detokenized.length - RESERVE);
    const safePart = detokenized.slice(0, safeLen);
    this.pendingContent = detokenized.slice(safeLen);

    if (!safePart) return "";
    return this._wrapEvent(safePart);
  }

  _wrapEvent(contentPiece) {
    return `data: ${JSON.stringify({ choices: [{ delta: { content: contentPiece } }] })}\n\n`;
  }

  _flushPending() {
    if (!this.pendingContent) return "";
    const out = this._wrapEvent(this.pendingContent);
    this.pendingContent = "";
    return out;
  }

  /** Chamar quando o stream terminar, para libertar tudo o que ainda
   * estava em reserva (já não há risco de um token continuar depois). */
  end() {
    let output = this._flushPending();
    if (this.rawBuffer.trim()) {
      output += this.rawBuffer;
      this.rawBuffer = "";
    }
    return output;
  }
}
