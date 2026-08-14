from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.user import User
from app.schemas import AuthResponse, LoginRequest, SignupRequest, UserResponse
from app.services.auth import authenticate, create_access_token, create_user, get_user_by_email

router = APIRouter(prefix="/auth")


def _auth_response(user: User) -> AuthResponse:
    return AuthResponse(access_token=create_access_token(user), user=UserResponse.model_validate(user))


@router.post("/signup", response_model=AuthResponse, status_code=201)
def signup(body: SignupRequest, db: Session = Depends(get_db)):
    if get_user_by_email(db, body.email):
        raise HTTPException(status_code=409, detail="An account with that email already exists")

    try:
        user = create_user(
            db,
            email=body.email,
            password=body.password,
            name=body.name,
            business_name=body.business_name,
            wallet_address=body.wallet_address,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    return _auth_response(user)


@router.post("/login", response_model=AuthResponse)
def login(body: LoginRequest, db: Session = Depends(get_db)):
    user = authenticate(db, body.email, body.password)
    if user is None:
        # Deliberately not "no such account" vs "wrong password" — that
        # difference tells an attacker which emails are registered.
        raise HTTPException(status_code=401, detail="Email or password is incorrect")
    return _auth_response(user)


@router.get("/me", response_model=UserResponse)
def me(user: User = Depends(get_current_user)):
    return user
