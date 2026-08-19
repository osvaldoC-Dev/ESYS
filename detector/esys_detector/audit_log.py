"""
Registo de auditoria para decisões BLOCK.

Sem isto, um bloqueio simplesmente desaparece — não há forma de saber
depois "o que foi bloqueado esta semana" nem de recuperar um falso
positivo que impediu um pedido legítimo de passar. Isto é o mínimo
necessário para resolver isso: persistência simples em ficheiro (JSONL),
sem precisar de base de dados nem servidor extra.

DESIGN DE PRIVACIDADE (decisão consciente, não acidente):
  - O payload completo (sem máscara) fica guardado localmente. Isto é
    necessário: sem o conteúdo original, nunca consegues confirmar se um
    bloqueio foi mesmo um falso positivo. Mascarar ao escrever destruiria
    a informação que o registo existe para preservar.
  - "Local" só é uma promessa de privacidade real se for mesmo local —
    por isso o caminho por omissão fica em ~/.esys/, FORA de qualquer
    pasta normalmente ligada a um repositório de código (e portanto fora
    do que costuma ser sincronizado por engano por ferramentas tipo
    OneDrive quando alguém sincroniza o ambiente de trabalho inteiro).
  - Mesmo assim, detectamos e avisamos se o caminho final calhar dentro
    de uma pasta sincronizada conhecida (OneDrive, iCloud Drive,
    Dropbox) — para o caso de alguém ter o próprio $HOME dentro de uma
    dessas pastas, o que também acontece na prática.
  - `esys-review` (listagem) nunca mostra o payload. Só `esys-review show
    <id>` revela o conteúdo completo — um "--reveal" explícito, não a
    vista por omissão.
"""

import json
import os
import stat
import urllib.request
import urllib.error
import uuid
from datetime import datetime, timezone, timedelta

DEFAULT_LOG_PATH = os.path.join(os.path.expanduser("~"), ".esys", "blocked_log.jsonl")
LOG_PATH = os.environ.get("ESYS_AUDIT_LOG_PATH", DEFAULT_LOG_PATH)

SYNCED_FOLDER_MARKERS = ["onedrive", "icloud drive", "dropbox"]

SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_SERVICE_KEY = os.environ.get("SUPABASE_SERVICE_KEY")

_warned_about_sync = False


def _warn_if_synced_path(path: str) -> None:
    global _warned_about_sync
    if _warned_about_sync:
        return
    normalized = os.path.abspath(path).lower()
    for marker in SYNCED_FOLDER_MARKERS:
        if marker in normalized:
            print(
                f"aviso: o log de auditoria ({path}) parece estar dentro de uma "
                f"pasta sincronizada para a cloud ({marker}). Isto pode enviar "
                f"dados sensíveis para fora desta máquina sem intenção. "
                f"Considera definir ESYS_AUDIT_LOG_PATH para um caminho fora "
                f"dessa pasta."
            )
            _warned_about_sync = True
            return


def _restrict_permissions(path: str) -> None:
    try:
        os.chmod(path, stat.S_IRUSR | stat.S_IWUSR)
    except OSError:
        pass


def _send_to_supabase(entry: dict) -> None:
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
    _warn_if_synced_path(LOG_PATH)

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
    _restrict_permissions(LOG_PATH)

    _send_to_supabase(entry)
    return entry_id


def load_all() -> list[dict]:
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
        _restrict_permissions(LOG_PATH)
        _update_status_in_supabase(entry_id, status)
    return found


def purge_older_than(days: int) -> int:
    entries = load_all()
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    kept = []
    removed = 0
    for e in entries:
        try:
            ts = datetime.fromisoformat(e["timestamp"])
        except (KeyError, ValueError):
            kept.append(e)
            continue
        if ts >= cutoff:
            kept.append(e)
        else:
            removed += 1
    if removed:
        with open(LOG_PATH, "w", encoding="utf-8") as f:
            for e in kept:
                f.write(json.dumps(e) + "\n")
        _restrict_permissions(LOG_PATH)
    return removed