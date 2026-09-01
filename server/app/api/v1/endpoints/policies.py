"""Versioned policy administration endpoints."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.database import get_db
from app.integrations.chroma import ChromaIndex
from app.integrations.openai_gateway import MissingAIConfigurationError, OpenAIGateway
from app.models.entities import IndexStatus, Policy
from app.repositories import policies as repository
from app.schemas.policies import (
    PolicyCreate,
    PolicyDetail,
    PolicyDraftUpdate,
    PolicySummary,
    PolicyTestRequest,
    PolicyTestResponse,
    PolicyVersionRead,
    PublishPolicyResponse,
)
from app.services.compliance_checker import policy_payload, validate_model_output

router = APIRouter()


def policy_detail(policy: Policy) -> PolicyDetail:
    current = max(policy.versions, key=lambda version: version.version)
    return PolicyDetail(
        id=policy.id,
        key=policy.key,
        title=current.title,
        category=current.category,
        versions=[PolicyVersionRead.model_validate(version) for version in policy.versions],
    )


def policy_summary(policy: Policy) -> PolicySummary:
    current = max(policy.versions, key=lambda version: version.version)
    return PolicySummary(
        id=policy.id,
        key=policy.key,
        title=current.title,
        category=current.category,
        current_version=current.version,
        status=current.status,
        index_status=current.index_status,
        jurisdictions=current.jurisdictions,
        updated_at=current.updated_at,
    )


def handle_repository_error(error: Exception) -> HTTPException:
    if isinstance(error, repository.PolicyNotFoundError):
        return HTTPException(status_code=404, detail="Policy not found")
    return HTTPException(status_code=409, detail=str(error))


@router.get("", response_model=list[PolicySummary])
async def list_policies(db: AsyncSession = Depends(get_db)) -> list[PolicySummary]:
    return [policy_summary(policy) for policy in await repository.list_policies(db)]


@router.post("", response_model=PolicyDetail, status_code=status.HTTP_201_CREATED)
async def create_policy(request: PolicyCreate, db: AsyncSession = Depends(get_db)) -> PolicyDetail:
    try:
        return policy_detail(await repository.create_policy(db, request))
    except (repository.PolicyStateError, repository.PolicyNotFoundError) as error:
        raise handle_repository_error(error) from error


@router.get("/{policy_id}", response_model=PolicyDetail)
async def get_policy(policy_id: str, db: AsyncSession = Depends(get_db)) -> PolicyDetail:
    try:
        return policy_detail(await repository.get_policy(db, policy_id))
    except repository.PolicyNotFoundError as error:
        raise handle_repository_error(error) from error


@router.patch("/{policy_id}/versions/{version_id}", response_model=PolicyDetail)
async def update_policy_draft(
    policy_id: str,
    version_id: str,
    request: PolicyDraftUpdate,
    db: AsyncSession = Depends(get_db),
) -> PolicyDetail:
    try:
        return policy_detail(await repository.update_draft(db, policy_id, version_id, request))
    except (repository.PolicyStateError, repository.PolicyNotFoundError) as error:
        raise handle_repository_error(error) from error


@router.post("/{policy_id}/versions", response_model=PolicyDetail, status_code=201)
async def create_policy_version(policy_id: str, db: AsyncSession = Depends(get_db)) -> PolicyDetail:
    try:
        return policy_detail(await repository.create_draft_version(db, policy_id))
    except (repository.PolicyStateError, repository.PolicyNotFoundError) as error:
        raise handle_repository_error(error) from error


@router.post("/{policy_id}/versions/{version_id}/test", response_model=PolicyTestResponse)
async def test_policy_version(
    policy_id: str,
    version_id: str,
    request: PolicyTestRequest,
    db: AsyncSession = Depends(get_db),
) -> PolicyTestResponse:
    try:
        policy = await repository.get_policy(db, policy_id)
    except repository.PolicyNotFoundError as error:
        raise handle_repository_error(error) from error
    version = next((item for item in policy.versions if item.id == version_id), None)
    if not version:
        raise HTTPException(status_code=404, detail="Policy version not found")
    try:
        ai = OpenAIGateway(get_settings())
        result = await ai.check_compliance(
            posting=request.posting_text, policies=[policy_payload(version)]
        )
        validate_model_output(request.posting_text, [version], result.output)
    except MissingAIConfigurationError as error:
        raise HTTPException(status_code=503, detail=str(error)) from error
    assessment = result.output.assessments[0]
    return PolicyTestResponse(
        policy_key=policy.key,
        status=assessment.status.value,
        evidence_text=assessment.evidence_text,
        reason=assessment.reason,
        confidence=assessment.confidence,
    )


@router.post("/{policy_id}/versions/{version_id}/publish", response_model=PublishPolicyResponse)
async def publish_policy_version(
    policy_id: str, version_id: str, db: AsyncSession = Depends(get_db)
) -> PublishPolicyResponse:
    try:
        policy, snapshot = await repository.publish_policy_version(db, policy_id, version_id)
    except (repository.PolicyStateError, repository.PolicyNotFoundError) as error:
        raise handle_repository_error(error) from error

    version = next(item for item in policy.versions if item.id == version_id)
    try:
        ai = OpenAIGateway(get_settings())
        await ChromaIndex(get_settings(), ai).index_policy(version)
        version.index_status = IndexStatus.INDEXED.value
    except Exception:
        version.index_status = IndexStatus.FAILED.value
    await db.commit()
    policy = await repository.get_policy(db, policy_id)
    return PublishPolicyResponse(
        policy=policy_detail(policy),
        snapshot_version=snapshot.version,
        index_status=version.index_status,
    )
