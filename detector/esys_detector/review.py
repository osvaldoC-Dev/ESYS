"""
esys review — CLI para consultar e aprovar bloqueios passados.

Uso:
    python -m esys_detector.review                 # lista bloqueios pendentes
    python -m esys_detector.review --all            # lista todos
    python -m esys_detector.review approve <id>     # aprova um bloqueio
    python -m esys_detector.review show <id>        # revela o payload original completo
    python -m esys_detector.review purge <dias>     # remove entradas mais antigas que N dias
"""

import sys

from esys_detector.audit_log import load_all, set_status, purge_older_than, LOG_PATH


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


def cmd_purge(days_str: str) -> None:
    try:
        days = int(days_str)
    except ValueError:
        print(f"'{days_str}' não é um número válido de dias.")
        sys.exit(2)
    removed = purge_older_than(days)
    print(f"{removed} entrada(s) com mais de {days} dia(s) removida(s) de {LOG_PATH}.")


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
    elif args[0] == "purge" and len(args) > 1:
        cmd_purge(args[1])
    else:
        print(__doc__)
        sys.exit(2)


if __name__ == "__main__":
    main()