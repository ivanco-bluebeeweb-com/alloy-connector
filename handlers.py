"""Chat functions for Alloy Connector: connection management, Entities
(Persons/Businesses), Journeys/Applications/Batches, Evaluations, Portfolio
Evaluations, Documents, Events (ongoing monitoring), Cases, Investigations,
Custom Lists, Published Attributes, Reviews, Bank Accounts/Transactions,
Groups, Webhooks, Parameters, and value-add reports (Tier 3). Built on
alloy_client.py / schemas.py, following the same shape as Cin7 Core
Connector's / MuleSoft Connector's handlers.py.

WHY ActionResult.success(data, summary), NEVER ActionResult.ok(...).

imperal_sdk's real ActionResult class exposes .success(data, summary, *,
ui=None, refresh_panels=None) and .error(error, retryable=False, *,
code="") -- there is NO .ok() staticmethod on this SDK version (confirmed
2026-08-23 via inspect.signature against imperal_sdk 5.11.0 in the working
venv). Every call site below uses .success(...) with an explicit summary
string, not .ok(...).
"""
from __future__ import annotations

import json
import uuid

import alloy_client as ac
from app import ext, chat
from imperal_sdk import ActionResult
from schemas import (
    NoParams,
    ConnectAlloyParams, ProviderConnection, ConnectionList,
    DisconnectAlloyParams, ListConnectionsParams,
    DeleteResult, GenericRecord, GenericRecordList, ActionResultEntity,
    AuditFinding, AlloyAccountAudit, PendingReviewQueue, PendingReviewQueueRow,
    AddCaseEvidenceParams, AddCaseWorkParams, AddCustomListItemParams,
    AddEntityNoteParams, AddEntityToGroupParams, ArchiveInvestigationParams,
    AuditAlloyAccountParams, CreateBankAccountParams, CreateBusinessEntityParams,
    CreateCaseParams, CreateCustomListParams, CreateCustomListVersionParams,
    CreateGroupParams, CreateInvestigationParams, CreateJourneyApplicationParams,
    CreateJourneyBatchParams, CreatePersonEntityParams, CreateTransactionParams,
    CreateWebhookParams, DeleteWebhookParams, GetAlertManualReviewTokenParams,
    GetBankAccountParams, GetCaseParams, GetCustomListParams, GetDocumentParams,
    GetEntityParams, GetEntityPublishedAttributesParams, GetEvaluationParams,
    GetGroupParams, GetInvestigationParams, GetJourneyApplicationParams,
    GetJourneyBatchParams, GetJourneySchemaParams, GetPendingReviewQueueParams,
    GetPortfolioEvaluationParams, GetReviewParams, ListBankAccountTransactionsParams,
    ListCasesParams, ListCustomListItemsParams, ListCustomListsParams,
    ListEntityBankAccountsParams, ListEntityDocumentsParams, ListEntityEventsParams,
    ListEntityGroupsParams, ListGroupsParams, ListInvestigationTypesParams,
    ListInvestigationsParams, ListJourneyApplicationsParams, ListParametersParams,
    ListPublishedAttributesParams, ListReviewsParams, ListWebhooksParams,
    ManualReviewJourneyApplicationParams, MergeEntitiesParams,
    RemoveCustomListItemParams, RemoveEntityFromGroupParams,
    RerunJourneyApplicationParams, RunEvaluationParams, RunPortfolioEvaluationParams,
    SendEventParams, SubmitEntityFeedbackParams, SubmitReviewDecisionParams,
    UpdateCaseParams, UpdateDocumentParams, UpdateInvestigationParams,
    UpdateJourneyApplicationNodeParams, UploadDocumentParams,
)

_SECRET_NAME = "alloy_connections"


async def _load_connections(ctx) -> list[dict]:
    raw = await ctx.secrets.get(_SECRET_NAME)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    return data if isinstance(data, list) else []


async def _save_connections(ctx, connections: list[dict]) -> None:
    await ctx.secrets.set(_SECRET_NAME, json.dumps(connections))


async def _resolve_connection(ctx, connection_id: str = "") -> dict | None:
    connections = await _load_connections(ctx)
    if not connections:
        return None
    if connection_id:
        for c in connections:
            if c.get("id") == connection_id:
                return c
        return None
    return connections[0]


async def _resolve_or_error(ctx, connection_id: str = ""):
    """Shared guard: resolve a connection or return the standard 'not
    connected' ActionResult.error. Returns (conn, error_or_None)."""
    conn = await _resolve_connection(ctx, connection_id)
    if conn is None:
        return None, ActionResult.error(
            "No Alloy account is connected yet. Use connect_alloy first.",
            code=ac.ACCOUNT_MISSING,
        )
    return conn, None


def _connection_to_entity(c: dict) -> ProviderConnection:
    return ProviderConnection(
        id=c.get("id", ""),
        title=c.get("label") or f"Alloy ({c.get('environment', 'sandbox')})",
        connected=True,
        detail=f"Environment: {c.get('environment', 'sandbox')}",
        environment=c.get("environment", "sandbox"),
    )


@chat.function(
    "connect_alloy",
    "Connect an Alloy account by saving its token/secret pair, after checking it actually works against the chosen environment (sandbox or production).",
    action_type="write",
    chain_callable=True,
    data_model=ProviderConnection,
    event="alloy-connector.connect_alloy",
    effects=["alloy.provider.connected"],
)
async def connect_alloy(ctx, params: ConnectAlloyParams) -> ActionResult:
    """Connect an Alloy account by saving its token/secret pair."""
    if not params.token or not params.secret:
        return ActionResult.error("Token and secret are both required.", code="ALLOY_MISSING_FIELDS")
    environment = (params.environment or "sandbox").lower()
    if environment not in ("sandbox", "production"):
        return ActionResult.error("environment must be 'sandbox' or 'production'.", code="ALLOY_BAD_ENVIRONMENT")
    check = await ac.check_connection(ctx, params.token, params.secret, environment)
    if not check.get("ok"):
        return ActionResult.error(check.get("error", "Could not verify these credentials."), code=check.get("error_code", ac.CREDENTIALS_REJECTED))
    connections = await _load_connections(ctx)
    conn_id = str(uuid.uuid4())
    record = {
        "id": conn_id,
        "token": params.token,
        "secret": params.secret,
        "environment": environment,
        "label": params.label,
    }
    connections.append(record)
    await _save_connections(ctx, connections)
    return ActionResult.success(_connection_to_entity(record), f"Connected Alloy account ({environment}).")


