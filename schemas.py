"""Pydantic params models + SDL entity contracts for Alloy Connector.

All params models are module-scope (V17 federal invariant, same rule as
Cin7 Core Connector / MuleSoft Connector / Shopify Connector's schemas.py).
"""
from __future__ import annotations

from pydantic import BaseModel, Field
from imperal_sdk import sdl


class NoParams(BaseModel):
    """Explicit empty params model -- V17 disallows untyped handlers."""
    pass


# ──────────────────────────────────────────────────────────────────────────
# Connection
# ──────────────────────────────────────────────────────────────────────────


class ConnectAlloyParams(BaseModel):
    token: str = Field("", description="Alloy account token from Dashboard > API Key Settings.")
    secret: str = Field("", description="Alloy account secret from the same API Key Settings page.")
    environment: str = Field(
        "sandbox",
        description="Which Alloy environment this token/secret pair belongs to: 'sandbox' or 'production'.",
    )
    label: str = Field("", description="Optional friendly name for this account connection.")


class ProviderConnection(sdl.Entity):
    id: str = ""
    title: str = ""
    connected: bool = False
    detail: str = ""
    environment: str = "sandbox"


class ConnectionList(sdl.Entity):
    id: str = ""
    title: str = ""
    connections: list[ProviderConnection] = Field(default_factory=list)


class DisconnectAlloyParams(BaseModel):
    connection_id: str = Field("", description="Connection id to disconnect, from list_connections.")


class ListConnectionsParams(NoParams):
    pass


# ──────────────────────────────────────────────────────────────────────────
# Entities -- Persons / Businesses
# ──────────────────────────────────────────────────────────────────────────


class CreatePersonEntityParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    name_first: str = Field(..., description="Person's legal first name.")
    name_last: str = Field(..., description="Person's legal last name.")
    email_address: str = Field("", description="Person's email address.")
    phone_number: str = Field("", description="Person's phone number, e.g. +15551234567.")
    birth_date: str = Field("", description="Date of birth, YYYY-MM-DD.")
    ssn: str = Field("", description="Social Security Number (US) or equivalent national ID -- sent only, never stored by this connector.")
    address_line_1: str = Field("", description="Street address line 1.")
    address_line_2: str = Field("", description="Street address line 2 (apartment/suite).")
    address_city: str = Field("", description="City.")
    address_state: str = Field("", description="State/province code, e.g. NY.")
    address_postal_code: str = Field("", description="ZIP/postal code.")
    address_country_code: str = Field("US", description="Two-letter country code, e.g. US.")
    external_entity_id: str = Field("", description="Your own system's identifier for this person, for future lookups.")
    extra_fields: dict = Field(default_factory=dict, description="Additional Alloy-recognized fields not covered above (e.g. document numbers, employment info).")


class CreateBusinessEntityParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    business_name: str = Field(..., description="Registered legal business name.")
    business_ein: str = Field("", description="Employer Identification Number (US) or equivalent business tax id.")
    business_website: str = Field("", description="Business website URL.")
    business_phone_number: str = Field("", description="Business phone number.")
    address_line_1: str = Field("", description="Registered street address line 1.")
    address_city: str = Field("", description="City.")
    address_state: str = Field("", description="State/province code.")
    address_postal_code: str = Field("", description="ZIP/postal code.")
    address_country_code: str = Field("US", description="Two-letter country code, e.g. US.")
    external_entity_id: str = Field("", description="Your own system's identifier for this business, for future lookups.")
    extra_fields: dict = Field(default_factory=dict, description="Additional Alloy-recognized fields (e.g. NAICS code, formation date, beneficial owners).")


class GetEntityParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token to read, from a previous create/list result.")
    entity_type: str = Field("person", description="Entity kind: 'person' or 'business'.")


class MergeEntitiesParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    primary_entity_token: str = Field(..., description="The entity token to keep as the surviving record.")
    duplicate_entity_token: str = Field(..., description="The entity token to merge into the primary and retire.")


class AddEntityNoteParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token to attach the note to.")
    note: str = Field(..., description="Free-text note content.")


class SubmitEntityFeedbackParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token the feedback is about.")
    feedback_type: str = Field(..., description="Feedback classification, e.g. 'confirmed_fraud', 'false_positive', as configured in your Alloy account.")
    comment: str = Field("", description="Optional free-text comment explaining the feedback.")


class ListEntityGroupsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token to read groups for.")


