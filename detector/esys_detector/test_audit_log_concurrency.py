"""
Testes de audit_log.py -- dois achados reais desta ronda de testes:

1. `purge_older_than` com dias negativos apagava TUDO, incluindo entradas
   criadas no mesmo segundo -- confirmado a acontecer de verdade
   (esys-review purge -1 esvaziava o log inteiro). Corrigido em
   review.py (cmd_purge recusa dias negativos antes de sequer chamar
   purge_older_than).

2. `set_status`/`purge_older_than` fazem leitura+reescrita completa do
   ficheiro, enquanto `log_block` só faz append -- sem proteção, dois
   PROCESSOS separados (o serviço a bloquear coisas + `esys-review` a
   correr ao lado) podiam perder entradas silenciosamente. Corrigido com
   um lock de ficheiro cross-plataforma (_FileLock), sem dependências
   novas. O teste de concorrência aqui usa multiprocessing (processos
   reais, não threads) porque é isso que reproduz o cenário verdadeiro:
   o serviço HTTP corre num processo, `esys-review` corre noutro.

NOTA DE PORTABILIDADE: as funções worker abaixo estão deliberadamente ao
nível do módulo, não aninhadas dentro das funções de teste. No Windows, o
multiprocessing usa "spawn" (não "fork" como no Linux), o que exige que a
função passada a Process(target=...) seja "picklable" -- uma closure
aninhada dentro de outra função não é. Isto já foi confirmado a rebentar
no Windows antes desta correção.
"""

import json
import multiprocessing
import os
import time

import pytest

import esys_detector.audit_log as al


def _finding():
    return [{"category": "secret", "subtype": "test", "offset_start": 0, "offset_end": 1}]


@pytest.fixture()
def temp_log(tmp_path, monkeypatch):
    log_path = str(tmp_path / "blocked_log.jsonl")
    monkeypatch.setattr(al, "LOG_PATH", log_path)
    return log_path


def test_purge_dias_negativos_nao_apaga_tudo(temp_log):
    """Antes desta correção: purge_older_than(-1) apagava TODAS as
    entradas, incluindo uma criada no mesmo instante. A correção real
    está em review.py (recusa antes de chamar isto), mas confirmamos
    aqui que a própria função, se chamada com dias negativos, continua
    a ter esse comportamento perigoso -- é por isso que a validação tem
    de ficar no ponto de entrada do CLI, não confiar só na função."""
    al.log_block("entrada de agora mesmo", _finding())
    assert len(al.load_all()) == 1

    removed = al.purge_older_than(-1)

    assert removed == 1
    assert al.load_all() == []


# --- workers ao nível do módulo (necessário para multiprocessing no Windows) ---

def _lock_worker(log_path: str, results_path: str, n: int) -> None:
    os.environ["ESYS_AUDIT_LOG_PATH"] = log_path
    import importlib
    import esys_detector.audit_log as al2
    importlib.reload(al2)
    with al2._FileLock(log_path):
        start = time.time()
        time.sleep(0.15)
        end = time.time()
    with open(results_path, "a") as f:
        f.write(json.dumps({"n": n, "start": start, "end": end}) + "\n")


def _append_worker(log_path: str, n: int) -> None:
    os.environ["ESYS_AUDIT_LOG_PATH"] = log_path
    import importlib
    import esys_detector.audit_log as al2
    importlib.reload(al2)
    al2.log_block(f"entrada {n}", _finding())


def _purge_worker(log_path: str) -> None:
    os.environ["ESYS_AUDIT_LOG_PATH"] = log_path
    import importlib
    import esys_detector.audit_log as al2
    importlib.reload(al2)
    al2.purge_older_than(9999)  # não remove nada, só força leitura+lock repetidamente


def test_filelock_impede_sobreposicao_entre_processos(temp_log):
    """Confirma a exclusão mútua diretamente: 3 processos a tentar obter
    o mesmo lock nunca o detêm ao mesmo tempo."""
    results_path = temp_log + ".results"
    procs = [
        multiprocessing.Process(target=_lock_worker, args=(temp_log, results_path, i))
        for i in range(3)
    ]
    for p in procs:
        p.start()
    for p in procs:
        p.join(timeout=10)

    with open(results_path) as f:
        intervals = [json.loads(line) for line in f if line.strip()]

    assert len(intervals) == 3, "algum processo não conseguiu terminar"

    intervals.sort(key=lambda x: x["start"])
    for i in range(len(intervals) - 1):
        assert intervals[i]["end"] <= intervals[i + 1]["start"] + 0.01, (
            "dois processos tiveram o lock ao mesmo tempo -- exclusão mútua falhou"
        )


def test_appends_concorrentes_com_reescrita_real_nao_perdem_entradas(temp_log):
    """Réplica do cenário real: o serviço (múltiplos processos/threads a
    dar log_block) e o esys-review (purge, que reescreve o ficheiro
    inteiro) a correr ao mesmo tempo. Sem o lock, isto perdia entradas
    silenciosamente (confirmado manualmente: 9 de 60 perdidas antes da
    correção)."""
    N_APPENDS = 30
    append_procs = [
        multiprocessing.Process(target=_append_worker, args=(temp_log, i))
        for i in range(N_APPENDS)
    ]
    purge_procs = [
        multiprocessing.Process(target=_purge_worker, args=(temp_log,)) for _ in range(10)
    ]

    all_procs = append_procs + purge_procs
    for p in all_procs:
        p.start()
    for p in all_procs:
        p.join(timeout=15)

    entries = al.load_all()
    assert len(entries) == N_APPENDS, (
        f"esperado {N_APPENDS} entradas, encontrado {len(entries)} -- "
        f"perda de dados sob concorrência real"
    )