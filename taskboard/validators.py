from datetime import date

from .errors import ValidationError

VALID_STATUSES = ("todo", "in_progress", "done")
VALID_PRIORITIES = ("low", "medium", "high")
MAX_TITLE_LENGTH = 200
MAX_TAGS = 10
MAX_AUTHOR_LENGTH = 100
MAX_COMMENT_BODY_LENGTH = 2000


def _require_object(data):
    if not isinstance(data, dict):
        raise ValidationError("request body must be a JSON object")


def validate_project(data):
    _require_object(data)
    name = data.get("name")
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name is required")
    description = data.get("description", "")
    if not isinstance(description, str):
        raise ValidationError("description must be a string")
    return {"name": name.strip(), "description": description}


def validate_project_update(data, project):
    """Return the full name/description pair after applying a partial update."""
    _require_object(data)
    name = data.get("name", project["name"])
    if not isinstance(name, str) or not name.strip():
        raise ValidationError("name is required")
    description = data.get("description", project["description"])
    if not isinstance(description, str):
        raise ValidationError("description must be a string")
    return {"name": name.strip(), "description": description}


def validate_title(title):
    if not isinstance(title, str) or not title.strip():
        raise ValidationError("title is required")
    title = title.strip()
    if len(title) > MAX_TITLE_LENGTH:
        raise ValidationError(f"title must be at most {MAX_TITLE_LENGTH} characters")
    return title


def validate_status(status):
    if status not in VALID_STATUSES:
        raise ValidationError(f"status must be one of {', '.join(VALID_STATUSES)}")
    return status


def validate_priority(priority):
    if priority not in VALID_PRIORITIES:
        raise ValidationError(f"priority must be one of {', '.join(VALID_PRIORITIES)}")
    return priority


def validate_due_date(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValidationError("due_date must be a YYYY-MM-DD string")
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValidationError("due_date must be a valid YYYY-MM-DD date")


def validate_tags(tags):
    if not isinstance(tags, list) or not all(isinstance(t, str) for t in tags):
        raise ValidationError("tags must be a list of strings")
    cleaned = []
    for tag in tags:
        tag = tag.strip().lower()
        if tag and tag not in cleaned:
            cleaned.append(tag)
    if len(cleaned) > MAX_TAGS:
        raise ValidationError(f"a task can have at most {MAX_TAGS} tags")
    return cleaned


def validate_new_task(data):
    _require_object(data)
    project_id = data.get("project_id")
    if not isinstance(project_id, int):
        raise ValidationError("project_id is required")
    description = data.get("description", "")
    if not isinstance(description, str):
        raise ValidationError("description must be a string")
    return {
        "project_id": project_id,
        "title": validate_title(data.get("title")),
        "description": description,
        "status": validate_status(data.get("status", "todo")),
        "priority": validate_priority(data.get("priority", "medium")),
        "due_date": validate_due_date(data.get("due_date")),
        "tags": validate_tags(data.get("tags", [])),
    }


def _validate_text(value, name, max_length):
    if not isinstance(value, str) or not value.strip():
        raise ValidationError(f"{name} is required")
    value = value.strip()
    if len(value) > max_length:
        raise ValidationError(f"{name} must be at most {max_length} characters")
    return value


def validate_new_comment(data):
    _require_object(data)
    return {
        "author": _validate_text(data.get("author"), "author", MAX_AUTHOR_LENGTH),
        "body": _validate_text(data.get("body"), "body", MAX_COMMENT_BODY_LENGTH),
    }


def validate_comment_body(value):
    return _validate_text(value, "body", MAX_COMMENT_BODY_LENGTH)


def parse_positive_int(value, name, default):
    if value is None:
        return default
    try:
        number = int(value)
    except (TypeError, ValueError):
        raise ValidationError(f"{name} must be an integer")
    if number < 1:
        raise ValidationError(f"{name} must be >= 1")
    return number
