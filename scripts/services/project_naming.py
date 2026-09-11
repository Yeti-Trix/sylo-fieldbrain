"""Project naming: job 12345, sub-project 12345-001."""

from __future__ import annotations

import re

JOB_PATTERN = re.compile(r"^(\d{5})$")
SUB_SUFFIX_PATTERN = re.compile(r"^(\d{3})$")
SUBJOB_PATTERN = re.compile(r"^(\d{5})-(\d{3})$")


def normalize_digits(raw: str) -> str:
    return raw.strip()


def compose_subproject_name(job_number: str, sub_number: str) -> str:
    return f"{job_number}-{sub_number}"


def parse_job_number(name: str) -> str | None:
    clean = normalize_digits(name)
    job = JOB_PATTERN.match(clean)
    if job:
        return job.group(1)
    sub = SUBJOB_PATTERN.match(clean)
    if sub:
        return sub.group(1)
    return None


def parse_subproject_suffix(raw: str) -> str | None:
    """Accept 001 or 12345-001; return three-digit suffix."""
    clean = normalize_digits(raw)
    if not clean:
        return None
    suffix = SUB_SUFFIX_PATTERN.match(clean)
    if suffix:
        return suffix.group(1)
    full = SUBJOB_PATTERN.match(clean)
    if full:
        return full.group(2)
    return None


def parse_project_name(name: str) -> tuple[str | None, str | None]:
    """Return (job_number, sub_suffix) from a stored project name."""
    clean = normalize_digits(name)
    job = JOB_PATTERN.match(clean)
    if job:
        return job.group(1), None
    sub = SUBJOB_PATTERN.match(clean)
    if sub:
        return sub.group(1), sub.group(2)
    return None, None


def validate_job_number(raw: str) -> str:
    clean = normalize_digits(raw)
    if not JOB_PATTERN.match(clean):
        raise ValueError("Project number must be five digits (e.g. 12345).")
    return clean


def validate_subproject_number(raw: str, *, job_number: str) -> str:
    clean = normalize_digits(raw)
    suffix = parse_subproject_suffix(clean)
    if suffix is None:
        raise ValueError("Sub-project number must be three digits (e.g. 001) or full 12345-001.")
    full = SUBJOB_PATTERN.match(clean)
    if full and full.group(1) != job_number:
        raise ValueError(f"Sub-project {clean!r} does not match project number {job_number}.")
    return suffix
