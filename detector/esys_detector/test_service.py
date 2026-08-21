"""
Testes de service.py -- foco em pedidos HTTP malformados/inesperados.

Motivação: antes desta correção, um payload com tipo errado (número,
lista, null -- em vez de string) chegava a passar pela validação de JSON
(a chave "payload" existe, o JSON é válido), mas rebentava mais tarde,
sem tratamento, dentro dos detectores (`AWS_KEY_RE.finditer(payload)`
espera uma string). O cliente não recebia erro nenhum -- a ligação era
cortada a meio (connection reset), sem corpo de resposta, e o servidor
despejava um traceback completo para o stderr.

Isto foi confirmado a acontecer de verdade contra o serviço real a
correr (HTTP 000 no curl, connection reset) antes de ser corrigido.
Estes testes usam o servidor HTTP real (não chamam handlers Python
diretamente) precisamente porque o bug só se manifestava no caminho
HTTP completo.
"""

import json
import threading
import http.client
import time

import pytest

from esys_detector.service import Handler
from http.server import HTTPServer


@pytest.fixture(scope="module")
def running_server():
    server = HTTPServer(("127.0.0.1", 0), Handler)
    port = server.server_address[1]
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.1)
    yield port
    server.shutdown()
    thread.join(timeout=2)


def _post(port: int, body: dict) -> tuple[int, dict | None]:
    conn = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    conn.request(
        "POST",
        "/inspect",
        body=json.dumps(body),
        headers={"Content-Type": "application/json"},
    )
    resp = conn.getresponse()
    status = resp.status
    raw = resp.read()
    conn.close()
    parsed = json.loads(raw) if raw else None
    return status, parsed


def test_payload_numero_da_400_limpo_nao_connection_reset(running_server):
    status, body = _post(running_server, {"payload": 12345})
    assert status == 400
    assert body == {"error": "invalid_request"}


def test_payload_lista_da_400_limpo(running_server):
    status, body = _post(running_server, {"payload": ["a", "b"]})
    assert status == 400
    assert body == {"error": "invalid_request"}


def test_payload_null_da_400_limpo(running_server):
    status, body = _post(running_server, {"payload": None})
    assert status == 400
    assert body == {"error": "invalid_request"}


def test_payload_string_normal_continua_a_funcionar(running_server):
    """Regressão: a correção não pode ter partido o caminho normal."""
    status, body = _post(running_server, {"payload": "AKIA1234567890ABCDEF"})
    assert status == 200
    assert body["action"] == "BLOCK"


def test_chave_payload_em_falta_continua_400(running_server):
    status, body = _post(running_server, {})
    assert status == 400
    assert body == {"error": "invalid_request"}


def test_servidor_sobrevive_a_varios_pedidos_malformados_seguidos(running_server):
    """Confirma que o servidor não degrada nem morre depois de vários
    pedidos malformados em sequência -- só porque um pedido individual
    dá 400 não significa que o servidor continue saudável a seguir."""
    for bad_payload in [12345, ["x"], None, {"nested": "dict"}, True]:
        status, _ = _post(running_server, {"payload": bad_payload})
        assert status == 400

    status, body = _post(running_server, {"payload": "o meu email é joao@example.com"})
    assert status == 200
    assert body["action"] == "REDACT"