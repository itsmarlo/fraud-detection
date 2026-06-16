# SAP AI Core Serving Deployment

This folder contains the deployment assets for running the fraud assessment API
as an SAP AI Core serving workload that can be invoked from Joule by deployment
ID.

## Serving Contract

Use the JSON-only endpoint:

```text
POST /api/v1/inference/fraud-assessment
```

Request shape:

```json
{
  "claim": {
    "claim_id": "CLM-10001",
    "policy_id": "POL-20001",
    "policyholder_id": "CUST-30001",
    "claim_amount": 8200,
    "vehicle_value": 15000,
    "repair_estimate_amount": 7800,
    "accident_date": "2026-05-10",
    "claim_report_date": "2026-05-20",
    "policy_start_date": "2025-05-01",
    "policy_end_date": "2027-04-30",
    "coverage_type": "COMPREHENSIVE",
    "driver_age": 27,
    "vehicle_age_years": 6,
    "vehicle_mileage": 92000,
    "number_of_previous_claims": 0,
    "number_of_previous_rejected_claims": 0,
    "premium_payment_status": "CURRENT",
    "recent_policy_change": false,
    "accident_location": "Berlin",
    "accident_time_hour": 14,
    "damage_description": "Front bumper and left headlamp damaged after collision.",
    "garage_id": "GAR-009",
    "garage_previous_suspicious_claims": 0,
    "has_police_report": false,
    "has_damage_photos": false,
    "has_repair_invoice": false,
    "has_witness_statement": false,
    "invoice_date": null,
    "photo_capture_date": null,
    "bank_account_hash": null,
    "phone_hash": null,
    "email_hash": null,
    "third_party_involved": true
  },
  "evidence": [
    {
      "filename": "damage.jpg",
      "content_type": "image/jpeg",
      "document_type": "DAMAGE_PHOTO",
      "content_base64": "<base64>"
    }
  ],
  "replace_existing_evidence": true
}
```

Response shape is optimized for Joule:

```json
{
  "claim_id": "CLM-10001",
  "fraud_score": 42.1,
  "risk_level": "MEDIUM",
  "confidence_score": 72.0,
  "recommended_action": "Claims handler review",
  "summary": "Medium risk assessment with 72% confidence. Recommended action: Claims handler review.",
  "reasons": [
    {"code": "MISSING_POLICE_REPORT", "severity": "MEDIUM", "message": "..."}
  ],
  "warnings": [],
  "evidence_used": [],
  "component_scores": {},
  "rule_based_score": 41.0,
  "ml_probability_score": null,
  "model_version": "fraud-score-v2-calibrated-boosting"
}
```

## Build Image

Build and push the Docker image to a registry accessible by SAP AI Core:

```bash
docker build -t <registry>/fraud-detection-claims-api:<tag> .
docker push <registry>/fraud-detection-claims-api:<tag>
```

Then update `serving-template.yaml` image placeholders.

## AI Core Configuration

Create a scenario/executable/configuration/deployment in SAP AI Core or AI
Launchpad using:

```text
ai-core/serving-template.yaml
```

Required environment variables:

```text
ENABLE_LLM_ENCODER=true
LLM_PROVIDER=btp
AICORE_BASE_URL=<AI Core base URL>
AICORE_TOKEN_URL=<OAuth token URL>
AICORE_CLIENT_ID=<client id>
AICORE_CLIENT_SECRET=<client secret>
AICORE_RESOURCE_GROUP=grounding-test
ORCH_DEPLOYMENT_URL=<orchestration deployment URL>
AICORE_LLM_MODEL=claude-sonnet-4
MASKING_REQUIRED=true
```

Keep secrets in AI Core secret bindings, not in Git.
