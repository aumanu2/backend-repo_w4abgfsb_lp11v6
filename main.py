import os
from typing import List, Dict
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from database import db, create_document, get_documents
from schemas import FinancialProfile, Transaction, AnalysisRequest, Alert, AnalysisResult

app = FastAPI(title="Financial Protection AI Agent")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "Financial Protection AI Agent Backend"}

@app.get("/test")
def test_database():
    """Test endpoint to check if database is available and accessible"""
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

# Helper: compute protection score and alerts

def analyze_financial_protection(profile: FinancialProfile, transactions: List[Transaction]):
    income = profile.monthly_income
    expenses = profile.monthly_expenses
    savings = profile.savings
    dependents = profile.dependents

    # Basic stats
    monthly_net = income - expenses
    burn_rate_months = (savings / expenses) if expenses > 0 else 12.0

    # Category spending from provided transactions
    category_totals: Dict[str, float] = {}
    total_debits = 0.0
    for t in transactions:
        amt = t.amount
        # Convention: positive = outflow
        if amt > 0:
            total_debits += amt
            if t.category:
                category_totals[t.category] = category_totals.get(t.category, 0) + amt

    alerts: List[Alert] = []

    # Emergency fund alert
    target_months = 3 if profile.risk_tolerance == "high" else 6 if profile.risk_tolerance == "medium" else 9
    if burn_rate_months < target_months:
        shortfall = max(0.0, target_months * expenses - savings)
        alerts.append(Alert(
            user_email=profile.email,
            alert_type="emergency_fund_shortfall",
            severity="high" if burn_rate_months < target_months/2 else "medium",
            message=f"Emergency fund covers {burn_rate_months:.1f} months; target is {target_months} months.",
            data={"shortfall": round(shortfall, 2), "target_months": target_months}
        ))

    # Insurance coverage alerts
    if not profile.insurance_health:
        alerts.append(Alert(
            user_email=profile.email,
            alert_type="missing_health_insurance",
            severity="high",
            message="Health insurance not detected.",
            data={}
        ))
    if not profile.insurance_renters:
        alerts.append(Alert(
            user_email=profile.email,
            alert_type="missing_renters_insurance",
            severity="medium",
            message="Renter's/home insurance not detected.",
            data={}
        ))
    if not profile.insurance_auto and total_debits > 0:
        alerts.append(Alert(
            user_email=profile.email,
            alert_type="missing_auto_insurance",
            severity="medium",
            message="Auto insurance not detected.",
            data={}
        ))
    if dependents > 0 and not profile.insurance_life:
        alerts.append(Alert(
            user_email=profile.email,
            alert_type="missing_life_insurance",
            severity="high",
            message="Life insurance recommended when you have dependents.",
            data={"dependents": dependents}
        ))

    # Overspending vs income
    if income > 0 and total_debits > income * 1.1:
        alerts.append(Alert(
            user_email=profile.email,
            alert_type="overspending",
            severity="medium",
            message="Recent spending exceeds monthly income by more than 10%.",
            data={"income": income, "spend": round(total_debits, 2)}
        ))

    # Budget adherence alerts when budgets are provided
    if profile.budgets:
        for cat, limit in profile.budgets.items():
            spent = category_totals.get(cat, 0.0)
            if limit and spent > limit:
                alerts.append(Alert(
                    user_email=profile.email,
                    alert_type="budget_exceeded",
                    severity="low" if spent <= limit*1.1 else "medium",
                    message=f"Spending in {cat} is {spent:.2f} which exceeds your budget {limit:.2f}.",
                    data={"category": cat, "spent": round(spent,2), "limit": limit}
                ))

    # Score from 0-100 based on key pillars
    score = 100
    # Emergency fund weight
    score -= int(max(0, (target_months - burn_rate_months) / target_months) * 40)
    # Insurance coverage weight
    missing_insurance = sum([
        1 if not profile.insurance_health else 0,
        1 if not profile.insurance_renters else 0,
        1 if not profile.insurance_auto else 0,
        1 if (dependents > 0 and not profile.insurance_life) else 0,
    ])
    score -= missing_insurance * 10
    # Cash flow weight
    if monthly_net < 0:
        score -= 20
    elif monthly_net < expenses * 0.1:
        score -= 10

    score = max(0, min(100, score))

    stats = {
        "monthly_income": income,
        "monthly_expenses": expenses,
        "monthly_net": round(monthly_net, 2),
        "savings": savings,
        "burn_rate_months": round(burn_rate_months, 2),
        "total_spend": round(total_debits, 2)
    }

    summary = (
        f"Protection score {score}/100. Net cash flow {monthly_net:.2f} per month. "
        f"Emergency fund covers {burn_rate_months:.1f} months (target {target_months}). "
        f"Generated {len(alerts)} alerts."
    )

    return AnalysisResult(score=score, summary=summary, alerts=alerts, stats=stats)

# API endpoints

@app.post("/api/analyze", response_model=AnalysisResult)
def analyze_finances(req: AnalysisRequest):
    # Persist profile and transactions
    try:
        create_document("financialprofile", req.profile)
        for t in req.transactions:
            create_document("transaction", t)
    except Exception:
        # Database may be unavailable; proceed without persistence
        pass

    result = analyze_financial_protection(req.profile, req.transactions)
    try:
        create_document("analysisresult", result)
        for a in result.alerts:
            create_document("alert", a)
    except Exception:
        pass

    return result

@app.get("/api/alerts/{email}", response_model=List[Alert])
def get_alerts(email: str):
    try:
        docs = get_documents("alert", {"user_email": email})
        # Convert to pydantic models
        alerts = []
        for d in docs:
            d.pop("_id", None)
            alerts.append(Alert(**d))
        return alerts
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
