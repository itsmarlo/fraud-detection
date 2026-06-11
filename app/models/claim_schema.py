from datetime import date

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ClaimInput(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    claim_id: str = Field(min_length=1)
    policy_id: str = Field(min_length=1)
    policyholder_id: str = Field(min_length=1)
    claim_amount: float = Field(ge=0)
    vehicle_value: float = Field(gt=0)
    repair_estimate_amount: float = Field(ge=0)
    accident_date: date
    claim_report_date: date
    policy_start_date: date
    policy_end_date: date
    coverage_type: str = Field(min_length=1)
    driver_age: int = Field(ge=16, le=110)
    vehicle_age_years: int = Field(ge=0, le=100)
    vehicle_mileage: int = Field(ge=0)
    number_of_previous_claims: int = Field(ge=0)
    number_of_previous_rejected_claims: int = Field(ge=0)
    premium_payment_status: str = Field(min_length=1)
    recent_policy_change: bool
    accident_location: str = Field(min_length=1)
    accident_time_hour: int = Field(ge=0, le=23)
    damage_description: str
    garage_id: str = Field(min_length=1)
    garage_previous_suspicious_claims: int = Field(ge=0)
    has_police_report: bool
    has_damage_photos: bool
    has_repair_invoice: bool
    has_witness_statement: bool
    invoice_date: date | None = None
    photo_capture_date: date | None = None
    bank_account_hash: str | None = None
    phone_hash: str | None = None
    email_hash: str | None = None
    third_party_involved: bool

    @model_validator(mode="after")
    def validate_dates(self) -> "ClaimInput":
        if self.policy_end_date < self.policy_start_date:
            raise ValueError("policy_end_date must not be before policy_start_date")
        return self


class BatchClaimInput(BaseModel):
    claims: list[ClaimInput] = Field(min_length=1, max_length=100)
