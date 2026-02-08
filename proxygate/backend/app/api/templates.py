from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
import json

from app.api.deps import DBSession, CurrentAdmin
from app.models import DomainTemplate
from app.schemas.domain import (
    DomainTemplateCreate, DomainTemplateUpdate, DomainTemplateResponse
)


router = APIRouter()


@router.get("", response_model=list[DomainTemplateResponse])
async def list_templates(
    db: DBSession,
    admin: CurrentAdmin
):
    """List all domain templates."""
    result = await db.execute(
        select(DomainTemplate).order_by(DomainTemplate.name)
    )
    templates = result.scalars().all()

    return [
        DomainTemplateResponse(
            id=t.id,
            name=t.name,
            description=t.description,
            icon=t.icon,
            domains=json.loads(t.domains_json),
            is_active=t.is_active,
            is_public=t.is_public,
            created_at=t.created_at
        )
        for t in templates
    ]


@router.post("", response_model=DomainTemplateResponse, status_code=status.HTTP_201_CREATED)
async def create_template(
    request: DomainTemplateCreate,
    db: DBSession,
    admin: CurrentAdmin
):
    """Create a new domain template."""
    # Check if name exists
    result = await db.execute(
        select(DomainTemplate).where(DomainTemplate.name == request.name)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=400, detail="Template with this name already exists")

    template = DomainTemplate(
        name=request.name,
        description=request.description,
        icon=request.icon,
        domains_json=json.dumps(request.domains),
        is_active=True,
        is_public=request.is_public
    )

    db.add(template)
    await db.commit()
    await db.refresh(template)

    return DomainTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        icon=template.icon,
        domains=request.domains,
        is_active=template.is_active,
        is_public=template.is_public,
        created_at=template.created_at
    )


@router.get("/{template_id}", response_model=DomainTemplateResponse)
async def get_template(
    template_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Get a domain template by ID."""
    result = await db.execute(
        select(DomainTemplate).where(DomainTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    return DomainTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        icon=template.icon,
        domains=json.loads(template.domains_json),
        is_active=template.is_active,
        is_public=template.is_public,
        created_at=template.created_at
    )


@router.put("/{template_id}", response_model=DomainTemplateResponse)
async def update_template(
    template_id: int,
    request: DomainTemplateUpdate,
    db: DBSession,
    admin: CurrentAdmin
):
    """Update a domain template."""
    result = await db.execute(
        select(DomainTemplate).where(DomainTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    update_data = request.model_dump(exclude_unset=True)

    if "domains" in update_data:
        update_data["domains_json"] = json.dumps(update_data.pop("domains"))

    for field, value in update_data.items():
        setattr(template, field, value)

    await db.commit()
    await db.refresh(template)

    return DomainTemplateResponse(
        id=template.id,
        name=template.name,
        description=template.description,
        icon=template.icon,
        domains=json.loads(template.domains_json),
        is_active=template.is_active,
        is_public=template.is_public,
        created_at=template.created_at
    )


@router.delete("/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    db: DBSession,
    admin: CurrentAdmin
):
    """Delete a domain template."""
    result = await db.execute(
        select(DomainTemplate).where(DomainTemplate.id == template_id)
    )
    template = result.scalar_one_or_none()

    if template is None:
        raise HTTPException(status_code=404, detail="Template not found")

    await db.delete(template)
    await db.commit()
