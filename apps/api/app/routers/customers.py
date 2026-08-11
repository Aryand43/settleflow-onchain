from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_api_key
from app.repositories.customer import get_customer_repository
from app.schemas import CustomerCreate, CustomerResponse

router = APIRouter(prefix="/customers", dependencies=[Depends(verify_api_key)])


@router.get("", response_model=list[CustomerResponse])
def list_customers(db: Session = Depends(get_db)):
    repo = get_customer_repository()
    return repo.list_customers(db)


@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(data: CustomerCreate, db: Session = Depends(get_db)):
    repo = get_customer_repository()
    return repo.create(db, data)
