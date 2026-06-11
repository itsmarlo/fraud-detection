"""Generate deterministic sample data and train the optional fraud model."""

from pathlib import Path

import numpy as np
import pandas as pd

from app.services.model_service import FEATURES, ModelService


DATA_DIR = Path("app/data")


def generate_sample_data(rows: int = 160, seed: int = 42) -> None:
    rng = np.random.default_rng(seed)
    records = []
    for index in range(rows):
        claim_vehicle_ratio = float(np.clip(rng.beta(2, 5) * 1.3, 0.02, 1.4))
        repair_vehicle_ratio = float(np.clip(claim_vehicle_ratio * rng.uniform(0.6, 1.2), 0.01, 1.5))
        previous_claims = int(rng.poisson(1.5))
        previous_rejected = int(rng.binomial(2, 0.12))
        premium_overdue = int(rng.random() < 0.12)
        recent_change = int(rng.random() < 0.18)
        unusual_hour = int(rng.random() < 0.16)
        garage_suspicious = int(rng.poisson(1.4))
        missing_police = int(rng.random() < 0.35)
        missing_photos = int(rng.random() < 0.18)
        missing_invoice = int(rng.random() < 0.22)
        third_without_witness = int(rng.random() < 0.14)
        days_since_policy = int(rng.integers(0, 700))
        report_delay = int(rng.choice([0, 1, 2, 3, 5, 10, 20, 45], p=[.2, .2, .15, .1, .1, .1, .08, .07]))

        risk = (
            2.2 * claim_vehicle_ratio
            + 1.6 * repair_vehicle_ratio
            + 0.8 * (days_since_policy <= 30)
            + 0.5 * (report_delay > 7)
            + 0.25 * previous_claims
            + 0.8 * previous_rejected
            + 0.8 * premium_overdue
            + 0.45 * recent_change
            + 0.35 * unusual_hour
            + 0.22 * garage_suspicious
            + 0.4 * missing_police
            + 0.5 * missing_photos
            + 0.45 * missing_invoice
            + 0.5 * third_without_witness
            + rng.normal(0, 0.5)
        )
        fraud_label = int(risk > 3.8)
        records.append(
            {
                "claim_id": f"CLM-{10000 + index}",
                "policy_id": f"POL-{20000 + index // 2}",
                "garage_id": f"GAR-{1 + index % 20:03d}",
                "claim_vehicle_ratio": round(claim_vehicle_ratio, 4),
                "repair_vehicle_ratio": round(repair_vehicle_ratio, 4),
                "days_since_policy_start": days_since_policy,
                "report_delay_days": report_delay,
                "previous_claims": previous_claims,
                "previous_rejected_claims": previous_rejected,
                "premium_overdue": premium_overdue,
                "recent_policy_change": recent_change,
                "unusual_accident_hour": unusual_hour,
                "garage_suspicious_claims": garage_suspicious,
                "missing_police_report": missing_police,
                "missing_damage_photos": missing_photos,
                "missing_repair_invoice": missing_invoice,
                "third_party_without_witness": third_without_witness,
                "fraud_label": fraud_label,
            }
        )

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records).to_csv(DATA_DIR / "sample_claims.csv", index=False)

    policies = pd.DataFrame(
        {
            "policy_id": [f"POL-{20000 + index}" for index in range(80)],
            "policyholder_id": [f"CUST-{3000 + index}" for index in range(80)],
            "coverage_type": rng.choice(["COMPREHENSIVE", "COLLISION", "THIRD_PARTY"], 80),
            "premium_payment_status": rng.choice(["PAID", "PAID", "PAID", "OVERDUE"], 80),
            "recent_policy_change": rng.choice([False, False, False, True], 80),
        }
    )
    policies.to_csv(DATA_DIR / "sample_policies.csv", index=False)

    garages = pd.DataFrame(
        {
            "garage_id": [f"GAR-{index:03d}" for index in range(1, 21)],
            "garage_name": [f"Partner Repair Center {index}" for index in range(1, 21)],
            "previous_claims": rng.integers(20, 500, 20),
            "previous_suspicious_claims": rng.integers(0, 12, 20),
            "risk_tier": rng.choice(["LOW", "MEDIUM", "HIGH"], 20, p=[0.55, 0.3, 0.15]),
        }
    )
    garages.to_csv(DATA_DIR / "sample_garages.csv", index=False)


if __name__ == "__main__":
    if not (DATA_DIR / "sample_claims.csv").exists():
        generate_sample_data()
    result = ModelService().train()
    print(result.model_dump_json(indent=2))
