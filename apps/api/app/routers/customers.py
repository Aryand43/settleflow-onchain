import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.database import get_db
from app.deps import get_current_user
from app.models.customer import Customer
from app.models.user import User
from app.schemas import CustomerCreate, CustomerImportResult, CustomerResponse

router = APIRouter(prefix="/customers")

# Accepted CSV headers, lowercased. Anything else in the file is ignored rather
# than rejected — exports from other invoicing tools carry columns we don't want.
COLUMN_ALIASES = {
    "name": "name",
    "customer": "name",
    "customer name": "name",
    "full name": "name",
    "contact": "name",
    "email": "email",
    "email address": "email",
    "e-mail": "email",
    "company": "company",
    "organisation": "company",
    "organization": "company",
    "business": "company",
    "wallet": "wallet_address",
    "wallet address": "wallet_address",
    "address": "wallet_address",
}

MAX_IMPORT_ROWS = 500


@router.get("", response_model=list[CustomerResponse])
def list_customers(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return (
        db.query(Customer)
        .filter(Customer.owner_id == user.id)
        .order_by(Customer.name)
        .all()
    )


@router.post("", response_model=CustomerResponse, status_code=201)
def create_customer(
    data: CustomerCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    email = str(data.email).strip().lower()
    existing = (
        db.query(Customer)
        .filter(Customer.owner_id == user.id, Customer.email == email)
        .first()
    )
    if existing:
        raise HTTPException(
            status_code=409, detail=f"{existing.name} is already in your directory with that email"
        )

    customer = Customer(
        owner_id=user.id,
        name=data.name.strip(),
        email=email,
        wallet_address=(data.wallet_address or "").strip() or None,
        company=(data.company or "").strip() or None,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=204)
def delete_customer(
    customer_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.owner_id == user.id)
        .first()
    )
    if customer is None:
        raise HTTPException(status_code=404, detail="Customer not found")
    if customer.invoices:
        raise HTTPException(
            status_code=409,
            detail=f"{customer.name} has {len(customer.invoices)} invoice(s) and can't be removed",
        )
    db.delete(customer)
    db.commit()


@router.post("/import", response_model=CustomerImportResult)
async def import_customers(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Bulk-adds customers from a CSV.

    Deliberately partial: valid rows are imported even when others fail, and
    every rejected row is reported with its line number. A spreadsheet with one
    bad email shouldn't cost you the other ninety-nine rows.
    """
    raw = await file.read()
    if not raw.strip():
        raise HTTPException(status_code=400, detail="That file is empty")

    try:
        text = raw.decode("utf-8-sig")
    except UnicodeDecodeError:
        # Excel on Windows still exports cp1252 by default.
        try:
            text = raw.decode("cp1252")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400, detail="Couldn't read that file — save it as UTF-8 CSV"
            )

    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="That file has no header row")

    mapping = {}
    for raw_header in reader.fieldnames:
        key = COLUMN_ALIASES.get((raw_header or "").strip().lower())
        if key and key not in mapping.values():
            mapping[raw_header] = key

    if "name" not in mapping.values() or "email" not in mapping.values():
        raise HTTPException(
            status_code=400,
            detail="CSV needs a name column and an email column. Found: "
            + ", ".join(h for h in reader.fieldnames if h),
        )

    existing_emails = {
        email.lower()
        for (email,) in db.query(Customer.email).filter(Customer.owner_id == user.id).all()
    }

    imported: list[Customer] = []
    errors: list[str] = []
    skipped = 0
    seen_in_file: set[str] = set()

    for line_number, row in enumerate(reader, start=2):
        if line_number - 1 > MAX_IMPORT_ROWS:
            errors.append(f"Stopped at {MAX_IMPORT_ROWS} rows — split the file and import again")
            break

        values = {field: (row.get(header) or "").strip() for header, field in mapping.items()}
        if not any(values.values()):
            continue  # blank line, not an error

        try:
            parsed = CustomerCreate(
                name=values.get("name", ""),
                email=values.get("email", ""),
                company=values.get("company") or None,
                wallet_address=values.get("wallet_address") or None,
            )
        except ValidationError:
            label = values.get("name") or values.get("email") or "row"
            errors.append(f"Line {line_number}: {label} — needs a name and a valid email")
            skipped += 1
            continue

        email = str(parsed.email).lower()
        if email in existing_emails or email in seen_in_file:
            skipped += 1
            continue

        seen_in_file.add(email)
        imported.append(
            Customer(
                owner_id=user.id,
                name=parsed.name.strip(),
                email=email,
                company=(parsed.company or "").strip() or None,
                wallet_address=(parsed.wallet_address or "").strip() or None,
            )
        )

    if imported:
        db.add_all(imported)
        db.commit()
        for customer in imported:
            db.refresh(customer)

    return CustomerImportResult(
        imported=len(imported),
        skipped=skipped,
        customers=[CustomerResponse.model_validate(c) for c in imported],
        errors=errors,
    )
