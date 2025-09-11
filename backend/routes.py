from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from . import models, database
from pydantic import BaseModel
from typing import List

router = APIRouter(prefix="/api")

# Pydantic schemas
class ExpenseCreate(BaseModel):
    amount: float
    category: str = None
    note: str = None

class ExpenseOut(ExpenseCreate):
    id: int
    user_id: int

    class Config:
        orm_mode = True

@router.get("/expenses", response_model=List[ExpenseOut])
def list_expenses(db: Session = Depends(database.get_db)):
    return db.query(models.Expense).all()

@router.post("/expenses", response_model=ExpenseOut)
def create_expense(expense: ExpenseCreate, db: Session = Depends(database.get_db)):
    db_exp = models.Expense(**expense.dict(), user_id=1)
    db.add(db_exp)
    db.commit()
    db.refresh(db_exp)
    return db_exp
