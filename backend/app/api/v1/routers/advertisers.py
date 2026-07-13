from datetime import date, datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field, field_validator
from sqlalchemy.orm import Session

from app.dependencies import require_roles
from app.infrastructure.db.session import get_db
from app.models import Advertiser, AuditLog, User

router = APIRouter(prefix="/advertisers", tags=["Advertisers"])

class AdvertiserCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    contact_email: EmailStr | None = None
    contact_phone: str | None = Field(default=None, max_length=50)
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    is_active: bool = True

    @field_validator("name")
    @classmethod
    def normalize_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Advertiser name is required")
        return value

    @field_validator("contact_phone")
    @classmethod
    def normalize_phone(cls, value: str | None) -> str | None:
        if value is None or value.strip() == "":
            return None
        return value.strip()

    @field_validator("contract_end_date")
    @classmethod
    def validate_contract_dates(cls, end_date: date | None, info):
        start_date = info.data.get("contract_start_date")
        if start_date and end_date and end_date < start_date:
            raise ValueError("contract_end_date cannot be before contract_start_date")
        return end_date

class AdvertiserResponse(BaseModel):
    id: int
    name: str
    contact_email: EmailStr | None = None
    contact_phone: str | None = None
    contract_start_date: date | None = None
    contract_end_date: date | None = None
    is_active: bool
    is_archived: bool

    class Config:
        from_attributes = True

def _advertiser_to_response(advertiser: Advertiser) -> AdvertiserResponse:
    return AdvertiserResponse(
        id=advertiser.id,
        name=advertiser.name,
        contact_email=advertiser.contact_email,
        contact_phone=advertiser.contact_phone,
        contract_start_date=advertiser.contract_start_date,
        contract_end_date=advertiser.contract_end_date,
        is_active=advertiser.is_active,
        is_archived=advertiser.is_archived,
    )

@router.post("", response_model=AdvertiserResponse, status_code=status.HTTP_201_CREATED)
def create_advertiser(
    payload: AdvertiserCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    existing = db.query(Advertiser).filter(Advertiser.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Advertiser already exists")

    advertiser = Advertiser(
        name=payload.name,
        contact_email=str(payload.contact_email) if payload.contact_email else None,
        contact_phone=payload.contact_phone,
        contract_start_date=payload.contract_start_date,
        contract_end_date=payload.contract_end_date,
        is_active=payload.is_active,
        is_archived=False,
    )

    db.add(advertiser)
    db.flush()
    db.add(
        AuditLog(
            user_id=current_user.id,
            action="CREATE_ADVERTISER",
            entity_type="advertiser",
            entity_id=advertiser.id,
            details=f"Created advertiser {advertiser.name}",
        )
    )

    db.commit()
    db.refresh(advertiser)
    return _advertiser_to_response(advertiser)

@router.get("", response_model=list[AdvertiserResponse])
def list_advertisers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin", "client", "operator")),
):
    advertisers = (
        db.query(Advertiser)
        .filter(Advertiser.is_archived.is_(False))
        .order_by(Advertiser.created_at.desc())
        .all()
    )
    return [_advertiser_to_response(item) for item in advertisers]

@router.delete("/{advertiser_id}", status_code=status.HTTP_204_NO_CONTENT)
def archive_advertiser(
    advertiser_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles("admin")),
):
    advertiser = db.query(Advertiser).filter(Advertiser.id == advertiser_id).first()
    if not advertiser:
        raise HTTPException(status_code=404, detail="Advertiser not found")

    advertiser.is_archived = True
    advertiser.is_active = False
    advertiser.archived_at = datetime.now(timezone.utc)

    db.add(
        AuditLog(
            user_id=current_user.id,
            action="ARCHIVE_ADVERTISER",
            entity_type="advertiser",
            entity_id=advertiser.id,
            details=f"Archived advertiser {advertiser.name} without deleting historical reports",
        )
    )

    db.commit()
    return None