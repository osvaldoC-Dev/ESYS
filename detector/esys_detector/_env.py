"""
Carregador minúsculo de .env — sem trazer a dependência python-dotenv,
mantendo o detector com zero dependências externas.

Lê detector/.env (se existir) e define as variáveis em os.environ, só se
ainda não estiverem definidas (uma variável já exportada no shell tem
sempre prioridade sobre o ficheiro).
"""

import os

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", ".env")


def load() -> None:
    if not os.path.exists(_ENV_PATH):
        return
    with open(_ENV_PATH, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip()
            value = value.strip()
            if key and key not in os.environ:
                os.environ[key] = value


load()
