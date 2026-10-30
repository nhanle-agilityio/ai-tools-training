from flask import Blueprint, current_app, jsonify, request

from . import services
from .db import get_db
from .validators import parse_positive_int

bp = Blueprint("api", __name__)


def _json_body():
    return request.get_json(silent=True)


# --- projects -----------------------------------------------------------------


@bp.get("/projects")
def list_projects():
    return jsonify(items=services.list_projects(get_db()))


@bp.post("/projects")
def create_project():
    return jsonify(services.create_project(get_db(), _json_body())), 201


@bp.get("/projects/<int:project_id>")
def get_project(project_id):
    return jsonify(services.get_project(get_db(), project_id))


@bp.patch("/projects/<int:project_id>")
def update_project(project_id):
    return jsonify(services.update_project(get_db(), project_id, _json_body()))


@bp.delete("/projects/<int:project_id>")
def delete_project(project_id):
    services.delete_project(get_db(), project_id)
    return "", 204


@bp.get("/projects/<int:project_id>/stats")
def project_stats(project_id):
    return jsonify(services.project_stats(get_db(), project_id))


# --- tasks --------------------------------------------------------------------


@bp.get("/tasks")
def list_tasks():
    args = request.args
    per_page = min(
        parse_positive_int(args.get("per_page"), "per_page", current_app.config["DEFAULT_PER_PAGE"]),
        current_app.config["MAX_PER_PAGE"],
    )
    project_id = args.get("project_id")
    result = services.list_tasks(
        get_db(),
        project_id=parse_positive_int(project_id, "project_id", None),
        status=args.get("status"),
        q=args.get("q", "").strip() or None,
        sort=args.get("sort", "created_at"),
        page=parse_positive_int(args.get("page"), "page", 1),
        per_page=per_page,
    )
    return jsonify(result)


@bp.post("/tasks")
def create_task():
    return jsonify(services.create_task(get_db(), _json_body())), 201


@bp.get("/tasks/overdue")
def list_overdue_tasks():
    return jsonify(items=services.list_overdue_tasks(get_db()))


@bp.get("/tasks/<int:task_id>")
def get_task(task_id):
    return jsonify(services.get_task(get_db(), task_id))


@bp.patch("/tasks/<int:task_id>")
def update_task(task_id):
    return jsonify(services.update_task(get_db(), task_id, _json_body()))


@bp.delete("/tasks/<int:task_id>")
def delete_task(task_id):
    services.delete_task(get_db(), task_id)
    return "", 204


# --- comments -----------------------------------------------------------------


@bp.post("/tasks/<int:task_id>/comments")
def create_comment(task_id):
    return jsonify(services.create_comment(get_db(), task_id, _json_body())), 201


@bp.get("/comments/<int:comment_id>")
def get_comment(comment_id):
    return jsonify(services.get_comment(get_db(), comment_id))


@bp.patch("/comments/<int:comment_id>")
def update_comment(comment_id):
    return jsonify(services.update_comment(get_db(), comment_id, _json_body()))


@bp.get("/tasks/<int:task_id>/comments")
def list_comments(task_id):
    return jsonify(items=services.list_comments(get_db(), task_id))
