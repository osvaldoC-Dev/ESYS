export function forwardToMockProvider(_req, res) {
  res.json({
    id: "mock-completion",
    choices: [{ message: { role: "assistant", content: "ok" } }],
  });
}
