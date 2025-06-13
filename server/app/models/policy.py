"""Database models for policies."""

from typing import List
from sqlalchemy import String, Float, ForeignKey, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

class PolicyCategory(Base):
    """Model for policy categories."""
    
    __tablename__ = "policy_categories"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    description: Mapped[str] = mapped_column(String(500))
    
    # Relationships
    policies: Mapped[List["Policy"]] = relationship(back_populates="category")

class Policy(Base):
    """Model for individual policies."""
    
    __tablename__ = "policies"
    
    id: Mapped[int] = mapped_column(primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("policy_categories.id"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str] = mapped_column(String(1000))
    extra_metadata: Mapped[dict] = mapped_column(JSON, nullable=True)
    
    # Relationships
    category: Mapped["PolicyCategory"] = relationship(back_populates="policies") 