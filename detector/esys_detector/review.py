"""
esys review — CLI para consultar e aprovar bloqueios passados.

Sem isto, um falso positivo bloqueado desaparece para sempre. Isto dá
visibilidade (o que foi bloqueado, quando, porquê) e um mecanismo simples
de aprovação manual — não reenvia nada automaticamente, mas deixa um
registo auditável de que um humano reviu e decidiu que aquele bloqueio
era um falso positivo.

Uso:
    python -m esys_detector.review                 # lista bloqueios pendentes
    python -m esys_detector.review --all            # lista todos (incluindo já revistos)
    python -m esys_detector.review approve <id>     # aprova um bloqueio específico
    python -m esys_detector.review show <id>        # mostra o payload original completo desse bloqueio
"""

import sys

from esys_detector.audit_log import load_all, set_status


def _summary_line(entry: dict) -> str:
    subtypes = ", ".join(f["subtype"] for f in entry["findings"])
    return f"  [{entry['status']:<9}] {entry['id']}  {entry['timestamp']}  findings: {subtypes}"


def cmd_list(show_all: bool) -> None:
    entries = load_all()
    if not show_all:
        entries = [e for e in entries if e["status"] == "pending"]

    if not entries:
        print("Nenhum bloqueio pendente." if not show_all else "Nenhum bloqueio registado ainda.")
        return

    print(f"{len(entries)} bloqueio(s):\n")
    for e in entries:
        print(_summary_line(e))
    print("\nUsa: python -m esys_detector.review show <id>     para ver o detalhe")
    print("     python -m esys_detector.review approve <id>  para aprovar")


def cmd_show(entry_id: str) -> None:
    entries = load_all()
    match = next((e for e in entries if e["id"] == entry_id), None)
    if not match:
        print(f"Nenhum bloqueio encontrado com id {entry_id}")
        sys.exit(1)

    print("=" * 60)
    print(f"ID: {match['id']}   Status: {match['status']}   {match['timestamp']}")
    print("=" * 60)
    print("Findings:")
    for f in match["findings"]:
        print(f"  [{f['category']}] {f['subtype']}  (pos {f['offset_start']}-{f['offset_end']})")
    print()
    print("Payload original completo:")
    print("-" * 60)
    print(match["payload"])
    print("-" * 60)


def cmd_approve(entry_id: str) -> None:
    if set_status(entry_id, "approved"):
        print(f"Bloqueio {entry_id} marcado como aprovado (falso positivo revisto por humano).")
    else:
        print(f"Nenhum bloqueio encontrado com id {entry_id}")
        sys.exit(1)


def main() -> None:
    args = sys.argv[1:]

    if not args:
        cmd_list(show_all=False)
    elif args[0] == "--all":
        cmd_list(show_all=True)
    elif args[0] == "show" and len(args) > 1:
        cmd_show(args[1])
    elif args[0] == "approve" and len(args) > 1:
        cmd_approve(args[1])
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()
