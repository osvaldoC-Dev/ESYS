"""
Local HTTP service exposing the detector to the Node proxy.

Run with: uvicorn esys_detector.service:app --reload --port 8787
"""

from fastapi import FastAPI
from pydantic import BaseModel

from esys_detector.detectors import pii, secrets
from esys_detector.policy import evaluate

app = FastAPI(title="ESYS Detector")


class InspectRequest(BaseModel):
    payload: str


class InspectResponse(BaseModel):
    decision: str
    finding_count: int
    redacted_payload: str | None = None


@app.post("/inspect", response_model=InspectResponse)
def inspect(req: InspectRequest) -> InspectResponse:
    findings = secrets.detect(req.payload) + pii.detect(req.payload)
    result = evaluate(req.payload, findings)
    return InspectResponse(
        decision=result.decision.value,
        finding_count=len(result.findings),
        redacted_payload=result.redacted_payload,
    )


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}
