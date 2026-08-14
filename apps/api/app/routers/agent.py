from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.services.reminders import run_collections_agent

router = APIRouter(prefix="/agent")


@router.post("/run-collections")
def run_collections(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return run_collections_agent(db, user.id)