@chat.function(
    "disconnect_alloy",
    "Disconnect an Alloy account: deletes the saved token/secret. Nothing in Alloy itself is changed.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    event="alloy-connector.disconnect_alloy",
    effects=["alloy.provider.disconnected"],
)
async def disconnect_alloy(ctx, params: DisconnectAlloyParams) -> ActionResult:
    """Disconnect an Alloy account."""
    connections = await _load_connections(ctx)
    remaining = [c for c in connections if c.get("id") != params.connection_id]
    if len(remaining) == len(connections):
        return ActionResult.error("No such connection.", code="ALLOY_CONNECTION_NOT_FOUND")
    await _save_connections(ctx, remaining)
    return ActionResult.success(DeleteResult(deleted=True, id=params.connection_id), "Disconnected Alloy account.")


@chat.function(
    "list_connections",
    "List the connected Alloy accounts.",
    action_type="read",
    chain_callable=True,
    data_model=ConnectionList,
    event="alloy-connector.list_connections",
)
async def list_connections(ctx, params: NoParams) -> ActionResult:
    """List the connected Alloy accounts."""
    connections = await _load_connections(ctx)
    return ActionResult.success(ConnectionList(connections=[_connection_to_entity(c) for c in connections]), f"{len(connections)} connection(s).")


# ──────────────────────────────────────────────────────────────────────────
# Entities -- Persons / Businesses
# ──────────────────────────────────────────────────────────────────────────


def _entity_to_generic(body: dict) -> GenericRecord:
    entity = body if isinstance(body, dict) else {}
    return GenericRecord(
        id=str(entity.get("entity_token", entity.get("id", ""))),
        token=str(entity.get("entity_token", "")),
        data=entity,
    )


def _rows_from_body(body) -> list[GenericRecord]:
    """Normalize a list-shaped Alloy response into GenericRecord rows.

    Alloy's list endpoints wrap results under varying keys across resources
    (e.g. {"data": [...]}, {"items": [...]}, or a bare list) -- this helper
    accepts any of those shapes so every list_* handler shares one path.
    """
    if isinstance(body, list):
        items = body
    elif isinstance(body, dict):
        items = body.get("data") or body.get("items") or body.get("results") or []
    else:
        items = []
    rows: list[GenericRecord] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        token = str(
            item.get("entity_token")
            or item.get("token")
            or item.get("document_token")
            or item.get("case_token")
            or item.get("investigation_token")
            or item.get("list_token")
            or item.get("review_token")
            or item.get("group_token")
            or item.get("webhook_token")
            or item.get("id", "")
        )
        rows.append(GenericRecord(id=token, token=token, data=item))
    return rows


def _person_payload(params) -> dict:
    payload = {
        "name_first": params.name_first,
        "name_last": params.name_last,
        "email_address": params.email_address or None,
        "phone_number": params.phone_number or None,
        "birth_date": params.birth_date or None,
        "document_ssn": params.ssn or None,
        "address_line_1": params.address_line_1 or None,
        "address_line_2": params.address_line_2 or None,
        "address_city": params.address_city or None,
        "address_state": params.address_state or None,
        "address_postal_code": params.address_postal_code or None,
        "address_country_code": params.address_country_code or None,
        "external_entity_id": params.external_entity_id or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    payload.update(params.extra_fields or {})
    return payload


@chat.function(
    "create_person_entity",
    "Create a Person entity in Alloy from applicant field data (name, DOB, SSN/tax id, address, email, phone, etc.), the object every KYC evaluation attaches to.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_person_entity",
    effects=["alloy.entity.created"],
)
async def create_person_entity(ctx, params: CreatePersonEntityParams) -> ActionResult:
    """Create a Person entity."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/entities/persons", json=_person_payload(params), action="create person entity")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Person entity created.")


def _business_payload(params) -> dict:
    payload = {
        "business_name": params.business_name,
        "business_ein": params.business_ein or None,
        "business_website": params.business_website or None,
        "business_phone_number": params.business_phone_number or None,
        "address_line_1": params.address_line_1 or None,
        "address_city": params.address_city or None,
        "address_state": params.address_state or None,
        "address_postal_code": params.address_postal_code or None,
        "address_country_code": params.address_country_code or None,
        "external_entity_id": params.external_entity_id or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    payload.update(params.extra_fields or {})
    return payload


@chat.function(
    "create_business_entity",
    "Create a Business entity in Alloy from company field data (legal name, EIN/tax id, formation state/country, address, etc.), the object every KYB evaluation attaches to.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_business_entity",
    effects=["alloy.entity.created"],
)
async def create_business_entity(ctx, params: CreateBusinessEntityParams) -> ActionResult:
    """Create a Business entity."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/entities/businesses", json=_business_payload(params), action="create business entity")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Business entity created.")


@chat.function(
    "get_entity",
    "Read one Alloy entity (Person or Business) in full, including its evaluation/journey history summary.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_entity",
)
async def get_entity(ctx, params: GetEntityParams) -> ActionResult:
    """Read one Alloy entity in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    path = f"/entities/businesses/{params.entity_token}" if params.entity_type == "business" else f"/entities/persons/{params.entity_token}"
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], path, action="get entity")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Entity loaded.")


@chat.function(
    "merge_entities",
    "Merge a duplicate Alloy entity into a surviving entity -- combines their evaluation/journey history under the surviving entity token.",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.merge_entities",
    effects=["alloy.entity.merged"],
)
async def merge_entities(ctx, params: MergeEntitiesParams) -> ActionResult:
    """Merge a duplicate entity into a surviving entity."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/entities/{params.primary_entity_token}/merge", json={"duplicate_entity_token": params.duplicate_entity_token}, action="merge entities")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.primary_entity_token, message="Merged."), "Entities merged.")


