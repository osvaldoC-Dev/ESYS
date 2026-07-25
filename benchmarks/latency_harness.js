const BASE_URL = process.env.ESYS_PROXY_URL || "http://localhost:8080";

const PAYLOADS = {
  clean: { model: "gpt-4", messages: [{ role: "user", content: "hello there, how are you" }] },
  secret: { model: "gpt-4", messages: [{ role: "user", content: "my key is AKIAIQK2919AHEJ8CX9J" }] },
};

function percentile(sorted, p) {
  const idx = Math.ceil((p / 100) * sorted.length) - 1;
  return sorted[Math.max(0, Math.min(idx, sorted.length - 1))];
}

async function runBatch(path, n, body) {
  const timings = [];
  for (let i = 0; i < n; i++) {
    const start = performance.now();
    await fetch(`${BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    timings.push(performance.now() - start);
  }
  timings.sort((a, b) => a - b);
  return {
    p50: percentile(timings, 50),
    p95: percentile(timings, 95),
    p99: percentile(timings, 99),
    min: timings[0],
    max: timings[timings.length - 1],
  };
}

function parseArgs() {
  const args = process.argv.slice(2);
  const opts = { n: 200, payload: "clean" };
  for (let i = 0; i < args.length; i += 2) {
    if (args[i] === "--n") opts.n = parseInt(args[i + 1], 10);
    if (args[i] === "--payload") opts.payload = args[i + 1];
  }
  return opts;
}

async function main() {
  const { n, payload } = parseArgs();
  const body = PAYLOADS[payload];
  if (!body) throw new Error(`payload desconhecido: ${payload} (usa "clean" ou "secret")`);

  console.log(`ESYS Latency Harness — ${n} pedidos por rota, payload="${payload}"\n`);

  await runBatch("/bench/baseline", 10, body);
  await runBatch("/bench/with-inspection", 10, body);

  const baseline = await runBatch("/bench/baseline", n, body);
  const withInspection = await runBatch("/bench/with-inspection", n, body);

  const addedP95 = withInspection.p95 - baseline.p95;

  console.log("baseline (sem ESYS):        ", fmt(baseline));
  console.log("with-inspection (com ESYS): ", fmt(withInspection));
  console.log();
  console.log(`Added Latency (p95): ${addedP95.toFixed(2)}ms  (target: < 30ms)`);
  console.log(addedP95 < 30 ? "PASS" : "FAIL");
}

function fmt(r) {
  return `p50=${r.p50.toFixed(2)}ms  p95=${r.p95.toFixed(2)}ms  p99=${r.p99.toFixed(2)}ms  min=${r.min.toFixed(2)}ms  max=${r.max.toFixed(2)}ms`;
}

main();