# ──────────────────────────────────────────────────────────────────────────
# Journeys / Journey Applications / Batches
# ──────────────────────────────────────────────────────────────────────────


class CreateJourneyApplicationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field(..., description="Alloy Journey token configured in your Alloy Dashboard (the decisioning workflow to run this application through).")
    application_data: dict = Field(..., description="Application field values keyed by the Journey's own field names, e.g. {\"name_first\": \"Jane\", \"name_last\": \"Doe\", \"email_address\": \"jane@example.com\"}.")
    branch_name: str = Field("", description="Optional Journey branch/version name to run against, if your Journey has multiple branches.")


class GetJourneyApplicationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field(..., description="Alloy Journey token this application belongs to.")
    journey_application_token: str = Field(..., description="Journey application token to read, from create_journey_application's result.")


class ListJourneyApplicationsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field(..., description="Alloy Journey token to list applications for.")
    outcome: str = Field("", description="Filter by outcome status if supported, e.g. 'Approved', 'Denied', 'Manual Review'. Omit for all.")
    page: int = Field(1, ge=1, description="Page number for paginated results.")
    limit: int = Field(50, ge=1, le=500, description="Items per page.")


class RerunJourneyApplicationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field(..., description="Alloy Journey token this application belongs to.")
    journey_application_token: str = Field(..., description="Journey application token to rerun through the Journey's decisioning logic.")


class ManualReviewJourneyApplicationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field(..., description="Alloy Journey token this application belongs to.")
    journey_application_token: str = Field(..., description="Journey application token currently gated in manual review.")
    manual_review_token: str = Field(..., description="Manual review token identifying which alert/queue item to resolve, from get_alert_manual_review_token.")
    outcome: str = Field(..., description="Reviewer's decision outcome, e.g. 'Approved', 'Denied', as configured for this Journey's manual review step.")
    reason: str = Field("", description="Optional free-text reason for the reviewer's decision.")


class GetAlertManualReviewTokenParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field(..., description="Alloy Journey token this application belongs to.")
    journey_application_token: str = Field(..., description="Journey application token currently in manual review.")


class GetJourneySchemaParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field(..., description="Alloy Journey token to read the input field schema for.")


class UpdateJourneyApplicationNodeParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field(..., description="Alloy Journey token this application belongs to.")
    journey_application_token: str = Field(..., description="Journey application token whose action node is being updated.")
    node_id: str = Field(..., description="The Journey's action node id to update, from the Journey's own configuration.")
    node_data: dict = Field(..., description="New values for this action node, keyed by the node's own field names.")


class CreateJourneyBatchParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field(..., description="Alloy Journey token to run this batch of applications through.")
    applications: list[dict] = Field(..., description="List of application field-value dicts, one per applicant, in the same shape as create_journey_application's application_data.")


class GetJourneyBatchParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field(..., description="Alloy Journey token this batch belongs to.")
    journey_batch_token: str = Field(..., description="Journey batch token to read, from create_journey_batch's result.")


# ──────────────────────────────────────────────────────────────────────────
# Evaluations (legacy/direct decisioning, alongside Journeys)
# ──────────────────────────────────────────────────────────────────────────


class RunEvaluationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    workflow_token: str = Field(..., description="Alloy Workflow token configured in your Alloy Dashboard for direct (non-Journey) evaluations.")
    evaluation_data: dict = Field(..., description="Applicant field values keyed by the Workflow's own field names.")


class GetEvaluationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    evaluation_token: str = Field(..., description="Evaluation token to read, from run_evaluation's result.")


class RunPortfolioEvaluationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    portfolio_token: str = Field(..., description="Alloy Portfolio Risk workflow token to run this book of business against.")
    evaluation_data: dict = Field(..., description="Portfolio-level field values, keyed by the portfolio workflow's own field names.")


class GetPortfolioEvaluationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    portfolio_evaluation_token: str = Field(..., description="Portfolio evaluation token to read, from run_portfolio_evaluation's result.")


# ──────────────────────────────────────────────────────────────────────────
# Documents
# ──────────────────────────────────────────────────────────────────────────


class UploadDocumentParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token this document belongs to.")
    document_type: str = Field(..., description="Document classification, e.g. 'drivers_license', 'passport', 'utility_bill', 'articles_of_incorporation'.")
    file_base64: str = Field(..., description="Base64-encoded file content of the document image/PDF.")
    file_name: str = Field("", description="Original file name, e.g. 'license_front.jpg'.")


class GetDocumentParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    document_token: str = Field(..., description="Document token to read, from upload_document's result.")


class UpdateDocumentParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    document_token: str = Field(..., description="Document token to update.")
    document_type: str = Field("", description="New document classification. Omit to keep unchanged.")
    status: str = Field("", description="New review status, e.g. 'verified', 'rejected', as configured for your account. Omit to keep unchanged.")


class ListEntityDocumentsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token to list uploaded documents for.")


# ──────────────────────────────────────────────────────────────────────────
# Events -- ongoing monitoring
# ──────────────────────────────────────────────────────────────────────────


class SendEventParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token this event happened to.")
    event_type: str = Field(..., description="Alloy event type, e.g. 'login', 'transaction', 'address_change', 'phone_change', as configured for ongoing monitoring on your account.")
    event_data: dict = Field(..., description="Event payload fields keyed by the event type's own schema, e.g. amount/currency for a transaction event.")
    occurred_at: str = Field("", description="ISO-8601 timestamp the event actually happened at. Omit to use the time Alloy receives it.")


class ListEntityEventsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token to list recorded events for.")
    event_type: str = Field("", description="Filter by event type. Omit for all types.")
    page: int = Field(1, ge=1, description="Page number for paginated results.")
    limit: int = Field(50, ge=1, le=500, description="Items per page.")


# ──────────────────────────────────────────────────────────────────────────
# Cases -- investigation case management
# ──────────────────────────────────────────────────────────────────────────


class CreateCaseParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token this case is about.")
    case_type: str = Field(..., description="Case classification as configured on your account, e.g. 'fraud_review', 'aml_alert'.")
    title: str = Field("", description="Short human-readable case title.")
    description: str = Field("", description="Free-text case description.")
    assignee: str = Field("", description="Alloy user id/email to assign this case to. Omit to leave unassigned.")


class GetCaseParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    case_token: str = Field(..., description="Case token to read, from create_case's result.")


class ListCasesParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    status: str = Field("", description="Filter by case status, e.g. 'open', 'closed'. Omit for all.")
    assignee: str = Field("", description="Filter by assignee. Omit for all.")
    page: int = Field(1, ge=1, description="Page number for paginated results.")
    limit: int = Field(50, ge=1, le=500, description="Items per page.")


class UpdateCaseParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    case_token: str = Field(..., description="Case token to update.")
    status: str = Field("", description="New case status. Omit to keep unchanged.")
    assignee: str = Field("", description="New assignee. Omit to keep unchanged.")
    title: str = Field("", description="New title. Omit to keep unchanged.")
    description: str = Field("", description="New description. Omit to keep unchanged.")


class AddCaseEvidenceParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    case_token: str = Field(..., description="Case token to attach evidence to.")
    evidence_type: str = Field(..., description="Evidence classification, e.g. 'document', 'note', 'external_link'.")
    content: str = Field(..., description="Evidence content: a document token, free-text note, or URL depending on evidence_type.")


class AddCaseWorkParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    case_token: str = Field(..., description="Case token to log work against.")
    work_note: str = Field(..., description="Free-text description of the investigative work performed.")


# ──────────────────────────────────────────────────────────────────────────
# Investigations
# ──────────────────────────────────────────────────────────────────────────


class CreateInvestigationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token this investigation is about.")
    investigation_type: str = Field(..., description="Investigation type as configured on your account.")
    notes: str = Field("", description="Optional initial notes.")


class GetInvestigationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    investigation_token: str = Field(..., description="Investigation token to read, from create_investigation's result.")


class ListInvestigationsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    status: str = Field("", description="Filter by investigation status. Omit for all.")
    page: int = Field(1, ge=1, description="Page number for paginated results.")
    limit: int = Field(50, ge=1, le=500, description="Items per page.")


class UpdateInvestigationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    investigation_token: str = Field(..., description="Investigation token to update.")
    status: str = Field("", description="New status, e.g. 'assigned', 'in_review', 'archived'. Omit to keep unchanged.")
    notes: str = Field("", description="New/appended notes. Omit to keep unchanged.")


class ArchiveInvestigationParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    investigation_token: str = Field(..., description="Investigation token to archive.")


class ListInvestigationTypesParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")


# ──────────────────────────────────────────────────────────────────────────
# Custom Lists -- internal watchlists/allowlists
# ──────────────────────────────────────────────────────────────────────────


class CreateCustomListParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    name: str = Field(..., description="Custom list name, e.g. 'Internal Watchlist', 'VIP Allowlist'.")
    list_type: str = Field(..., description="List item shape, e.g. 'name', 'email_address', 'ssn', 'ein', as supported by Alloy custom lists.")
    description: str = Field("", description="Optional list description.")


class GetCustomListParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    list_token: str = Field(..., description="Custom list token to read, from create_custom_list's result.")


class ListCustomListsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")


class AddCustomListItemParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    list_token: str = Field(..., description="Custom list token to add an item to.")
    value: str = Field(..., description="The value to add, matching the list's configured list_type (e.g. a name, email, or SSN).")
    label: str = Field("", description="Optional label/reason for this list entry.")


class RemoveCustomListItemParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    list_token: str = Field(..., description="Custom list token to remove an item from.")
    item_token: str = Field(..., description="List item token to remove, from list_custom_list_items.")


class ListCustomListItemsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    list_token: str = Field(..., description="Custom list token to list items for.")
    page: int = Field(1, ge=1, description="Page number for paginated results.")
    limit: int = Field(50, ge=1, le=500, description="Items per page.")


class CreateCustomListVersionParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    list_token: str = Field(..., description="Custom list token to create a new version snapshot for.")
    label: str = Field("", description="Optional label for this version, e.g. 'Q3 2026 review'.")


# ──────────────────────────────────────────────────────────────────────────
# Published Attributes
# ──────────────────────────────────────────────────────────────────────────


class ListPublishedAttributesParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")


class GetEntityPublishedAttributesParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token to read published attribute values for.")


# ──────────────────────────────────────────────────────────────────────────
# Reviews (standalone review queue, alongside Journey manual review)
# ──────────────────────────────────────────────────────────────────────────


class ListReviewsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    status: str = Field("", description="Filter by review status, e.g. 'pending', 'completed'. Omit for all.")
    page: int = Field(1, ge=1, description="Page number for paginated results.")
    limit: int = Field(50, ge=1, le=500, description="Items per page.")


class GetReviewParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    review_token: str = Field(..., description="Review token to read, from list_reviews.")


class SubmitReviewDecisionParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    review_token: str = Field(..., description="Review token to submit a decision for.")
    outcome: str = Field(..., description="Reviewer's decision outcome as configured for this review type.")
    reason: str = Field("", description="Optional free-text reason for the decision.")


# ──────────────────────────────────────────────────────────────────────────
# Bank Accounts / Transactions
# ──────────────────────────────────────────────────────────────────────────


class CreateBankAccountParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token this bank account belongs to.")
    account_number: str = Field(..., description="Bank account number.")
    routing_number: str = Field("", description="Bank routing/sort/IBAN routing code, as applicable to the country.")
    account_type: str = Field("checking", description="Account type, e.g. 'checking', 'savings'.")
    institution_name: str = Field("", description="Name of the bank/financial institution.")


class GetBankAccountParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    bank_account_token: str = Field(..., description="Bank account token to read, from create_bank_account's result.")


class ListEntityBankAccountsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    entity_token: str = Field(..., description="Alloy entity token to list bank accounts for.")


class CreateTransactionParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    bank_account_token: str = Field(..., description="Bank account token this transaction is posted against.")
    amount: float = Field(..., description="Transaction amount (positive for credit/deposit, negative for debit/withdrawal, per your account's sign convention).")
    currency: str = Field("USD", description="Three-letter ISO currency code.")
    transaction_type: str = Field("", description="Transaction classification, e.g. 'ach', 'wire', 'card', 'p2p'.")
    description: str = Field("", description="Free-text transaction description/memo.")
    occurred_at: str = Field("", description="ISO-8601 timestamp the transaction occurred at. Omit to use the time Alloy receives it.")


class ListBankAccountTransactionsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    bank_account_token: str = Field(..., description="Bank account token to list transactions for.")
    page: int = Field(1, ge=1, description="Page number for paginated results.")
    limit: int = Field(50, ge=1, le=500, description="Items per page.")


# ──────────────────────────────────────────────────────────────────────────
# Groups / Entity Groups (household/business relationship linking)
# ──────────────────────────────────────────────────────────────────────────


class CreateGroupParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    name: str = Field(..., description="Group name, e.g. a household or a related-business cluster name.")
    group_type: str = Field("", description="Group classification as configured on your account, e.g. 'household', 'business_network'.")


class AddEntityToGroupParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    group_token: str = Field(..., description="Group token to add the entity to, from create_group's result.")
    entity_token: str = Field(..., description="Alloy entity token to add to this group.")
    relationship: str = Field("", description="Optional relationship label, e.g. 'spouse', 'beneficial_owner'.")


class RemoveEntityFromGroupParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    group_token: str = Field(..., description="Group token to remove the entity from.")
    entity_token: str = Field(..., description="Alloy entity token to remove from this group.")


class GetGroupParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    group_token: str = Field(..., description="Group token to read.")


class ListGroupsParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    page: int = Field(1, ge=1, description="Page number for paginated results.")
    limit: int = Field(50, ge=1, le=500, description="Items per page.")


# ──────────────────────────────────────────────────────────────────────────
# Webhooks
# ──────────────────────────────────────────────────────────────────────────


class CreateWebhookParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    target_url: str = Field(..., description="HTTPS endpoint Alloy will POST events to.")
    event_types: list[str] = Field(default_factory=list, description="Alloy event types to subscribe to, e.g. ['journey_application_status_change', 'case_status_change']. Empty means all supported types.")


class ListWebhooksParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")


class DeleteWebhookParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    webhook_token: str = Field(..., description="Webhook token to delete, from list_webhooks.")


# ──────────────────────────────────────────────────────────────────────────
# Parameters (reference/config data Alloy exposes about the account itself)
# ──────────────────────────────────────────────────────────────────────────


class ListParametersParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    parameter_type: str = Field("", description="Filter by parameter category, e.g. 'document_types', 'case_types', 'feedback_types'. Omit for all available parameter sets.")


# ──────────────────────────────────────────────────────────────────────────
# Value-add: cross-resource reports built by this connector, not Alloy itself
# ──────────────────────────────────────────────────────────────────────────


class AuditAlloyAccountParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")
    journey_token: str = Field("", description="Optional: scope the audit to one Journey's recent applications. Omit to sample across open cases/investigations/reviews account-wide.")


class GetPendingReviewQueueParams(BaseModel):
    connection_id: str = Field("", description="Connection id from list_connections. Omit if only one account is connected.")


# ──────────────────────────────────────────────────────────────────────────
# Entity / response models (SDL entities returned to chat/panel)
# ──────────────────────────────────────────────────────────────────────────


class DeleteResult(sdl.Entity):
    title: str = ""
    deleted: bool = False
    id: str = ""


class GenericRecord(sdl.Entity):
    """Thin pass-through wrapper for Alloy resources whose full field shape
    is too large/variable to model field-by-field (Entities, Journey
    Applications, Evaluations, Cases, Investigations all carry dozens of
    optional, account-configured fields) -- returning the raw dict as
    `data` avoids re-declaring every field twice while still giving
    chat/panel code a stable entity name. Same pattern as Cin7 Core's /
    MuleSoft's / Salesforce's raw passthrough rows."""
    title: str = ""
    id: str = ""
    token: str = ""
    data: dict = Field(default_factory=dict)


class GenericRecordList(sdl.Entity):
    id: str = ""
    title: str = ""
    items: list[GenericRecord] = Field(default_factory=list)
    total: int = 0
    page: int = 1


class ActionResultEntity(sdl.Entity):
    title: str = ""
    ok: bool = True
    id: str = ""
    message: str = ""


class AuditFinding(sdl.Entity):
    id: str = ""
    title: str = ""
    category: str = ""
    severity: str = ""
    reference_id: str = ""
    detail: str = ""


class AlloyAccountAudit(sdl.Entity):
    id: str = ""
    title: str = ""
    findings: list[AuditFinding] = Field(default_factory=list)
    open_cases_count: int = 0
    open_investigations_count: int = 0
    pending_reviews_count: int = 0
    denied_applications_sampled: int = 0
    manual_review_applications_sampled: int = 0


class PendingReviewQueueRow(sdl.Entity):
    id: str = ""
    title: str = ""
    review_token: str = ""
    entity_or_application_token: str = ""
    review_type: str = ""
    status: str = ""
    created_at: str = ""


class PendingReviewQueue(sdl.Entity):
    id: str = ""
    title: str = ""
    rows: list[PendingReviewQueueRow] = Field(default_factory=list)
    total: int = 0