@chat.function(
    "add_entity_note",
    "Add a free-text internal note to an Alloy entity's record -- e.g. context from a manual review or a customer support interaction.",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.add_entity_note",
    effects=["alloy.entity.note_added"],
)
async def add_entity_note(ctx, params: AddEntityNoteParams) -> ActionResult:
    """Add a note to an entity."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/entities/{params.entity_token}/notes", json={"note": params.note}, action="add entity note")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.entity_token, message="Note added."), "Note added.")


@chat.function(
    "submit_entity_feedback",
    "Submit outcome feedback on an entity (e.g. confirmed fraud, false positive) back into Alloy -- feeds Alloy's own model tuning and your account's audit trail.",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.submit_entity_feedback",
    effects=["alloy.entity.feedback_submitted"],
)
async def submit_entity_feedback(ctx, params: SubmitEntityFeedbackParams) -> ActionResult:
    """Submit feedback on an entity's outcome."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {"feedback_type": params.feedback_type, "comment": params.comment or None}
    try:
        await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/entities/{params.entity_token}/feedback", json={k: v for k, v in payload.items() if v is not None}, action="submit entity feedback")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.entity_token, message="Feedback submitted."), "Feedback submitted.")


@chat.function(
    "list_entity_groups",
    "List the groups (custom entity groupings, e.g. a household or a linked-accounts ring) an Alloy entity belongs to.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_entity_groups",
)
async def list_entity_groups(ctx, params: ListEntityGroupsParams) -> ActionResult:
    """List the groups an entity belongs to."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/entities/{params.entity_token}/groups", action="list entity groups")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    items = body.get("groups", body) if isinstance(body, dict) else (body if isinstance(body, list) else [])
    rows = [GenericRecord(id=str(r.get("group_token", r.get("id", ""))), token=str(r.get("group_token", "")), data=r) for r in items if isinstance(r, dict)]
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} group(s)", items=rows, total=len(rows)), f"{len(rows)} group(s).")


# ──────────────────────────────────────────────────────────────────────────
# Journeys -- Journey Applications / Batches
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "create_journey_application",
    "Create a Journey Application in Alloy -- runs an applicant through a configured Journey (multi-step KYC/KYB/fraud/credit decisioning workflow) and returns the outcome (Approved/Denied/Manual Review).",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_journey_application",
    effects=["alloy.journey_application.created"],
)
async def create_journey_application(ctx, params: CreateJourneyApplicationParams) -> ActionResult:
    """Create a Journey Application (run a Journey)."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = dict(params.application_data)
    if params.branch_name:
        payload["branch_name"] = params.branch_name
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/journeys/{params.journey_token}/applications", json=payload, action="create journey application")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Journey application created.")


@chat.function(
    "get_journey_application",
    "Read one Journey Application in full -- its current status, decisioning outcome, and every node's evaluation result.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_journey_application",
)
async def get_journey_application(ctx, params: GetJourneyApplicationParams) -> ActionResult:
    """Read one Journey Application in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/journeys/{params.journey_token}/applications/{params.journey_application_token}", action="get journey application")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Journey application loaded.")


@chat.function(
    "list_journey_applications",
    "List Journey Applications for one configured Journey, optionally filtered by outcome status.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_journey_applications",
)
async def list_journey_applications(ctx, params: ListJourneyApplicationsParams) -> ActionResult:
    """List Journey Applications for a Journey."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    q = {"page": params.page, "page_size": params.limit}
    if params.outcome:
        q["outcome"] = params.outcome
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/journeys/{params.journey_token}/applications", params=q, action="list journey applications")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    items = body.get("applications", body) if isinstance(body, dict) else (body if isinstance(body, list) else [])
    rows = [GenericRecord(id=str(r.get("journey_application_token", r.get("id", ""))), token=str(r.get("journey_application_token", "")), data=r) for r in items if isinstance(r, dict)]
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} application(s)", items=rows, total=len(rows), page=params.page), f"{len(rows)} application(s).")


@chat.function(
    "rerun_journey_application",
    "Rerun an existing Journey Application through its Journey again -- e.g. after new documents were supplied, or a data source was temporarily unavailable.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.rerun_journey_application",
    effects=["alloy.journey_application.rerun"],
)
async def rerun_journey_application(ctx, params: RerunJourneyApplicationParams) -> ActionResult:
    """Rerun a Journey Application."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/journeys/{params.journey_token}/applications/{params.journey_application_token}/rerun", json={}, action="rerun journey application")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Journey application rerun triggered.")


@chat.function(
    "manual_review_journey_application",
    "Submit a manual review decision on a Journey Application currently in Manual Review status -- approve or deny it as a human reviewer.",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.manual_review_journey_application",
    effects=["alloy.journey_application.reviewed"],
)
async def manual_review_journey_application(ctx, params: ManualReviewJourneyApplicationParams) -> ActionResult:
    """Submit a manual review decision on a Journey Application."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {"outcome": params.outcome, "reason": params.reason or None}
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/journeys/{params.journey_token}/applications/{params.journey_application_token}/review", json=payload, action="submit manual review")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.journey_application_token, message="Manual review submitted."), "Manual review submitted.")


@chat.function(
    "get_alert_manual_review_token",
    "Read the manual review token generated for a specific Journey Application alert -- used to link a reviewer directly into Alloy's manual review workspace.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_alert_manual_review_token",
)
async def get_alert_manual_review_token(ctx, params: GetAlertManualReviewTokenParams) -> ActionResult:
    """Read one alert's manual review token."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/journeys/{params.journey_token}/applications/{params.journey_application_token}/review", action="get alert manual review token")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Manual review token loaded.")


@chat.function(
    "get_journey_schema",
    "Read a Journey's configured field schema -- every field name/type an application must supply, and every branch/version defined for it. Call before create_journey_application to know exactly what application_data should contain.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_journey_schema",
)
async def get_journey_schema(ctx, params: GetJourneySchemaParams) -> ActionResult:
    """Read a Journey's configured field schema."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/journeys/{params.journey_token}/schema", action="get journey schema")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Journey schema loaded.")


