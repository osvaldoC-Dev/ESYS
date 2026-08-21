"""
Guarda-costas contra ReDoS voltar a aparecer.

O projeto já corrigiu 3 bugs de ReDoS no passado (ver docs: Metrics /
Robustness section) -- regex com .* sem bounds que rebentava com input
adversarial construído para maximizar backtracking. A correção foi trocar
por .{0,N} com limites explícitos.

Este teste não prova ausência de ReDoS em geral (isso precisaria de fuzzing
mais sério), mas apanha o caso mais comum de regressão: alguém adiciona um
padrão novo com quantificador não limitado, e ele passa despercebido até
alguém mandar o payload adversarial certo em produção. Os limiares abaixo
são generosos de propósito (uma mensagem de chat real nunca chega perto
destes tamanhos) -- o objetivo é apanhar explosão exponencial/quadrática
óbvia, não otimizar performance normal.
"""

import time

from esys_detector.detectors.secrets import detect_secrets
from esys_detector.detectors.pii import detect_pii
from esys_detector.detectors.prompt_injection import detect_prompt_injection

# 3000ms para um payload de ~350KB feito inteiramente de quase-matches
# adversariais é generoso -- uma mensagem de chat real (poucos KB) fica
# ordens de magnitude abaixo disto num regex são. Se isto disparar, o
# candidato número 1 é sempre um quantificador não limitado novo.
TIMEOUT_MS = 3000

ADVERSARIAL_PAYLOADS = {
    "muitos quase-matches de goal_hijack": "ignore " * 5000 + "x" * 1000,
    "muitos quase-matches de system_prompt_extraction": "reveal the " * 5000,
    "muitas aspas quase-concat (secrets)": '"AAAAAA" + ' * 3000,
    "muitos candidatos base64": "QUFBQUFBQUFBQUFBQUFBQUFBQUFB " * 5000,
    "part-of-a-key repetido sem fechar (multi-turn gap)": "part of a key: XXXXXX " * 2000,
    "muitos 'BI' sem número válido perto (national_id context-gate)": "BI " * 3000 + "texto normal",
    "payload grande genérico (1MB+)": "lorem ipsum dolor sit amet " * 40000,
}


def _assert_fast(fn, payload: str, label: str) -> None:
    start = time.perf_counter()
    fn(payload)
    elapsed_ms = (time.perf_counter() - start) * 1000
    assert elapsed_ms < TIMEOUT_MS, (
        f"{label} demorou {elapsed_ms:.0f}ms (limite {TIMEOUT_MS}ms) -- "
        f"suspeita de regex com quantificador não limitado (ReDoS)"
    )


def test_detect_secrets_sem_redos():
    for label, payload in ADVERSARIAL_PAYLOADS.items():
        _assert_fast(detect_secrets, payload, f"detect_secrets / {label}")


def test_detect_pii_sem_redos():
    for label, payload in ADVERSARIAL_PAYLOADS.items():
        _assert_fast(detect_pii, payload, f"detect_pii / {label}")


def test_detect_prompt_injection_sem_redos():
    for label, payload in ADVERSARIAL_PAYLOADS.items():
        _assert_fast(detect_prompt_injection, payload, f"detect_prompt_injection / {label}")