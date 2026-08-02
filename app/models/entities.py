"""Database models — per 08_DATA_CONTRACTS_AND_OUTPUT_SCHEMA.md

Entities: users, businesses, outlets, location_candidates, google_connections,
import_batches, reviews, review_versions, review_analyses, review_replies,
approvals, issues, pubsub_events, audit_logs
"""
from datetime import datetime, timezone
from app import db
import uuid


def _uuid():
    return str(uuid.uuid4())


def _now():
    return datetime.now(timezone.utc)


# ─── ROLES ───────────────────────────────────────────────
ROLES = ['owner', 'admin', 'supervisor', 'customer_service', 'viewer']


# ─── USER ────────────────────────────────────────────────
class User(db.Model):
    __tablename__ = 'users'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    email = db.Column(db.String(255), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    display_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(50), nullable=False, default='viewer')  # ROLES enum
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    # Multi-tenant: user belongs to a business
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'), nullable=True)

    def has_role(self, *roles):
        return self.role in roles

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    def get_id(self):
        return self.id


# ─── BUSINESS (tenant) ──────────────────────────────────
class Business(db.Model):
    __tablename__ = 'businesses'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), unique=True, nullable=False, default=_uuid, index=True)
    name = db.Column(db.String(200), nullable=False)
    brand_name = db.Column(db.String(200), nullable=False)
    country = db.Column(db.String(10), default='ID')
    timezone = db.Column(db.String(50), default='Asia/Jakarta')
    default_language = db.Column(db.String(10), default='id')
    status = db.Column(db.String(50), default='active')  # active, suspended, deleted
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    outlets = db.relationship('Outlet', backref='business', lazy='dynamic')
    users = db.relationship('User', backref='business', lazy='dynamic')


# ─── OUTLET ──────────────────────────────────────────────
class Outlet(db.Model):
    __tablename__ = 'outlets'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'), nullable=False)
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.Text)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    public_place_id = db.Column(db.String(200))
    province = db.Column(db.String(100))
    city_regency = db.Column(db.String(100))
    district = db.Column(db.String(100))
    maps_url = db.Column(db.Text)
    business_rating = db.Column(db.Float)
    business_review_count = db.Column(db.Integer)
    source = db.Column(db.String(50), default='public_scraping')
    needs_geographic_resolution = db.Column(db.Boolean, default=False)
    gbp_account_id = db.Column(db.String(200))
    gbp_location_id = db.Column(db.String(200))
    owner_verification_status = db.Column(db.String(50), default='pending')
    gbp_match_status = db.Column(db.String(50), default='unmatched')
    monitor_enabled = db.Column(db.Boolean, default=False)
    reply_enabled = db.Column(db.Boolean, default=False)
    status = db.Column(db.String(50), default='active')
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'gbp_location_id', name='uq_outlet_gbp_location'),
    )


# ─── LOCATION CANDIDATE ─────────────────────────────────
class LocationCandidate(db.Model):
    __tablename__ = 'location_candidates'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'), nullable=False)
    search_query = db.Column(db.String(500))
    place_id = db.Column(db.String(200))
    display_name = db.Column(db.String(300))
    formatted_address = db.Column(db.Text)
    province = db.Column(db.String(100))
    city_regency = db.Column(db.String(100))
    district = db.Column(db.String(100))
    needs_geographic_resolution = db.Column(db.Boolean, default=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    business_status = db.Column(db.String(50))
    google_maps_uri = db.Column(db.Text)
    rating = db.Column(db.Float)
    review_count = db.Column(db.Integer)
    phone = db.Column(db.String(50))
    website = db.Column(db.Text)
    source = db.Column(db.String(50), default='google_places_text_search')
    discovery_status = db.Column(db.String(50), default='discovered')
    match_confidence = db.Column(db.Float)
    match_reasons = db.Column(db.JSON)
    owner_verification_status = db.Column(db.String(50), default='pending')
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'place_id', name='uq_candidate_place'),
    )


