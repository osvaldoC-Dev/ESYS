const CHUNKS = ["Hello", ", ", "this ", "is ", "a ", "streamed ", "response", "."];

function sleep(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

export async function forwardToMockStreamProvider(_req, res) {
  res.status(200);
  res.setHeader("Content-Type", "text/event-stream");
  res.setHeader("Cache-Control", "no-cache");
  res.setHeader("Connection", "keep-alive");
  res.flushHeaders?.();

  for (const piece of CHUNKS) {
    const event = { choices: [{ delta: { content: piece } }] };
    res.write(`data: ${JSON.stringify(event)}\n\n`);
    await sleep(50);
  }
  res.write("data: [DONE]\n\n");
  res.end();
}
