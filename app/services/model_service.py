import pickle
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score, brier_score_loss, roc_auc_score
from sklearn.model_selection import train_test_split

from app.core.config import get_settings
from app.models.claim_schema import ClaimInput
from app.models.scoring_schema import ModelInfoResponse, TrainingResponse


FEATURES = [
    "claim_vehicle_ratio",
    "repair_vehicle_ratio",
    "days_since_policy_start",
    "report_delay_days",
    "previous_claims",
    "previous_rejected_claims",
    "premium_overdue",
    "recent_policy_change",
    "unusual_accident_hour",
    "garage_suspicious_claims",
    "missing_police_report",
    "missing_damage_photos",
    "missing_repair_invoice",
]

MODEL_TYPE = "CalibratedHistGradientBoostingClassifier"


class ModelService:
    def __init__(self, model_path: Path | None = None) -> None:
        self.settings = get_settings()
        self.model_path = model_path or self.settings.model_path

    @staticmethod
    def claim_features(claim: ClaimInput) -> dict[str, float]:
        return {
            "claim_vehicle_ratio": claim.claim_amount / claim.vehicle_value,
            "repair_vehicle_ratio": claim.repair_estimate_amount / claim.vehicle_value,
            "days_since_policy_start": (claim.accident_date - claim.policy_start_date).days,
            "report_delay_days": (claim.claim_report_date - claim.accident_date).days,
            "previous_claims": claim.number_of_previous_claims,
            "previous_rejected_claims": claim.number_of_previous_rejected_claims,
            "premium_overdue": float(claim.premium_payment_status.upper() not in {"PAID", "CURRENT"}),
            "recent_policy_change": float(claim.recent_policy_change),
            "unusual_accident_hour": float(0 <= claim.accident_time_hour <= 5),
            "garage_suspicious_claims": claim.garage_previous_suspicious_claims,
            "missing_police_report": float(not claim.has_police_report),
            "missing_damage_photos": float(not claim.has_damage_photos),
            "missing_repair_invoice": float(not claim.has_repair_invoice),
        }

    def train(self, csv_path: Path | None = None) -> TrainingResponse:
        csv_path = csv_path or Path("app/data/sample_claims.csv")
        frame = pd.read_csv(csv_path)
        missing = set(FEATURES + ["fraud_label"]) - set(frame.columns)
        if missing:
            raise ValueError(f"Training data is missing columns: {sorted(missing)}")

        x_train, x_test, y_train, y_test = train_test_split(
            frame[FEATURES],
            frame["fraud_label"],
            test_size=0.25,
            random_state=42,
            stratify=frame["fraud_label"],
        )
        base_model = HistGradientBoostingClassifier(
            learning_rate=0.06,
            max_iter=200,
            max_leaf_nodes=15,
            min_samples_leaf=10,
            l2_regularization=1.0,
            class_weight="balanced",
            random_state=42,
        )
        model = CalibratedClassifierCV(
            estimator=base_model,
            method="sigmoid",
            cv=3,
            n_jobs=1,
        )
        model.fit(x_train, y_train)
        predictions = model.predict(x_test)
        probabilities = model.predict_proba(x_test)[:, 1]
        metrics = {
            "accuracy": float(accuracy_score(y_test, predictions)),
            "roc_auc": float(roc_auc_score(y_test, probabilities)) if len(set(y_test)) > 1 else None,
            "brier_score": float(brier_score_loss(y_test, probabilities)),
        }
        payload = {
            "model": model,
            "model_type": MODEL_TYPE,
            "features": FEATURES,
            "model_version": self.settings.model_version,
            "trained_at": datetime.now(UTC),
            "metrics": metrics,
        }
        self.model_path.parent.mkdir(parents=True, exist_ok=True)
        with self.model_path.open("wb") as output:
            pickle.dump(payload, output)
        return TrainingResponse(
            model_version=self.settings.model_version,
            model_type=MODEL_TYPE,
            training_samples=len(frame),
            fraud_rate=round(float(frame["fraud_label"].mean()), 4),
            accuracy=round(metrics["accuracy"], 4),
            roc_auc=round(metrics["roc_auc"], 4) if metrics["roc_auc"] is not None else None,
            brier_score=round(metrics["brier_score"], 4),
            feature_list=FEATURES,
            trained_at=payload["trained_at"],
        )

    def predict(self, claim: ClaimInput) -> float | None:
        payload = self._load()
        if not payload:
            return None
        features = self.claim_features(claim)
        if not set(payload["features"]).issubset(features):
            return None
        frame = pd.DataFrame([features])[payload["features"]]
        return round(float(payload["model"].predict_proba(frame)[0][1] * 100), 2)

    def info(self) -> ModelInfoResponse:
        payload = self._load()
        if not payload:
            return ModelInfoResponse(
                model_version=self.settings.model_version,
                model_type=MODEL_TYPE,
                trained_at=None,
                feature_list=FEATURES,
                available=False,
            )
        return ModelInfoResponse(
            model_version=payload["model_version"],
            model_type=payload.get("model_type", type(payload["model"]).__name__),
            trained_at=payload["trained_at"],
            feature_list=payload["features"],
            available=True,
            metrics=payload.get("metrics", {}),
        )

    def _load(self) -> dict[str, Any] | None:
        if not self.model_path.exists():
            return None
        try:
            with self.model_path.open("rb") as source:
                return pickle.load(source)
        except (OSError, pickle.UnpicklingError, EOFError):
            return None


model_service = ModelService()