# ─── GOOGLE CONNECTION ──────────────────────────────────
class GoogleConnection(db.Model):
    __tablename__ = 'google_connections'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'), nullable=False)
    google_subject_id = db.Column(db.String(200))
    selected_account_id = db.Column(db.String(200))
    encrypted_access_token_ref = db.Column(db.Text)   # encrypted, not plaintext
    encrypted_refresh_token_ref = db.Column(db.Text)   # encrypted, not plaintext
    token_expiry = db.Column(db.DateTime(timezone=True))
    scopes = db.Column(db.Text)
    status = db.Column(db.String(50), default='not_connected')
    connected_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    connected_at = db.Column(db.DateTime(timezone=True))
    last_health_check = db.Column(db.DateTime(timezone=True))
    last_error = db.Column(db.Text)
    last_sync = db.Column(db.DateTime(timezone=True))
    adapter_mode = db.Column(db.String(20), default='mock')  # 'mock' | 'production'
    production_api_connected = db.Column(db.Boolean, default=False)
    review_endpoint_accessible = db.Column(db.Boolean, default=False)
    reply_capability = db.Column(db.String(20), default='disabled')
    blocking_reason = db.Column(db.Text)


# ─── OAUTH STATE ─────────────────────────────────────────
class OAuthState(db.Model):
    __tablename__ = 'oauth_states'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    nonce_hash = db.Column(db.String(128), nullable=False, unique=True, index=True)
    user_id = db.Column(db.String(36), nullable=False)
    tenant_id = db.Column(db.String(36), nullable=False)
    business_id = db.Column(db.String(36), nullable=False)
    connection_id = db.Column(db.String(36), nullable=False)
    redirect_intent = db.Column(db.String(200), default='/google/accounts')
    expires_at = db.Column(db.DateTime(timezone=True), nullable=False)
    consumed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=_now)


# ─── IMPORT BATCH ───────────────────────────────────────
class ImportBatch(db.Model):
    __tablename__ = 'import_batches'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'), nullable=False)
    source = db.Column(db.String(50))  # outscraper_csv, outscraper_xlsx, manual
    file_name = db.Column(db.String(300))
    status = db.Column(db.String(50), default='pending')  # pending, processing, completed, failed
    rows_total = db.Column(db.Integer, default=0)
    rows_valid = db.Column(db.Integer, default=0)
    rows_invalid = db.Column(db.Integer, default=0)
    duplicates = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    error_report_ref = db.Column(db.Text)


# ─── REVIEW ─────────────────────────────────────────────
class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'), nullable=False)
    outlet_id = db.Column(db.String(36), db.ForeignKey('outlets.id'), nullable=True)
    source = db.Column(db.String(50))  # google_api, outscraper, pubsub
    source_review_name = db.Column(db.String(500))  # API resource name
    review_id = db.Column(db.String(200))
    reviewer_display_name = db.Column(db.String(200))
    reviewer_is_anonymous = db.Column(db.Boolean, default=False)
    star_rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    has_text = db.Column(db.Boolean, default=False)
    owner_reply_text = db.Column(db.Text)
    owner_reply_date = db.Column(db.DateTime(timezone=True))
    source_url = db.Column(db.Text)
    create_time = db.Column(db.DateTime(timezone=True))
    update_time = db.Column(db.DateTime(timezone=True))
    source_visibility_status = db.Column(db.String(50), default='available')
    current_version = db.Column(db.Integer, default=1)
    raw_payload_hash = db.Column(db.String(64))
    qualitative_analysis_status = db.Column(db.String(50), default='not_applicable')
    review_updated = db.Column(db.Boolean, default=False)
    analysis_reassessment_required = db.Column(db.Boolean, default=False)
    last_seen_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)

    __table_args__ = (
        db.UniqueConstraint('tenant_id', 'source', 'source_review_name', name='uq_review_source'),
    )


# ─── REVIEW VERSION ─────────────────────────────────────
class ReviewVersion(db.Model):
    __tablename__ = 'review_versions'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    review_pk = db.Column(db.String(36), db.ForeignKey('reviews.id'), nullable=False)
    version = db.Column(db.Integer, nullable=False)
    star_rating = db.Column(db.Integer)
    comment = db.Column(db.Text)
    source_update_time = db.Column(db.DateTime(timezone=True))
    raw_payload_hash = db.Column(db.String(64))
    captured_at = db.Column(db.DateTime(timezone=True), default=_now)