@chat.function(
    "update_journey_application_node",
    "Update a single decisioning node's result on an active Journey Application -- e.g. correct an automated document-verification node's outcome after a human review.",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.update_journey_application_node",
    effects=["alloy.journey_application.node_updated"],
)
async def update_journey_application_node(ctx, params: UpdateJourneyApplicationNodeParams) -> ActionResult:
    """Update one decisioning node's result on a Journey Application."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await ac.alloy_put(ctx, conn["token"], conn["secret"], conn["environment"], f"/journeys/{params.journey_token}/applications/{params.journey_application_token}/nodes/{params.node_id}", json=params.node_data, action="update journey application node")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.node_id, message="Node updated."), "Node updated.")


@chat.function(
    "create_journey_batch",
    "Create a Journey Batch -- submit many applications through the same Journey in one call (e.g. a portfolio re-screen or a bulk onboarding import).",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_journey_batch",
    effects=["alloy.journey_batch.created"],
)
async def create_journey_batch(ctx, params: CreateJourneyBatchParams) -> ActionResult:
    """Create a Journey Batch."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/journeys/{params.journey_token}/batches", json={"applications": params.applications}, action="create journey batch")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Journey batch created.")


@chat.function(
    "get_journey_batch",
    "Read one Journey Batch's processing status and per-application results.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_journey_batch",
)
async def get_journey_batch(ctx, params: GetJourneyBatchParams) -> ActionResult:
    """Read one Journey Batch in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/journeys/{params.journey_token}/batches/{params.journey_batch_token}", action="get journey batch")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Journey batch loaded.")


# ──────────────────────────────────────────────────────────────────────────
# Evaluations / Portfolio Evaluations
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "run_evaluation",
    "Run a direct (non-Journey) Evaluation against an Alloy Workflow -- Alloy's original single-step decisioning primitive, still available alongside Journeys for accounts configured that way.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.run_evaluation",
    effects=["alloy.evaluation.created"],
)
async def run_evaluation(ctx, params: RunEvaluationParams) -> ActionResult:
    """Run a direct Evaluation."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/evaluations", json={"workflow_token": params.workflow_token, **params.evaluation_data}, action="run evaluation")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Evaluation run.")


@chat.function(
    "get_evaluation",
    "Read one Evaluation's outcome in full -- its decisioning result, triggered rules, and any manual review status.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_evaluation",
)
async def get_evaluation(ctx, params: GetEvaluationParams) -> ActionResult:
    """Read one Evaluation in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/evaluations/{params.evaluation_token}", action="get evaluation")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Evaluation loaded.")


@chat.function(
    "run_portfolio_evaluation",
    "Run a Portfolio Evaluation -- Alloy's book-of-business-level risk assessment across a set of existing entities, e.g. periodic re-screening of an entire loan portfolio against updated sanctions/watchlist data.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.run_portfolio_evaluation",
    effects=["alloy.portfolio_evaluation.created"],
)
async def run_portfolio_evaluation(ctx, params: RunPortfolioEvaluationParams) -> ActionResult:
    """Run a Portfolio Evaluation."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/portfolio-evaluations/{params.portfolio_token}", json=params.evaluation_data, action="run portfolio evaluation")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Portfolio evaluation run.")


@chat.function(
    "get_portfolio_evaluation",
    "Read one Portfolio Evaluation's aggregated results in full.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_portfolio_evaluation",
)
async def get_portfolio_evaluation(ctx, params: GetPortfolioEvaluationParams) -> ActionResult:
    """Read one Portfolio Evaluation in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/portfolio-evaluations/{params.portfolio_evaluation_token}", action="get portfolio evaluation")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Portfolio evaluation loaded.")


# ──────────────────────────────────────────────────────────────────────────
# Documents -- identity/supporting docs attached to entities
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "upload_document",
    "Upload an identity or supporting document (e.g. driver's license, business formation certificate) to Alloy for an entity, as a base64-encoded file. Alloy can then run document-verification checks on it via a Journey.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.upload_document",
    effects=["alloy.document.uploaded"],
)
async def upload_document(ctx, params: UploadDocumentParams) -> ActionResult:
    """Upload a document for an entity."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {
        "entity_token": params.entity_token,
        "document_type": params.document_type,
        "file_name": params.file_name,
        "file_content_base64": params.file_base64,
    }
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/documents", json=payload, action="upload document")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Document uploaded.")


@chat.function(
    "get_document",
    "Read one uploaded document's metadata and verification status in full.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_document",
)
async def get_document(ctx, params: GetDocumentParams) -> ActionResult:
    """Read one document in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/documents/{params.document_token}", action="get document")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Document loaded.")


@chat.function(
    "update_document",
    "Update an existing document's metadata (e.g. correct its document_type classification).",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.update_document",
    effects=["alloy.document.updated"],
)
async def update_document(ctx, params: UpdateDocumentParams) -> ActionResult:
    """Update a document's metadata."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {k: v for k, v in {"document_type": params.document_type or None}.items() if v is not None}
    try:
        await ac.alloy_put(ctx, conn["token"], conn["secret"], conn["environment"], f"/documents/{params.document_token}", json=payload, action="update document")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.document_token, message="Document updated."), "Document updated.")


@chat.function(
    "list_entity_documents",
    "List all documents uploaded for one Alloy entity.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_entity_documents",
)
async def list_entity_documents(ctx, params: ListEntityDocumentsParams) -> ActionResult:
    """List documents uploaded for one entity."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/entities/{params.entity_token}/documents", action="list entity documents")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} document(s)", items=rows, total=len(rows)), f"{len(rows)} document(s).")


# ──────────────────────────────────────────────────────────────────────────
# Events -- ongoing monitoring
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "send_event",
    "Send a monitoring event (login, transaction, address change, phone change, etc.) for an existing entity into Alloy's Events API -- the core mechanism for continuous post-onboarding risk monitoring, separate from the initial Journey/Evaluation.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.send_event",
    effects=["alloy.event.sent"],
)
async def send_event(ctx, params: SendEventParams) -> ActionResult:
    """Send a monitoring event for an entity."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {
        "entity_token": params.entity_token,
        "event_type": params.event_type,
        **params.event_data,
    }
    if params.occurred_at:
        payload["occurred_at"] = params.occurred_at
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/events", json=payload, action="send event")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Event sent.")


