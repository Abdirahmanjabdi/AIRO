target = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\src\sentinel\domain\models.py"

with open(target, "r", encoding="utf-8") as f:
    content = f.read()

# The file lost these classes between RiskAssessment and CredentialResponse.
# We insert the three missing classes right before CredentialResponse.
insert_before = """class CredentialResponse(BaseModel):
    \"\"\"Response after secure credential storage.\"\"\""""

insertion = """class UserBaseline(BaseModel):
    \"\"\"Per-user model metadata returned to the frontend/API.\"\"\"

    user_id: str
    broker_server: str | None = None
    account_id: str | None = None
    trade_count: int = Field(..., ge=0)
    model_s3_key: str | None = None
    trained_at: datetime | None = None
    is_baseline_ready: bool = False
    risk_threshold: float = 0.6537
    contamination: float = 0.0399

    @field_validator("is_baseline_ready")
    @classmethod
    def validate_baseline(cls, value: bool, info: object) -> bool:
        data = getattr(info, "data", {})
        trade_count = data.get("trade_count", 0)
        if value and trade_count < 1:
            raise ValueError(
                f"Cannot be baseline_ready with only {trade_count} trades (min 1)"
            )
        return value


class OnboardingRequest(BaseModel):
    \"\"\"Public onboarding request body.\"\"\"

    user_id: str = Field(..., min_length=1)
    broker_server: str = Field(..., min_length=1)
    account_id: str = Field(..., min_length=1)
    min_trades: int = Field(default=10, ge=1, le=500)


class CredentialRequest(BaseModel):
    \"\"\"Secure broker credential submission stored in Vault.\"\"\"

    user_id: str = Field(..., min_length=1)
    broker_server: str = Field(..., min_length=1)
    account_id: str = Field(..., min_length=1)
    read_only_password: str = Field(..., min_length=1)


"""

# Also remove the orphaned CredentialRequest fields that are floating above CredentialResponse
orphan = """    user_id: str = Field(..., min_length=1)\r\n    broker_server: str = Field(..., min_length=1)\r\n    account_id: str = Field(..., min_length=1)\r\n    read_only_password: str = Field(..., min_length=1)\r\n\r\n\r\n"""

if orphan in content:
    content = content.replace(orphan, "")
    print("Removed orphaned CredentialRequest fields")
else:
    # Try Unix line endings
    orphan2 = """    user_id: str = Field(..., min_length=1)\n    broker_server: str = Field(..., min_length=1)\n    account_id: str = Field(..., min_length=1)\n    read_only_password: str = Field(..., min_length=1)\n\n\n"""
    if orphan2 in content:
        content = content.replace(orphan2, "")
        print("Removed orphaned CredentialRequest fields (unix endings)")
    else:
        print("WARNING: Could not find orphaned fields to remove")

if insert_before in content:
    content = content.replace(insert_before, insertion + insert_before)
    print("Inserted missing classes successfully")
else:
    print("ERROR: Could not find insertion point")
    print("Content around that area:")
    idx = content.find("CredentialResponse")
    print(repr(content[max(0,idx-200):idx+200]))

with open(target, "w", encoding="utf-8") as f:
    f.write(content)

print("Done.")
