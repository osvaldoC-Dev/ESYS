# Metrics

| Metric               | Target  |
|-----------------------|---------|
| Recall                | >= 98%  |
| False Positive Rate   | <= 2%   |
| Added Latency (p95)   | < 30ms  |

The whole product bet rests on hitting these three numbers together
against the 320-case labeled eval dataset. If they can't be hit, the
architecture needs to change before anything else gets built.
