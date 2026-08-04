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
