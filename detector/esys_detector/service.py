"""
Expõe o detector como um serviço HTTP local que o proxy (Node) chama antes
de deixar cada request seguir para o provider de IA.

Sem dependências externas (usa só a biblioteca nativa do Python) — evita
problemas de build de pacotes como fastapi/pydantic em versões novas do
Python (ex: 3.14) onde ainda não existem wheels pré-compiladas.

Correr com: python -m esys_detector.service
Porta por omissão: 8787 (define ESYS_DETECTOR_PORT para mudar)
"""

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from esys_detector.detectors.secrets import detect_secrets
from esys_detector.detectors.pii import detect_pii
from esys_detector.detectors.prompt_injection import detect_prompt_injection
from esys_detector.policy import decide
from esys_detector.audit_log import log_block

PORT = int(os.environ.get("ESYS_DETECTOR_PORT", "8787"))


class Handler(BaseHTTPRequestHandler):
    def _send_json(self, status: int, body: dict) -> None:
        payload = json.dumps(body).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def do_GET(self):
        if self.path == "/health":
            return self._send_json(200, {"status": "ok"})
        self._send_json(404, {"error": "not_found"})

    def do_POST(self):
        if self.path != "/inspect":
            return self._send_json(404, {"error": "not_found"})

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length)
            body = json.loads(raw)
            payload = body["payload"]
        except Exception:
            return self._send_json(400, {"error": "invalid_request"})

        findings = detect_secrets(payload) + detect_pii(payload) + detect_prompt_injection(payload)
        decision = decide(payload, findings)

        entry_id = None
        if decision["action"] == "BLOCK":
            entry_id = log_block(payload, findings)

        self._send_json(200, {
            "action": decision["action"],
            "finding_count": len(findings),
            "redacted_payload": decision.get("redacted_payload"),
            "token_map": decision.get("token_map"),
            "audit_id": entry_id,
        })

    def log_message(self, fmt, *args):
        print(f"{self.address_string()} - {fmt % args}")


def main():
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"ESYS Detector Service listening on :{PORT}")
    server.serve_forever()


if __name__ == "__main__":
    main()