# ─── REVIEW ANALYSIS ────────────────────────────────────
class ReviewAnalysis(db.Model):
    __tablename__ = 'review_analyses'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    review_pk = db.Column(db.String(36), db.ForeignKey('reviews.id'), nullable=False)
    analysis_version = db.Column(db.Integer, default=1)
    model_name = db.Column(db.String(100))
    policy_version = db.Column(db.String(50))
    sentiment = db.Column(db.String(20))  # positive, neutral, negative, mixed, not_applicable
    topics_json = db.Column(db.JSON)
    issue_summary = db.Column(db.Text)
    urgency = db.Column(db.String(20))  # low, medium, high, critical
    reputation_risk = db.Column(db.String(20))  # minimal, contained, elevated, severe
    repeat_pattern_candidate = db.Column(db.Boolean, default=False)
    responsible_role = db.Column(db.String(50))
    recommended_public_response_intent_json = db.Column(db.JSON)
    recommended_internal_action_json = db.Column(db.JSON)
    human_review_required = db.Column(db.Boolean, default=False)
    confidence_json = db.Column(db.JSON)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)


# ─── REVIEW REPLY ───────────────────────────────────────
class ReviewReply(db.Model):
    __tablename__ = 'review_replies'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    review_pk = db.Column(db.String(36), db.ForeignKey('reviews.id'), nullable=False)
    draft_version = db.Column(db.Integer, default=1)
    draft_text = db.Column(db.Text)
    route = db.Column(db.String(50))  # auto, approval, escalation
    approval_status = db.Column(db.String(50))  # pending, approved, rejected
    approved_text = db.Column(db.Text)
    publication_status = db.Column(db.String(50))  # draft, published, failed, rejected
    google_reply_update_time = db.Column(db.DateTime(timezone=True))
    review_reply_state = db.Column(db.String(50))
    policy_violation = db.Column(db.Text)
    review_reply_url = db.Column(db.Text)
    published_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    published_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)


# ─── APPROVAL ───────────────────────────────────────────
class Approval(db.Model):
    __tablename__ = 'approvals'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    review_reply_id = db.Column(db.String(36), db.ForeignKey('review_replies.id'), nullable=False)
    decision = db.Column(db.String(50))  # approved, rejected, edited
    actor_user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    edited_text = db.Column(db.Text)
    note = db.Column(db.Text)
    decided_at = db.Column(db.DateTime(timezone=True))


# ─── ISSUE ──────────────────────────────────────────────
class Issue(db.Model):
    __tablename__ = 'issues'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'), nullable=False)
    outlet_id = db.Column(db.String(36), db.ForeignKey('outlets.id'), nullable=True)
    review_id = db.Column(db.String(36), db.ForeignKey('reviews.id'), nullable=True)
    pattern_id = db.Column(db.String(36))
    title = db.Column(db.String(300), nullable=False)
    issue_summary = db.Column(db.Text)
    category = db.Column(db.String(50))
    urgency = db.Column(db.String(20))  # low, medium, high, critical
    reputation_risk = db.Column(db.String(20))
    source_facts = db.Column(db.JSON)
    ai_assessment = db.Column(db.JSON)
    primary_owner_role = db.Column(db.String(50))
    assigned_user_id = db.Column(db.String(36), db.ForeignKey('users.id'))
    supporting_roles = db.Column(db.JSON)
    status = db.Column(db.String(50), default='new')  # new, under_review, assigned, in_progress, resolved, closed, reopened
    due_at = db.Column(db.DateTime(timezone=True))
    action_checklist = db.Column(db.JSON)
    internal_notes = db.Column(db.JSON)
    evidence_attachments = db.Column(db.JSON)
    resolution_summary = db.Column(db.Text)
    closed_by = db.Column(db.String(36), db.ForeignKey('users.id'))
    closed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)
    resolved_at = db.Column(db.DateTime(timezone=True))


# ─── ISSUE PATTERN ───────────────────────────────────────
class IssuePattern(db.Model):
    __tablename__ = 'issue_patterns'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    business_id = db.Column(db.String(36), db.ForeignKey('businesses.id'), nullable=False)
    parent_issue_id = db.Column(db.String(36), db.ForeignKey('issues.id'), nullable=True)
    pattern_key = db.Column(db.String(100), nullable=False)  # e.g. 'wait_time', 'food_quality'
    title = db.Column(db.String(300))
    description = db.Column(db.Text)
    trend = db.Column(db.String(20), default='stable')  # stable, increasing, decreasing
    outlet_specific = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
    updated_at = db.Column(db.DateTime(timezone=True), default=_now, onupdate=_now)


