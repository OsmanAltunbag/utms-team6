import enum

from sqlalchemy import Enum as SAEnum


class UserRole(str, enum.Enum):
    APPLICANT = "APPLICANT"
    STUDENT_AFFAIRS = "STUDENT_AFFAIRS"
    TRANSFER_COMMISSION = "TRANSFER_COMMISSION"
    YDYO = "YDYO"
    DEAN_OFFICE = "DEAN_OFFICE"
    SYSTEM_ADMIN = "SYSTEM_ADMIN"


class AppStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ENGLISH_REVIEW = "ENGLISH_REVIEW"
    DEPT_EVAL = "DEPT_EVAL"
    RANKING = "RANKING"
    ANNOUNCED = "ANNOUNCED"
    REJECTED = "REJECTED"
    CORRECTION_REQUESTED = "CORRECTION_REQUESTED"


class DocType(str, enum.Enum):
    TRANSCRIPT = "TRANSCRIPT"
    YKS_RESULT = "YKS_RESULT"
    LANGUAGE_CERT = "LANGUAGE_CERT"
    ID_COPY = "ID_COPY"
    MILITARY_STATUS = "MILITARY_STATUS"
    DISCIPLINE_RECORD = "DISCIPLINE_RECORD"
    OTHER = "OTHER"


class DocStatus(str, enum.Enum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    CORRECTION_REQUESTED = "CORRECTION_REQUESTED"


class NotifChannel(str, enum.Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    IN_APP = "IN_APP"


class NotifStatus(str, enum.Enum):
    PENDING = "PENDING"
    SENT = "SENT"
    FAILED = "FAILED"


class RankStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    APPROVED = "APPROVED"
    PUBLISHED = "PUBLISHED"


class IntibakStatus(str, enum.Enum):
    DRAFT = "DRAFT"
    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"


# SQLAlchemy ENUM type definitions — reused in models and kept in sync with PG types
user_role_type = SAEnum(UserRole, name="user_role", create_constraint=True)
app_status_type = SAEnum(AppStatus, name="app_status", create_constraint=True)
doc_type_type = SAEnum(DocType, name="doc_type", create_constraint=True)
doc_status_type = SAEnum(DocStatus, name="doc_status", create_constraint=True)
notif_channel_type = SAEnum(NotifChannel, name="notif_channel", create_constraint=True)
notif_status_type = SAEnum(NotifStatus, name="notif_status", create_constraint=True)
rank_status_type = SAEnum(RankStatus, name="rank_status", create_constraint=True)
intibak_status_type = SAEnum(IntibakStatus, name="intibak_status", create_constraint=True)
