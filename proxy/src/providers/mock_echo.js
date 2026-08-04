import { detokenize } from "../tokenize.js";

// Provider mock que ecoa de volta o conteúdo que recebeu, no mesmo formato
// de resposta da OpenAI -- usado só para testar a reversão de tokens
// ponta a ponta, sem precisar de uma chave real da OpenAI. Se o pedido
// foi tokenizado (redact), o eco vai conter o token, tal como aconteceria
// se um modelo real repetisse de volta parte do prompt -- e este mock
// aplica a mesma reversão que o forwardToOpenAI real aplicaria.

export function forwardToMockEchoProvider(req, res) {
  const lastMessage = req.body?.messages?.[req.body.messages.length - 1];
  let echoedContent = `You said: ${lastMessage?.content ?? ""}`;

  if (req.esysTokenMap) {
    echoedContent = detokenize(echoedContent, req.esysTokenMap);
  }

  res.json({
    id: "mock-echo-completion",
    choices: [{ message: { role: "assistant", content: echoedContent } }],
  });
}