# ─── PATTERN REVIEW (supporting reviews) ─────────────────
class PatternReview(db.Model):
    __tablename__ = 'pattern_reviews'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    pattern_id = db.Column(db.String(36), db.ForeignKey('issue_patterns.id'), nullable=False)
    review_id = db.Column(db.String(36), db.ForeignKey('reviews.id'), nullable=False)
    issue_id = db.Column(db.String(36), db.ForeignKey('issues.id'), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), default=_now)

    __table_args__ = (
        db.UniqueConstraint('pattern_id', 'review_id', name='uq_pattern_review'),
    )


# ─── PUBSUB EVENT ───────────────────────────────────────
class PubsubEvent(db.Model):
    __tablename__ = 'pubsub_events'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    google_account_id = db.Column(db.String(200))
    event_type = db.Column(db.String(50))  # NEW_REVIEW, UPDATED_REVIEW
    review_name = db.Column(db.String(500))
    location_name = db.Column(db.String(500))
    message_id = db.Column(db.String(200))
    publish_time = db.Column(db.DateTime(timezone=True))
    payload_hash = db.Column(db.String(64))
    processing_status = db.Column(db.String(50), default='received')
    retry_count = db.Column(db.Integer, default=0)
    received_at = db.Column(db.DateTime(timezone=True), default=_now)
    processed_at = db.Column(db.DateTime(timezone=True))

    __table_args__ = (
        db.UniqueConstraint('google_account_id', 'message_id', name='uq_pubsub_message'),
    )


# ─── AUDIT LOG ──────────────────────────────────────────
class AuditLog(db.Model):
    __tablename__ = 'audit_logs'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=True, index=True)
    actor_type = db.Column(db.String(50))  # user, system, cron
    actor_id = db.Column(db.String(36))
    action = db.Column(db.String(100), nullable=False)
    entity_type = db.Column(db.String(50))
    entity_id = db.Column(db.String(36))
    before_json = db.Column(db.JSON)
    after_json = db.Column(db.JSON)
    reason = db.Column(db.Text)
    trace_id = db.Column(db.String(36))
    created_at = db.Column(db.DateTime(timezone=True), default=_now)


# ─── REVIEW RAW PAYLOAD ─────────────────────────────────
class ReviewRawPayload(db.Model):
    __tablename__ = 'review_raw_payloads'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    business_id = db.Column(db.String(36), nullable=False, index=True)
    review_pk = db.Column(db.String(36), db.ForeignKey('reviews.id'), nullable=True)
    source = db.Column(db.String(50))
    source_account_id = db.Column(db.String(200))
    source_location_id = db.Column(db.String(200))
    source_review_name = db.Column(db.String(500))
    raw_payload_hash = db.Column(db.String(64), index=True)
    raw_payload = db.Column(db.JSON)
    ingested_at = db.Column(db.DateTime(timezone=True), default=_now)
    import_batch_id = db.Column(db.String(36), db.ForeignKey('import_batches.id'), nullable=True)
    sync_id = db.Column(db.String(36), nullable=True)


# ─── SYNC REPORT ─────────────────────────────────────────
class SyncReport(db.Model):
    __tablename__ = 'sync_reports'

    id = db.Column(db.String(36), primary_key=True, default=_uuid)
    tenant_id = db.Column(db.String(36), nullable=False, index=True)
    business_id = db.Column(db.String(36), nullable=False)
    account_id = db.Column(db.String(200))
    source = db.Column(db.String(50))
    locations_requested = db.Column(db.Integer, default=0)
    locations_succeeded = db.Column(db.Integer, default=0)
    locations_failed = db.Column(db.Integer, default=0)
    reviews_received = db.Column(db.Integer, default=0)
    reviews_created = db.Column(db.Integer, default=0)
    reviews_updated = db.Column(db.Integer, default=0)
    reviews_unchanged = db.Column(db.Integer, default=0)
    rating_only_reviews = db.Column(db.Integer, default=0)
    duplicates_skipped = db.Column(db.Integer, default=0)
    analysis_jobs_created = db.Column(db.Integer, default=0)
    errors = db.Column(db.JSON)
    started_at = db.Column(db.DateTime(timezone=True))
    completed_at = db.Column(db.DateTime(timezone=True))
    created_at = db.Column(db.DateTime(timezone=True), default=_now)