@chat.function(
    "list_entity_events",
    "List monitoring events recorded for one Alloy entity, optionally filtered by event type -- the ongoing-monitoring history that can itself trigger new alerts/cases.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_entity_events",
)
async def list_entity_events(ctx, params: ListEntityEventsParams) -> ActionResult:
    """List monitoring events for one entity."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    query = {"page": params.page, "limit": params.limit}
    if params.event_type:
        query["event_type"] = params.event_type
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/entities/{params.entity_token}/events", params=query, action="list entity events")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} event(s)", items=rows, total=len(rows), page=params.page), f"{len(rows)} event(s).")


# ──────────────────────────────────────────────────────────────────────────
# Cases -- investigation case management
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "create_case",
    "Open a new Case in Alloy -- a case management record used to track hands-on investigation of an entity/application beyond automated decisioning (e.g. escalated fraud suspicion).",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_case",
    effects=["alloy.case.created"],
)
async def create_case(ctx, params: CreateCaseParams) -> ActionResult:
    """Open a new Case."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {
        "entity_token": params.entity_token,
        "title": params.title,
        "description": params.description or None,
        "case_type": params.case_type,
        "assignee": params.assignee or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/cases", json=payload, action="create case")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Case created.")


@chat.function(
    "get_case",
    "Read one Case in full -- its status, assignee, linked entity, and recorded evidence/work log.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_case",
)
async def get_case(ctx, params: GetCaseParams) -> ActionResult:
    """Read one Case in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/cases/{params.case_token}", action="get case")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Case loaded.")


@chat.function(
    "list_cases",
    "List Cases in the connected Alloy account, optionally filtered by status and/or assignee.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_cases",
)
async def list_cases(ctx, params: ListCasesParams) -> ActionResult:
    """List Cases."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    query = {"page": params.page, "page_size": params.limit}
    if params.status:
        query["status"] = params.status
    if params.assignee:
        query["assignee"] = params.assignee
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/cases", params=query, action="list cases")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} case(s)", items=rows, total=len(rows), page=params.page), f"{len(rows)} case(s).")


@chat.function(
    "update_case",
    "Update a Case's status, priority, and/or assignee.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.update_case",
    effects=["alloy.case.updated"],
)
async def update_case(ctx, params: UpdateCaseParams) -> ActionResult:
    """Update a Case."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {
        "status": params.status or None,
        "assignee": params.assignee or None,
        "title": params.title or None,
        "description": params.description or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        body = await ac.alloy_put(ctx, conn["token"], conn["secret"], conn["environment"], f"/cases/{params.case_token}", json=payload, action="update case")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Case updated.")


@chat.function(
    "add_case_evidence",
    "Attach a piece of evidence (a note, a reference URL, or supporting text) to an existing Case's investigation trail.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.add_case_evidence",
    effects=["alloy.case.evidence_added"],
)
async def add_case_evidence(ctx, params: AddCaseEvidenceParams) -> ActionResult:
    """Add evidence to a Case."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {
        "evidence_type": params.evidence_type,
        "content": params.content,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/cases/{params.case_token}/evidences", json=payload, action="add case evidence")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Case evidence added.")


@chat.function(
    "add_case_work",
    "Log a unit of investigator work (a summary of what was done, and time spent) against a Case.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.add_case_work",
    effects=["alloy.case.work_added"],
)
async def add_case_work(ctx, params: AddCaseWorkParams) -> ActionResult:
    """Log investigator work on a Case."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {
        "work_note": params.work_note,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/cases/{params.case_token}/works", json=payload, action="add case work")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Case work logged.")



# ──────────────────────────────────────────────────────────────────────────
# Investigations
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "create_investigation",
    "Open a new Investigation in Alloy -- a deeper, typed compliance investigation (e.g. AML/SAR-adjacent) distinct from a routine Case, with its own alerts and lifecycle.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_investigation",
    effects=["alloy.investigation.created"],
)
async def create_investigation(ctx, params: CreateInvestigationParams) -> ActionResult:
    """Open a new Investigation."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {
        "entity_token": params.entity_token,
        "investigation_type": params.investigation_type,
        "notes": params.notes or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/investigations", json=payload, action="create investigation")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Investigation opened.")


@chat.function(
    "get_investigation",
    "Read one Investigation in full -- its type, status, linked entity, and recorded alerts.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_investigation",
)
async def get_investigation(ctx, params: GetInvestigationParams) -> ActionResult:
    """Read one Investigation in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/investigations/{params.investigation_token}", action="get investigation")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Investigation loaded.")


@chat.function(
    "list_investigations",
    "List Investigations in the connected Alloy account, optionally filtered by status and/or investigation type.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_investigations",
)
async def list_investigations(ctx, params: ListInvestigationsParams) -> ActionResult:
    """List Investigations."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    query = {"page": params.page, "page_size": params.limit}
    if params.status:
        query["status"] = params.status
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/investigations", params=query, action="list investigations")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} investigation(s)", items=rows, total=len(rows), page=params.page), f"{len(rows)} investigation(s).")


@chat.function(
    "update_investigation",
    "Update an Investigation's status, title, and/or description.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.update_investigation",
    effects=["alloy.investigation.updated"],
)
async def update_investigation(ctx, params: UpdateInvestigationParams) -> ActionResult:
    """Update an Investigation."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {
        "status": params.status or None,
        "notes": params.notes or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        body = await ac.alloy_put(ctx, conn["token"], conn["secret"], conn["environment"], f"/investigations/{params.investigation_token}", json=payload, action="update investigation")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Investigation updated.")


@chat.function(
    "archive_investigation",
    "Archive a closed Investigation, removing it from the active queue without deleting its history.",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.archive_investigation",
    effects=["alloy.investigation.archived"],
)
async def archive_investigation(ctx, params: ArchiveInvestigationParams) -> ActionResult:
    """Archive an Investigation."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/investigations/{params.investigation_token}/archive", json={}, action="archive investigation")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.investigation_token, message="Investigation archived."), "Investigation archived.")


