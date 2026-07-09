from datetime import datetime, timezone

FREE_PROJECTS_PER_MONTH = 1
FREE_MATERIAL_OPTIONS = 1
PAID_MATERIAL_OPTIONS = 3


def _parse_paid_until(value: str | None):
    if not value:
        return None
    try:
        normalized = value.replace("Z", "+00:00")
        return datetime.fromisoformat(normalized)
    except ValueError:
        return None


def is_paid_active(user: dict) -> bool:
    paid_until = _parse_paid_until(user.get("paid_until"))
    if not paid_until:
        return False
    now = datetime.now(timezone.utc)
    if paid_until.tzinfo is None:
        paid_until = paid_until.replace(tzinfo=timezone.utc)
    return paid_until >= now


def get_plan_name(user: dict) -> str:
    return "paid" if is_paid_active(user) else "free"


def get_material_options_limit(user: dict) -> int:
    return PAID_MATERIAL_OPTIONS if is_paid_active(user) else FREE_MATERIAL_OPTIONS


def can_create_project(user: dict) -> bool:
    if is_paid_active(user):
        return True
    created = user.get("usage", {}).get("projects_created", 0)
    return created < FREE_PROJECTS_PER_MONTH


def get_plan_limits(user: dict) -> dict:
    if is_paid_active(user):
        return {
            "projects_per_month": None,
            "projects_per_month_label": "безлимит",
            "material_options": PAID_MATERIAL_OPTIONS,
        }
    return {
        "projects_per_month": FREE_PROJECTS_PER_MONTH,
        "projects_per_month_label": str(FREE_PROJECTS_PER_MONTH),
        "material_options": FREE_MATERIAL_OPTIONS,
    }
