from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_api_key
from app.services.reminders import run_collections_agent

router = APIRouter(prefix="/agent", dependencies=[Depends(verify_api_key)])


@router.post("/run-collections")
def run_collections(db: Session = Depends(get_db)):
    return run_collections_agent(db)
