"""
Database Schemas

Define your MongoDB collection schemas here using Pydantic models.
These schemas are used for data validation in your application.

Each Pydantic model represents a collection in your database.
Model name is converted to lowercase for the collection name:
- User -> "user" collection
- Product -> "product" collection
- BlogPost -> "blogs" collection
"""

from pydantic import BaseModel, Field
from typing import Optional, List, Dict

# Example schemas (you can still use these if needed)
class User(BaseModel):
    """
    Users collection schema
    Collection name: "user" (lowercase of class name)
    """
    name: str = Field(..., description="Full name")
    email: str = Field(..., description="Email address")
    address: str = Field(..., description="Address")
    age: Optional[int] = Field(None, ge=0, le=120, description="Age in years")
    is_active: bool = Field(True, description="Whether user is active")

class Product(BaseModel):
    """
    Products collection schema
    Collection name: "product" (lowercase of class name)
    """
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: float = Field(..., ge=0, description="Price in dollars")
    category: str = Field(..., description="Product category")
    in_stock: bool = Field(True, description="Whether product is in stock")

# Financial Protection Agent Schemas
class FinancialProfile(BaseModel):
    email: str = Field(..., description="User email to associate data")
    monthly_income: float = Field(..., ge=0, description="Average monthly income")
    monthly_expenses: float = Field(..., ge=0, description="Average monthly fixed expenses")
    savings: float = Field(0, ge=0, description="Liquid savings available for emergencies")
    dependents: int = Field(0, ge=0, description="Number of dependents")
    risk_tolerance: str = Field("medium", description="low | medium | high")
    insurance_health: bool = Field(False)
    insurance_renters: bool = Field(False)
    insurance_auto: bool = Field(False)
    insurance_life: bool = Field(False)
    budgets: Optional[Dict[str, float]] = Field(None, description="Optional category budgets per month")

class Transaction(BaseModel):
    # Use string to avoid BSON date encoding issues in Mongo
    date: Optional[str] = Field(None, description="Transaction date as YYYY-MM-DD")
    description: str = Field(..., description="Transaction description or memo")
    merchant: Optional[str] = Field(None, description="Merchant name if available")
    category: Optional[str] = Field(None, description="Spending category")
    amount: float = Field(..., description="Positive for outflow (debit), negative for inflow (credit)")
    type: Optional[str] = Field(None, description="debit | credit")

class AnalysisRequest(BaseModel):
    profile: FinancialProfile
    transactions: List[Transaction] = Field(default_factory=list)

class Alert(BaseModel):
    user_email: str
    alert_type: str
    severity: str
    message: str
    data: Optional[dict] = None

class AnalysisResult(BaseModel):
    score: int
    summary: str
    alerts: List[Alert]
    stats: Dict[str, float]
