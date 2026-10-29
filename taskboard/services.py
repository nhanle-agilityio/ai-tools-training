"""Business logic. Routes call into this module; this module calls the repository."""

import math
from datetime import datetime

from . import repository
from .errors import NotFoundError, ValidationError
from .validators import (
    VALID_STATUSES,
    validate_due_date,
    validate_new_task,
    validate_priority,
    validate_project,
    validate_status,
    validate_tags,
    validate_title,
)


def _now():
    return datetime.now().isoformat(timespec="seconds")


# --- projects -----------------------------------------------------------------


def create_project(db, data):
    fields = validate_project(data)
    if repository.get_project_by_name(db, fields["name"]) is not None:
        raise ValidationError("a project with this name already exists")
    project_id = repository.insert_project(db, fields["name"], fields["description"], _now())
    return get_project(db, project_id)


def _public(row):
    """Convert a row to a dict without internal columns."""
    data = dict(row)
    data.pop("deleted_at", None)
    return data


def get_project(db, project_id):
    row = repository.get_project(db, project_id)
    if row is None:
        raise NotFoundError(f"project {project_id} not found")
    return _public(row)


def list_projects(db):
    return [_public(row) for row in repository.list_projects(db)]


def _percentage(part, whole):
    return round(part * 100 / whole, 1) if whole else 0


def project_stats(db, project_id):
    get_project(db, project_id)
    counts = repository.count_tasks_by_status(db, project_id)
    total = sum(counts.values())
    done = counts.get("done", 0)
    in_progress = counts.get("in_progress", 0)
    return {
        "project_id": project_id,
        "total": total,
        "by_status": {status: counts.get(status, 0) for status in VALID_STATUSES},
        "completion_rate": _percentage(done, total),
        "in_progress_rate": _percentage(in_progress, total),
    }


# --- tasks --------------------------------------------------------------------


def is_overdue(task, now=None):
    if task["status"] == "done" or not task["due_date"]:
        return False
    return task["due_date"] < (now or datetime.now()).date().isoformat()


def _serialize_tasks(db, rows):
    tags = repository.get_tags(db, [row["id"] for row in rows])
    tasks = []
    for row in rows:
        task = _public(row)
        task["tags"] = tags.get(row["id"], [])
        task["is_overdue"] = is_overdue(task)
        tasks.append(task)
    return tasks


def get_task(db, task_id):
    row = repository.get_task(db, task_id)
    if row is None:
        raise NotFoundError(f"task {task_id} not found")
    return _serialize_tasks(db, [row])[0]


def create_task(db, data):
    fields = validate_new_task(data)
    get_project(db, fields["project_id"])
    task_id = repository.insert_task(db, fields, _now())
    repository.set_tags(db, task_id, fields["tags"])
    return get_task(db, task_id)


def update_task(db, task_id, data):
    if not isinstance(data, dict):
        raise ValidationError("request body must be a JSON object")
    task = get_task(db, task_id)
    fields = {
        "title": validate_title(data.get("title", task["title"])),
        "description": data.get("description", task["description"]),
        "status": validate_status(data.get("status", task["status"])),
        "priority": validate_priority(data.get("priority", task["priority"])),
        "due_date": validate_due_date(data.get("due_date", task["due_date"])),
    }
    tags = validate_tags(data["tags"]) if "tags" in data else None
    repository.update_task(db, task_id, fields, _now())
    if tags is not None:
        repository.set_tags(db, task_id, tags)
    return get_task(db, task_id)


def delete_task(db, task_id):
    get_task(db, task_id)
    repository.delete_task(db, task_id)


def paginate(total, page, per_page):
    pages = max(math.ceil(total / per_page), 1)
    if page > pages:
        raise ValidationError(f"page {page} is out of range (1-{pages})")
    return {
        "page": page,
        "per_page": per_page,
        "total": total,
        "pages": pages,
        "has_next": page < pages,
    }


def list_tasks(db, *, project_id=None, status=None, q=None, sort="created_at", page=1, per_page=10):
    if status is not None:
        validate_status(status)
    if sort not in repository.SORT_CLAUSES:
        raise ValidationError(f"sort must be one of {', '.join(repository.SORT_CLAUSES)}")
    offset = (page - 1) * per_page
    rows, total = repository.list_tasks(
        db, project_id=project_id, status=status, q=q, sort=sort, limit=per_page, offset=offset
    )
    return {"items": _serialize_tasks(db, rows), "pagination": paginate(total, page, per_page)}


def list_overdue_tasks(db, now=None):
    rows = repository.list_open_tasks_with_due_date(db)
    return [task for task in _serialize_tasks(db, rows) if is_overdue(task, now)]
