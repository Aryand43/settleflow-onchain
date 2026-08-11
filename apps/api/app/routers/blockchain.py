from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import verify_api_key
from app.services.blockchain import scan_blockchain_events

router = APIRouter(prefix="/blockchain", dependencies=[Depends(verify_api_key)])


@router.post("/scan")
def scan_blockchain(db: Session = Depends(get_db)):
    return scan_blockchain_events(db)
