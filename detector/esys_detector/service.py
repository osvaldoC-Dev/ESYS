"""
Expõe o detector como um serviço HTTP local que o proxy (Node) chama antes
de deixar cada request seguir para o provider de IA.

Correr com: uvicorn esys_detector.service:app --port 8787
"""

from fastapi import FastAPI
from pydantic import BaseModel

from esys_detector.detectors.secrets import detect_secrets
from esys_detector.detectors.pii import detect_pii
from esys_detector.policy import decide

app = FastAPI(title="ESYS Detector Service")


class InspectRequest(BaseModel):
    payload: str


class InspectResponse(BaseModel):
    action: str
    finding_count: int


@app.post("/inspect", response_model=InspectResponse)
def inspect(req: InspectRequest) -> InspectResponse:
    findings = detect_secrets(req.payload) + detect_pii(req.payload)
    decision = decide(req.payload, findings)
    return InspectResponse(action=decision["action"], finding_count=len(findings))


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
