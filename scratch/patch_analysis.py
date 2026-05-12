import os

file_path = r"c:\Users\jamaa\OneDrive\Documenti\SentinelTrading\src\sentinel\api\routes\analysis.py"

with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

content = content.replace(
    "    upsert_api_credential,\n    update_onboarding_job,\n    upsert_user,\n)",
    "    upsert_api_credential,\n    update_onboarding_job,\n    upsert_user,\n    update_risk_audit_explanation,\n)"
)

shap_bg = """        )
    return pd.DataFrame(rows)


async def _compute_shap_background(
    context: TradeContext,
    user_id: str,
    audit_id: int,
) -> None:
    try:
        from sentinel.infra.db import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            brain = await get_user_brain(user_id, session)
            if brain is None:
                brain = SentinelBrain()
            
            X_input = brain._context_to_dataframe(context)
            explanation = await asyncio.to_thread(brain._explain, X_input)
            
            exp_list = [e.model_dump(mode="json") for e in explanation] if hasattr(explanation[0], "model_dump") else [e for e in explanation] if explanation else []
            top_reason = exp_list[0]["feature"] if exp_list else None
            
            await update_risk_audit_explanation(session, audit_id, exp_list, top_reason)
    except Exception:
        logger.exception("Background SHAP calculation failed for %s", user_id)


async def _train_and_persist_user_model("""

content = content.replace(
    "        )\n    return pd.DataFrame(rows)\n\n\nasync def _train_and_persist_user_model(",
    shap_bg
)

content = content.replace(
    "async def analyze_trade(\n    context: TradeContext,\n    session: AsyncSession = Depends(get_db),\n) -> RiskAssessment:",
    "async def analyze_trade(\n    context: TradeContext,\n    background_tasks: BackgroundTasks,\n    session: AsyncSession = Depends(get_db),\n) -> RiskAssessment:"
)

content = content.replace(
    "    if brain is None:\n        brain = SentinelBrain()\n\n    assessment = await asyncio.to_thread(brain.assess_risk, context)\n\n    try:",
    "    if brain is None:\n        brain = SentinelBrain()\n\n    assessment = await asyncio.to_thread(brain.assess_risk, context, skip_explanation=True)\n\n    try:"
)

old_audit = """    try:
        await record_risk_audit(
            session,
            user_id=context.user_id,
            symbol=context.symbol,
            decision=assessment.decision.value,
            risk_score=assessment.risk_score,
            size_multiplier=assessment.size_multiplier,
            mode=assessment.mode.value,
            is_anomaly=assessment.is_anomaly,
            top_reason=assessment.explanation[0].feature if assessment.explanation else None,
            explanation=assessment.model_dump(mode="json")["explanation"],
            latency_ms=assessment.latency_ms,
            cached=False,
        )
    except Exception:"""

new_audit = """    try:
        audit_record = await record_risk_audit(
            session,
            user_id=context.user_id,
            symbol=context.symbol,
            decision=assessment.decision.value,
            risk_score=assessment.risk_score,
            size_multiplier=assessment.size_multiplier,
            mode=assessment.mode.value,
            is_anomaly=assessment.is_anomaly,
            top_reason=None,
            explanation=[],
            latency_ms=assessment.latency_ms,
            cached=False,
        )
        if getattr(audit_record, "id", None) is not None:
            background_tasks.add_task(_compute_shap_background, context, context.user_id, audit_record.id)
    except Exception:"""

content = content.replace(old_audit, new_audit)

with open(file_path, "w", encoding="utf-8") as f:
    f.write(content)

print("Patch successful!")
