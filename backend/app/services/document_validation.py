"""
Auto-validation results for staff application review — SPEC-006.
"""
from app.domain.application import Application
from app.domain.enums import DocType

_REQUIRED_DOCS = [DocType.TRANSCRIPT, DocType.YKS_RESULT, DocType.ID_COPY]
_MAX_BYTES = 5 * 1024 * 1024


def build_auto_validation_results(application: Application) -> list[dict]:
    docs_by_type = {d.doc_type: d for d in application.documents}
    results: list[dict] = []

    for doc_type in _REQUIRED_DOCS:
        doc = docs_by_type.get(doc_type)
        if doc is None:
            results.append({
                "doc_type": doc_type.value,
                "check": "UPLOADED",
                "passed": False,
                "detail": "Required document missing",
            })
            continue

        results.append({
            "doc_type": doc_type.value,
            "check": "UPLOADED",
            "passed": True,
            "detail": doc.file_name,
        })

        size_ok = doc.file_size_bytes is not None and doc.file_size_bytes <= _MAX_BYTES
        results.append({
            "doc_type": doc_type.value,
            "check": "FILE_SIZE",
            "passed": size_ok,
            "detail": (
                f"{doc.file_size_bytes} bytes"
                if doc.file_size_bytes is not None
                else "Unknown size"
            ),
        })

        has_extraction = bool(doc.extracted_data) or doc.extraction_confirmed
        results.append({
            "doc_type": doc_type.value,
            "check": "EXTRACTION",
            "passed": has_extraction,
            "detail": (
                "Data extracted"
                if has_extraction
                else "No extraction data available"
            ),
        })

    all_passed = all(r["passed"] for r in results)
    results.insert(0, {
        "doc_type": "ALL",
        "check": "OVERALL",
        "passed": all_passed,
        "detail": "All required documents valid" if all_passed else "Validation issues found",
    })
    return results
