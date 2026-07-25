# Immediate Next Steps

In order:

1. Fix the 3 detector gaps -> rerun `eval/score.py` -> confirm accuracy.
   Gate passes at recall >= 98%, FP rate <= 2%.
2. Build a minimal proxy (this Node scaffold) using the now-passing
   detector, wired to one provider (OpenAI first).
3. Build the latency harness and measure it against that minimal proxy
   (target: p95 < 30ms added latency).
