// Provider "mock" usado só para o harness de latência. Responde
// instantaneamente, sem sair para a rede, para isolar exatamente o que o
// ESYS acrescenta ao pedido — sem misturar isso com a latência (variável,
// fora do nosso controlo) da OpenAI real.

export function forwardToMockProvider(_req, res) {
  res.json({
    id: "mock-completion",
    choices: [{ message: { role: "assistant", content: "ok" } }],
  });
}
