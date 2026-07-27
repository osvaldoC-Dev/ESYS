"""
Registo de auditoria para decisões BLOCK.

Sem isto, um bloqueio simplesmente desaparece — não há forma de saber
depois "o que foi bloqueado esta semana" nem de recuperar um falso
positivo que impediu um pedido legítimo de passar. Isto é o mínimo
necessário para resolver isso: persistência simples em ficheiro (JSONL),
sem precisar de base de dados nem servidor extra.

Ficheiro: eval/results/blocked_log.jsonl (uma linha JSON por bloqueio)
"""

import json
import os
import uuid
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "results", "blocked_log.jsonl")


def log_block(payload: str, findings: list[dict]) -> str:
    """Regista um bloqueio e devolve o ID único da entrada."""
    entry_id = str(uuid.uuid4())[:8]
    entry = {
        "id": entry_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "status": "pending",
        "findings": findings,
        "payload": payload,
    }
    os.makedirs(os.path.dirname(LOG_PATH), exist_ok=True)
    with open(LOG_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")
    return entry_id


def load_all() -> list[dict]:
    if not os.path.exists(LOG_PATH):
        return []
    entries = []
    with open(LOG_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                entries.append(json.loads(line))
    return entries


def set_status(entry_id: str, status: str) -> bool:
    """Atualiza o status de uma entrada (ex: 'pending' -> 'approved').
    Devolve True se encontrou e atualizou, False se o ID não existe."""
    entries = load_all()
    found = False
    for e in entries:
        if e["id"] == entry_id:
            e["status"] = status
            found = True
    if found:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            for e in entries:
                f.write(json.dumps(e) + "\n")
    return found
