# Slide: Fraud Detection Claims Solution - Technical View

## Slide Title
Fraud Detection Claims API: Technical Architecture

## Subtitle
SAP AI Core serving endpoint for explainable motor-claim fraud scoring with structured claim data, multi-file evidence, optional ML, and optional multimodal LLM analysis.

## Main Message
The service exposes a Joule-ready inference API that receives claim metadata plus document/image evidence, validates and stores evidence, runs hybrid fraud scoring, and returns a normalized decision payload for downstream claims workflows.

## Slide Layout

### Left Panel: API Contract
**Inference request**

- Endpoint: `POST /api/v1/inference/fraud-assessment`
- Payload sections: `claim` and `evidence`
- `claim`: policy, vehicle, incident, repair, garage, history, dates
- `evidence[]`: multi-file array with `filename`, `content_type`, `document_type`, `content_base64`
- Supported evidence: damage photos, police reports, invoices, witness statements, claim forms, driver license, vehicle registration

### Center Panel: Runtime Pipeline
**Validation + scoring**

- Base64 decode and MIME/extension validation
- File validation for text, PDF, DOCX, and image evidence
- Structured rule scoring across policy, behavior, damage, document, and network signals
- Optional calibrated histogram gradient boosting model for tabular fraud probability
- Optional SAP AI Core / BTP multimodal LLM encoder for semantic document/image review
- Score fusion produces final `fraud_score`, `risk_level`, confidence, and reasons

### Right Panel: Deployment + Output
**SAP AI Core serving**

- Container image: `docker.io/itsmarlo/fraud-detection-claims-api:v1`
- ServingTemplate: KServe-compatible `kserve-container`, port `8080`, protocol `TCP`
- GitOps source: private GitHub repo synced by SAP AI Launchpad
- Deployment invoke path: `/v2/inference/deployments/{deploymentId}/api/v1/inference/fraud-assessment`
- Response: score, risk level, evidence used, component scores, recommended action, Joule workflow object

## Suggested Visual
A technical architecture flow:

`S/4HANA / Joule Payload -> SAP AI Core Inference Endpoint -> FastAPI Service -> Evidence Validation -> Rules + Optional ML + Optional Multimodal LLM -> Fraud Decision JSON`

Use compact labels for:

- `claim`
- `evidence[]`
- Docker container
- rule engine
- gradient boosting
- multimodal LLM
- Joule response

## Technical Callouts

- **Explainability**: every score includes reason codes, severity, warnings, and recommended action
- **Composable intelligence**: rules are always available; tabular ML and multimodal LLM are optional runtime layers
- **Evidence-first API**: one payload supports mixed documents and images through the `evidence[]` array
- **SAP-ready deployment**: Docker image, AI Core ServingTemplate, private Git sync, registry secret, and AI Launchpad configuration

## Speaker Notes
The fraud detection API is deployed as a SAP AI Core serving workload. The consumer sends one JSON request containing structured claim data and an evidence array. Each evidence item carries the business document type and the technical MIME type, allowing the API to validate and process mixed text documents, PDFs, DOCX files, and images. The scoring layer is hybrid: deterministic rules provide the baseline and explanation, optional gradient boosting adds tabular prediction, and optional SAP AI Core/BTP multimodal LLM analysis reviews documents and images. The response is structured for Joule and claims automation, including final fraud score, risk level, reasons, warnings, evidence used, component scores, and workflow-ready recommendations.

## Footer
FastAPI | Docker | SAP AI Core ServingTemplate | KServe container | Rule scoring + optional ML + optional multimodal LLM
