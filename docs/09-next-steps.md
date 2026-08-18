# Immediate Next Steps

*(Updated — the original 3 steps below are done. Sequence reflects where
the project actually is now, not where it started.)*

## Done
1. ~~Fix the 3 detector gaps -> rerun eval/score.py -> confirm accuracy~~
   — GO (100% recall, 0% FP).
2. ~~Build a minimal proxy wired to one provider~~ — done, tested,
   streaming-capable.
3. ~~Build the latency harness~~ — done, 3.72ms p95 (target <30ms).
4. ~~Detokenize streaming responses~~ — done. `StreamDetokenizer` buffers
   the last `TOKEN_LENGTH-1` chars before releasing output, so a token
   split across SSE chunks is never leaked. Verified with 441 adversarial
   chunk-split combinations plus a real end-to-end run on both the
   OpenAI and Anthropic streaming paths (see Current Status).

## Next, in order

1. **Test against real, non-synthetic traffic.** A first external tester
   is lined up (someone who already trusts the founder technically) — the
   goal is real prompts/files/logs that weren't designed with this
   detector in mind, to answer the still-open question: does this
   generalize, or did it just learn the exam?
2. **Package `esys-watch` for real distribution.** Today it's
   `git clone` + `pip install -e .` — fine for a technical tester, not
   for the PLG wedge described in Solution. No clipboard/editor
   integration (ruled out deliberately, see below) — the next honest step
   is a single well-chosen integration surface (e.g. one specific AI
   tool's official extension point), chosen once real usage data says
   where users actually spend their time — not guessed in advance.

## Explicitly not doing next (and why)

- **Clipboard-watching / "invisible" background monitoring** — removed
  from the roadmap after a design debate: it can't distinguish where
  copied content is headed (an AI tool vs. a code editor vs. Slack), so
  it either fires on everything (exactly the noisy-false-positive problem
  that gets a tool uninstalled) or needs the same targeted-integration
  work anyway. A background process reading the clipboard constantly also
  reads as spyware-adjacent to the security-conscious audience this
  product needs to earn trust with — the wrong tradeoff for this product,
  even though it works fine for something like Grammarly's UX.
- **Multiple simultaneous integrations** (ChatGPT + Cursor + VS Code +
  Copilot extensions) — each is its own maintenance surface (its own
  bugs, its own release cycle). For a one-person project, that's a
  roadmap for a 20-engineer team, not a next step. Rule adopted: *every
  new integration must justify itself with evidence from existing users;
  expand to a second surface only after the first shows clear adoption.*