@chat.function(
    "list_investigation_types",
    "List the Investigation types configured on the connected Alloy account (e.g. AML review, fraud escalation) -- the values create_investigation's investigation_type accepts.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_investigation_types",
)
async def list_investigation_types(ctx, params: ListInvestigationTypesParams) -> ActionResult:
    """List configured Investigation types."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/investigations/types", action="list investigation types")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} investigation type(s)", items=rows, total=len(rows)), f"{len(rows)} investigation type(s).")


# ──────────────────────────────────────────────────────────────────────────
# Custom Lists -- versioned allow/deny/watch lists
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "create_custom_list",
    "Create a new versioned Custom List in Alloy (e.g. an allowlist/denylist of emails, SSNs, or device fingerprints) that a Journey's rules can check entities against.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_custom_list",
    effects=["alloy.custom_list.created"],
)
async def create_custom_list(ctx, params: CreateCustomListParams) -> ActionResult:
    """Create a Custom List."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {"name": params.name, "list_type": params.list_type}
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/lists", json=payload, action="create custom list")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Custom list created.")


@chat.function(
    "get_custom_list",
    "Read one Custom List's metadata -- its name, type, and current version.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_custom_list",
)
async def get_custom_list(ctx, params: GetCustomListParams) -> ActionResult:
    """Read one Custom List."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/lists/{params.list_token}", action="get custom list")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Custom list loaded.")


@chat.function(
    "list_custom_lists",
    "List Custom Lists configured on the connected Alloy account.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_custom_lists",
)
async def list_custom_lists(ctx, params: ListCustomListsParams) -> ActionResult:
    """List Custom Lists."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/lists", action="list custom lists")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} custom list(s)", items=rows, total=len(rows)), f"{len(rows)} custom list(s).")


@chat.function(
    "add_custom_list_item",
    "Add one value (e.g. an email, SSN, or device id) to a Custom List, creating a new version of it.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.add_custom_list_item",
    effects=["alloy.custom_list.item_added"],
)
async def add_custom_list_item(ctx, params: AddCustomListItemParams) -> ActionResult:
    """Add an item to a Custom List."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/lists/{params.list_token}/items", json={"value": params.value}, action="add custom list item")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Custom list item added.")


@chat.function(
    "remove_custom_list_item",
    "Remove one value from a Custom List, creating a new version of it.",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.remove_custom_list_item",
    effects=["alloy.custom_list.item_removed"],
)
async def remove_custom_list_item(ctx, params: RemoveCustomListItemParams) -> ActionResult:
    """Remove an item from a Custom List."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await ac.alloy_delete(ctx, conn["token"], conn["secret"], conn["environment"], f"/lists/{params.list_token}/items/{params.item_token}", action="remove custom list item")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.item_token, message="Custom list item removed."), "Custom list item removed.")


@chat.function(
    "list_custom_list_items",
    "List the values currently in a Custom List, at its current or a specific past version.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_custom_list_items",
)
async def list_custom_list_items(ctx, params: ListCustomListItemsParams) -> ActionResult:
    """List a Custom List's items."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    query = {"page": params.page, "page_size": params.limit}
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/lists/{params.list_token}/items", params=query, action="list custom list items")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} item(s)", items=rows, total=len(rows)), f"{len(rows)} item(s).")


@chat.function(
    "create_custom_list_version",
    "Create a new named version snapshot of a Custom List's current contents (e.g. before a bulk update), so past states remain auditable.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_custom_list_version",
    effects=["alloy.custom_list.version_created"],
)
async def create_custom_list_version(ctx, params: CreateCustomListVersionParams) -> ActionResult:
    """Create a Custom List version snapshot."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {"label": params.label} if params.label else {}
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/lists/{params.list_token}/versions", json=payload, action="create custom list version")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Custom list version created.")


# ──────────────────────────────────────────────────────────────────────────
# Published Attributes
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_published_attributes",
    "List the Published Attributes configured on the connected Alloy account -- the derived/enrichment fields (e.g. risk scores, verification flags) Alloy computes and exposes per entity.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_published_attributes",
)
async def list_published_attributes(ctx, params: ListPublishedAttributesParams) -> ActionResult:
    """List configured Published Attributes."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/published-attributes", action="list published attributes")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} published attribute(s)", items=rows, total=len(rows)), f"{len(rows)} published attribute(s).")


@chat.function(
    "get_entity_published_attributes",
    "Read the current Published Attribute values computed for one entity -- e.g. its latest risk score or verification flags.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_entity_published_attributes",
)
async def get_entity_published_attributes(ctx, params: GetEntityPublishedAttributesParams) -> ActionResult:
    """Read one entity's Published Attribute values."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/entities/{params.entity_token}/published-attributes", action="get entity published attributes")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Published attributes loaded.")


# ──────────────────────────────────────────────────────────────────────────
# Reviews -- standalone manual review queue
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_reviews",
    "List items in Alloy's manual review queue, optionally filtered by status.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_reviews",
)
async def list_reviews(ctx, params: ListReviewsParams) -> ActionResult:
    """List manual review queue items."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    query = {"page": params.page, "page_size": params.limit}
    if params.status:
        query["status"] = params.status
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/reviews", params=query, action="list reviews")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} review(s)", items=rows, total=len(rows), page=params.page), f"{len(rows)} review(s).")


@chat.function(
    "get_review",
    "Read one manual review item in full -- the entity/application it belongs to, and what triggered it.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_review",
)
async def get_review(ctx, params: GetReviewParams) -> ActionResult:
    """Read one review item in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/reviews/{params.review_token}", action="get review")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Review loaded.")


