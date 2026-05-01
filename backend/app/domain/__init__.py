"""Domain models package — import all models here so SQLAlchemy metadata is populated."""

from .academic_record import AcademicRecord
from .application import Application
from .audit import AuditLog
from .document import Document
from .eligibility import DepartmentEvaluation, DepartmentRequirement, EligibilityCheck
from .english import EnglishProficiencyReview
from .enums import (
    AppStatus,
    DocStatus,
    DocType,
    IntibakStatus,
    NotifChannel,
    NotifStatus,
    RankStatus,
    UserRole,
)
from .intibak import CourseMapping, IntibakTable
from .notification import Notification
from .period import ApplicationPeriod
from .program import Program
from .qa import Question, Reply
from .ranking import Ranking, RankingEntry
from .user import Applicant, Staff, User

__all__ = [
    # Users
    "User",
    "Applicant",
    "Staff",
    # Programs & periods
    "Program",
    "ApplicationPeriod",
    # Applications
    "Application",
    "AcademicRecord",
    "Document",
    "EligibilityCheck",
    "DepartmentRequirement",
    "DepartmentEvaluation",
    "EnglishProficiencyReview",
    # Rankings
    "Ranking",
    "RankingEntry",
    # Intibak
    "IntibakTable",
    "CourseMapping",
    # Notifications & audit
    "Notification",
    "AuditLog",
    # Q&A
    "Question",
    "Reply",
    # Enums
    "UserRole",
    "AppStatus",
    "DocType",
    "DocStatus",
    "NotifChannel",
    "NotifStatus",
    "RankStatus",
    "IntibakStatus",
]
