"""
esys watch — CLI local que corre os mesmos detectores do ESYS sobre um
ficheiro ou stdin, e mostra o que encontrou antes de tu colares isso num
prompt de IA.

Uso:
    python -m esys_detector.watch caminho/para/ficheiro.txt
    cat ficheiro.txt | python -m esys_detector.watch
    echo "my key is AKIA..." | python -m esys_detector.watch

Exit code:
    0 -> ALLOW (nada encontrado, ou encontrado mas decisão ALLOW)
    1 -> BLOCK (encontrou algo suficientemente sensível para bloquear)
    2 -> REDACT (encontrou PII redigível)

Isto não reinventa deteção nenhuma — usa exatamente os mesmos
detectors/policy que já correm no service.py e passaram no gate (recall
1.00, FP 0.00). O CLI é só uma interface diferente por cima do mesmo core.
"""

import sys

from esys_detector.detectors.secrets import detect_secrets
from esys_detector.detectors.pii import detect_pii
from esys_detector.policy import decide


def _read_input(argv: list[str]) -> str:
    if len(argv) > 1:
        path = argv[1]
        with open(path, encoding="utf-8") as f:
            return f.read()
    if sys.stdin.isatty():
        print("Uso: python -m esys_detector.watch <ficheiro>  (ou faz pipe: cat ficheiro | ...)")
        sys.exit(2)
    return sys.stdin.read()


def _print_report(payload: str, findings: list[dict], decision: dict) -> None:
    print("=" * 60)
    print("ESYS WATCH")
    print("=" * 60)

    if not findings:
        print("Nada encontrado. Nenhum secret ou PII detectado.")
    else:
        print(f"{len(findings)} finding(s):\n")
        for f in findings:
            snippet = payload[f["offset_start"]:f["offset_end"]]
            masked = snippet[:2] + "*" * max(len(snippet) - 4, 0) + snippet[-2:] if len(snippet) > 4 else "*" * len(snippet)
            print(f"  [{f['category']}] {f['subtype']:<22} -> {masked}  (pos {f['offset_start']}-{f['offset_end']})")

    print()
    print(f"Decisão: {decision['action']}")

    if decision["action"] == "REDACT":
        print()
        print("Versão limpa (segura para colar):")
        print("-" * 60)
        print(decision["redacted_payload"])
        print("-" * 60)
    elif decision["action"] == "BLOCK":
        print()
        print("NÃO cola isto num prompt de IA — contém dados sensíveis que não")
        print("deviam sair da tua máquina.")

    print("=" * 60)


def main() -> None:
    payload = _read_input(sys.argv)
    findings = detect_secrets(payload) + detect_pii(payload)
    decision = decide(payload, findings)

    _print_report(payload, findings, decision)

    exit_codes = {"ALLOW": 0, "REDACT": 2, "BLOCK": 1}
    sys.exit(exit_codes.get(decision["action"], 0))


if __name__ == "__main__":
    main()