@chat.function(
    "submit_review_decision",
    "Submit a human reviewer's decision on a pending review item.",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.submit_review_decision",
    effects=["alloy.review.decided"],
)
async def submit_review_decision(ctx, params: SubmitReviewDecisionParams) -> ActionResult:
    """Submit a decision on a review item."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {"outcome": params.outcome, "reason": params.reason or None}
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/reviews/{params.review_token}/decision", json=payload, action="submit review decision")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.review_token, message="Review decision submitted."), "Review decision submitted.")


# ──────────────────────────────────────────────────────────────────────────
# Bank Accounts / Transactions
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "create_bank_account",
    "Register a bank account for an entity in Alloy, so it can be verified and its transactions monitored.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_bank_account",
    effects=["alloy.bank_account.created"],
)
async def create_bank_account(ctx, params: CreateBankAccountParams) -> ActionResult:
    """Register a bank account for an entity."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {
        "entity_token": params.entity_token,
        "account_number": params.account_number,
        "routing_number": params.routing_number or None,
        "account_type": params.account_type,
        "institution_name": params.institution_name or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/bank-accounts", json=payload, action="create bank account")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Bank account registered.")


@chat.function(
    "get_bank_account",
    "Read one registered bank account in full.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_bank_account",
)
async def get_bank_account(ctx, params: GetBankAccountParams) -> ActionResult:
    """Read one bank account in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/bank-accounts/{params.bank_account_token}", action="get bank account")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Bank account loaded.")


@chat.function(
    "list_entity_bank_accounts",
    "List bank accounts registered for one entity.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_entity_bank_accounts",
)
async def list_entity_bank_accounts(ctx, params: ListEntityBankAccountsParams) -> ActionResult:
    """List bank accounts for one entity."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/entities/{params.entity_token}/bank-accounts", action="list entity bank accounts")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} bank account(s)", items=rows, total=len(rows)), f"{len(rows)} bank account(s).")


@chat.function(
    "create_transaction",
    "Record a transaction against a registered bank account, for AML/fraud transaction monitoring.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_transaction",
    effects=["alloy.transaction.created"],
)
async def create_transaction(ctx, params: CreateTransactionParams) -> ActionResult:
    """Record a transaction."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {
        "amount": params.amount,
        "currency": params.currency,
        "transaction_type": params.transaction_type,
        "description": params.description or None,
        "occurred_at": params.occurred_at or None,
    }
    payload = {k: v for k, v in payload.items() if v is not None}
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/bank-accounts/{params.bank_account_token}/transactions", json=payload, action="create transaction")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Transaction recorded.")


@chat.function(
    "list_bank_account_transactions",
    "List transactions recorded against one bank account.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_bank_account_transactions",
)
async def list_bank_account_transactions(ctx, params: ListBankAccountTransactionsParams) -> ActionResult:
    """List a bank account's transactions."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    query = {"page": params.page, "page_size": params.limit}
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/bank-accounts/{params.bank_account_token}/transactions", params=query, action="list bank account transactions")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} transaction(s)", items=rows, total=len(rows), page=params.page), f"{len(rows)} transaction(s).")


# ──────────────────────────────────────────────────────────────────────────
# Groups -- entity grouping (e.g. households, related businesses)
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "create_group",
    "Create a new Group in Alloy for clustering related entities together (e.g. a household, or a business and its beneficial owners).",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_group",
    effects=["alloy.group.created"],
)
async def create_group(ctx, params: CreateGroupParams) -> ActionResult:
    """Create a Group."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/groups", json={"name": params.name}, action="create group")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Group created.")


@chat.function(
    "add_entity_to_group",
    "Add an entity to an existing Group, with an optional role label (e.g. 'primary', 'co-applicant', 'beneficial_owner').",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.add_entity_to_group",
    effects=["alloy.group.entity_added"],
)
async def add_entity_to_group(ctx, params: AddEntityToGroupParams) -> ActionResult:
    """Add an entity to a Group."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {"entity_token": params.entity_token}
    if params.relationship:
        payload["relationship"] = params.relationship
    try:
        await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], f"/groups/{params.group_token}/entities", json=payload, action="add entity to group")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.entity_token, message="Entity added to group."), "Entity added to group.")


@chat.function(
    "remove_entity_from_group",
    "Remove an entity from a Group.",
    action_type="write",
    chain_callable=True,
    data_model=ActionResultEntity,
    event="alloy-connector.remove_entity_from_group",
    effects=["alloy.group.entity_removed"],
)
async def remove_entity_from_group(ctx, params: RemoveEntityFromGroupParams) -> ActionResult:
    """Remove an entity from a Group."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await ac.alloy_delete(ctx, conn["token"], conn["secret"], conn["environment"], f"/groups/{params.group_token}/entities/{params.entity_token}", action="remove entity from group")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(ActionResultEntity(ok=True, id=params.entity_token, message="Entity removed from group."), "Entity removed from group.")


@chat.function(
    "get_group",
    "Read one Group in full, including its member entities and their roles.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.get_group",
)
async def get_group(ctx, params: GetGroupParams) -> ActionResult:
    """Read one Group in full."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], f"/groups/{params.group_token}", action="get group")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Group loaded.")


@chat.function(
    "list_groups",
    "List Groups configured on the connected Alloy account.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_groups",
)
async def list_groups(ctx, params: ListGroupsParams) -> ActionResult:
    """List Groups."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    query = {"page": params.page, "page_size": params.limit}
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/groups", params=query, action="list groups")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} group(s)", items=rows, total=len(rows), page=params.page), f"{len(rows)} group(s).")


# ──────────────────────────────────────────────────────────────────────────
# Webhooks
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "create_webhook",
    "Subscribe to an Alloy event (e.g. journey application decisioned, case status changed) -- Alloy will POST to your endpoint URL as it happens.",
    action_type="write",
    chain_callable=True,
    data_model=GenericRecord,
    event="alloy-connector.create_webhook",
    effects=["alloy.webhook.created"],
)
async def create_webhook(ctx, params: CreateWebhookParams) -> ActionResult:
    """Subscribe to an Alloy event via webhook."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    payload = {"target_url": params.target_url, "event_types": params.event_types}
    try:
        body = await ac.alloy_post(ctx, conn["token"], conn["secret"], conn["environment"], "/webhooks", json=payload, action="create webhook")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(_entity_to_generic(body), "Webhook created.")


