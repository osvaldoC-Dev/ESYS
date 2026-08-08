"""
Registo de auditoria para decisões BLOCK.

Sem isto, um bloqueio simplesmente desaparece — não há forma de saber
depois "o que foi bloqueado esta semana" nem de recuperar um falso
positivo que impediu um pedido legítimo de passar. Isto é o mínimo
necessário para resolver isso: persistência simples em ficheiro (JSONL),
sem precisar de base de dados nem servidor extra.

Ficheiro: eval/results/blocked_log.jsonl (uma linha JSON por bloqueio)

Adicionalmente, se SUPABASE_URL e SUPABASE_SERVICE_KEY estiverem
definidas, cada bloqueio (e cada aprovação) é TAMBÉM enviado/atualizado
numa tabela Supabase (esys_events) -- para o dashboard remoto conseguir
ler os eventos sem precisar de acesso a este disco local. Isto é sempre
um "extra": o ficheiro local continua a ser a fonte de verdade principal,
e uma falha a comunicar com o Supabase (rede em baixo, etc.) NUNCA impede
o bloqueio/aprovação local de funcionar -- só significa que essa cópia
remota fica desatualizada desta vez.

Nunca envia o payload nem o valor sensível para o Supabase -- só
metadados (timestamp, categoria, tipo, ação, contagem, status).
"""

import json
import os
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone

LOG_PATH = os.path.join(os.path.dirname(__file__), "..", "eval", "results", "blocked_log.jsonl")

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")


def _send_to_supabase(entry: dict) -> None:
    """Envia o evento para a tabela esys_events do Supabase. Silencioso
    em qualquer falha -- isto nunca deve impedir o bloqueio local de
    funcionar."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return

    findings = entry.get("findings") or []
    first = findings[0] if findings else {}

    body = {
        "audit_id": entry["id"],
        "timestamp": entry["timestamp"],
        "status": entry["status"],
        "category": first.get("category"),
        "subtype": first.get("subtype"),
        "action": "BLOCK",
        "finding_count": len(findings),
    }

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/esys_events",
        data=json.dumps(body).encode("utf-8"),
        method="POST",
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        urllib.request.urlopen(req, timeout=3)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"aviso: não foi possível enviar o evento para o Supabase ({e}); o registo local continua normal")


def _update_status_in_supabase(entry_id: str, status: str) -> None:
    """Atualiza o status do evento correspondente no Supabase. Silencioso
    em qualquer falha -- tal como no envio inicial, isto nunca deve
    impedir a aprovação local de funcionar."""
    if not SUPABASE_URL or not SUPABASE_SERVICE_KEY:
        return

    req = urllib.request.Request(
        f"{SUPABASE_URL}/rest/v1/esys_events?audit_id=eq.{entry_id}",
        data=json.dumps({"status": status}).encode("utf-8"),
        method="PATCH",
        headers={
            "apikey": SUPABASE_SERVICE_KEY,
            "Authorization": f"Bearer {SUPABASE_SERVICE_KEY}",
            "Content-Type": "application/json",
            "Prefer": "return=minimal",
        },
    )
    try:
        urllib.request.urlopen(req, timeout=3)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError) as e:
        print(f"aviso: não foi possível atualizar o status no Supabase ({e}); o registo local continua normal")


def log_block(payload: str, findings: list[dict]) -> str:
    """Regista um bloqueio (local, sempre) e devolve o ID único da
    entrada. Também tenta enviar uma cópia para o Supabase, sem deixar
    isso afetar o resultado desta função."""
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

    _send_to_supabase(entry)

    return entry_id


def load_all() -> list[dict]:
    """Lê todas as entradas do log. Uma linha corrompida (ex: escrita
    interrompida a meio, edição manual malfeita) é ignorada com um aviso,
    em vez de rebentar o comando inteiro — perder 1 entrada é muito menos
    grave do que tornar todo o resto do registo ilegível."""
    if not os.path.exists(LOG_PATH):
        return []
    entries = []
    with open(LOG_PATH, encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                print(f"aviso: linha {line_num} do log de auditoria está corrompida, a ignorar")
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
        _update_status_in_supabase(entry_id, status)
    return found