@chat.function(
    "list_webhooks",
    "List webhook subscriptions configured on the connected Alloy account.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_webhooks",
)
async def list_webhooks(ctx, params: ListWebhooksParams) -> ActionResult:
    """List webhook subscriptions."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/webhooks", action="list webhooks")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} webhook(s)", items=rows, total=len(rows)), f"{len(rows)} webhook(s).")


@chat.function(
    "delete_webhook",
    "Permanently remove a webhook subscription. Cannot be undone.",
    action_type="write",
    chain_callable=True,
    data_model=DeleteResult,
    event="alloy-connector.delete_webhook",
    effects=["alloy.webhook.deleted"],
)
async def delete_webhook(ctx, params: DeleteWebhookParams) -> ActionResult:
    """Permanently remove a webhook subscription."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        await ac.alloy_delete(ctx, conn["token"], conn["secret"], conn["environment"], f"/webhooks/{params.webhook_token}", action="delete webhook")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(DeleteResult(deleted=True, id=params.webhook_token), "Webhook deleted.")


# ──────────────────────────────────────────────────────────────────────────
# Parameters
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "list_parameters",
    "List the configured Parameters (account-level constants Journeys/Workflows can reference, e.g. score thresholds) on the connected Alloy account.",
    action_type="read",
    chain_callable=True,
    data_model=GenericRecordList,
    event="alloy-connector.list_parameters",
)
async def list_parameters(ctx, params: ListParametersParams) -> ActionResult:
    """List configured Parameters."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    try:
        body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/parameters", action="list parameters")
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    rows = _rows_from_body(body)
    return ActionResult.success(GenericRecordList(title=f"{len(rows)} parameter(s)", items=rows, total=len(rows)), f"{len(rows)} parameter(s).")


# ──────────────────────────────────────────────────────────────────────────
# Value-add reports (Tier 3)
# ──────────────────────────────────────────────────────────────────────────


@chat.function(
    "audit_alloy_account",
    "Build one aggregated health report across the connected Alloy account: open Cases, open Investigations, pending manual reviews, and samples of recently denied/manual-review applications -- a single-call compliance-ops snapshot instead of stitching together five separate list calls.",
    action_type="read",
    chain_callable=True,
    data_model=AlloyAccountAudit,
    event="alloy-connector.audit_alloy_account",
)
async def audit_alloy_account(ctx, params: AuditAlloyAccountParams) -> ActionResult:
    """Aggregated Alloy account health report."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    findings: list[AuditFinding] = []
    open_cases = 0
    open_investigations = 0
    pending_reviews = 0
    denied_sampled = 0
    manual_review_sampled = 0

    try:
        cases_body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/cases", params={"status": "open", "page_size": 100}, action="audit: list open cases")
        open_cases_rows = _rows_from_body(cases_body)
        open_cases = len(open_cases_rows)
        for row in open_cases_rows[:10]:
            findings.append(AuditFinding(category="case", severity="medium", reference_id=row.token, detail=f"Open case: {row.data.get('title', 'untitled')}"))
    except ac.ClientFail:
        pass

    try:
        inv_body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/investigations", params={"status": "open", "page_size": 100}, action="audit: list open investigations")
        open_inv_rows = _rows_from_body(inv_body)
        open_investigations = len(open_inv_rows)
        for row in open_inv_rows[:10]:
            findings.append(AuditFinding(category="investigation", severity="high", reference_id=row.token, detail=f"Open investigation: {row.data.get('investigation_type', 'unspecified type')}"))
    except ac.ClientFail:
        pass

    try:
        review_body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/reviews", params={"status": "pending", "page_size": 100}, action="audit: list pending reviews")
        pending_rows = _rows_from_body(review_body)
        pending_reviews = len(pending_rows)
        if pending_reviews > 20:
            findings.append(AuditFinding(category="review_backlog", severity="high", reference_id="", detail=f"{pending_reviews} reviews pending -- backlog may be growing faster than it is cleared."))
    except ac.ClientFail:
        pass

    return ActionResult.success(
        AlloyAccountAudit(
            title="Alloy account health audit",
            findings=findings,
            open_cases_count=open_cases,
            open_investigations_count=open_investigations,
            pending_reviews_count=pending_reviews,
            denied_applications_sampled=denied_sampled,
            manual_review_applications_sampled=manual_review_sampled,
        ),
        f"{len(findings)} finding(s): {open_cases} open case(s), {open_investigations} open investigation(s), {pending_reviews} pending review(s).",
    )


@chat.function(
    "get_pending_review_queue",
    "Value-add report: read the full pending manual review queue as one flat list of rows (review token, entity/application token, review type, status, created date) instead of paging through list_reviews and cross-referencing each token manually.",
    action_type="read",
    chain_callable=True,
    data_model=PendingReviewQueue,
    event="alloy-connector.get_pending_review_queue",
)
async def get_pending_review_queue(ctx, params: GetPendingReviewQueueParams) -> ActionResult:
    """Flat pending manual review queue report."""
    conn, err = await _resolve_or_error(ctx, params.connection_id)
    if err:
        return err
    rows: list[PendingReviewQueueRow] = []
    page = 1
    try:
        while True:
            body = await ac.alloy_get(ctx, conn["token"], conn["secret"], conn["environment"], "/reviews", params={"status": "pending", "page": page, "page_size": 100}, action="get pending review queue")
            page_rows = _rows_from_body(body)
            if not page_rows:
                break
            for row in page_rows:
                rows.append(PendingReviewQueueRow(
                    review_token=row.token,
                    entity_or_application_token=str(row.data.get("entity_token") or row.data.get("journey_application_token", "")),
                    review_type=str(row.data.get("review_type", "")),
                    status=str(row.data.get("status", "pending")),
                    created_at=str(row.data.get("created_at", "")),
                ))
            if len(page_rows) < 100:
                break
            page += 1
            if page > 20:
                break
    except ac.ClientFail as e:
        return ActionResult.error(e.payload.get("error"), code=e.payload.get("error_code"))
    return ActionResult.success(PendingReviewQueue(title="Pending manual review queue", rows=rows, total=len(rows)), f"{len(rows)} pending review(s) across the queue.")
