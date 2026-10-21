from datetime import date, timedelta

import pytest

from taskboard.services import is_overdue

# --- create / read / delete -----------------------------------------------------


def test_create_task_with_defaults(make_task):
    task = make_task(title="Write docs")
    assert task["title"] == "Write docs"
    assert task["status"] == "todo"
    assert task["priority"] == "medium"
    assert task["due_date"] is None
    assert task["tags"] == []
    assert task["is_overdue"] is False


def test_create_task_normalizes_tags(make_task):
    task = make_task(tags=["Bug", " bug ", "UI", ""])
    assert task["tags"] == ["bug", "ui"]


def test_create_task_validation(client, project):
    cases = [
        ({"title": "x"}, "project_id"),
        ({"project_id": project["id"]}, "title"),
        ({"project_id": project["id"], "title": "x", "status": "blocked"}, "status"),
        ({"project_id": project["id"], "title": "x", "priority": "urgent"}, "priority"),
        (
            {"project_id": project["id"], "title": "x", "due_date": "2026-02-30"},
            "due_date",
        ),
        ({"project_id": project["id"], "title": "x", "tags": "bug"}, "tags"),
    ]
    for payload, field in cases:
        resp = client.post("/tasks", json=payload)
        assert resp.status_code == 400, payload
        assert field in resp.get_json()["error"]


def test_create_task_for_missing_project(client):
    resp = client.post("/tasks", json={"project_id": 999, "title": "x"})
    assert resp.status_code == 404


def test_get_and_delete_task(client, make_task):
    task = make_task()
    assert client.get(f"/tasks/{task['id']}").status_code == 200
    assert client.delete(f"/tasks/{task['id']}").status_code == 204
    assert client.get(f"/tasks/{task['id']}").status_code == 404


# --- update ---------------------------------------------------------------------


def test_update_task_title(client, make_task):
    task = make_task(title="Old", priority="high")
    resp = client.patch(f"/tasks/{task['id']}", json={"title": "New"})
    assert resp.status_code == 200
    updated = resp.get_json()
    assert updated["title"] == "New"
    assert updated["priority"] == "high"


def test_update_task_tags(client, make_task):
    task = make_task(tags=["a"])
    resp = client.patch(f"/tasks/{task['id']}", json={"tags": ["b", "c"]})
    assert resp.get_json()["tags"] == ["b", "c"]


def test_update_task_status_keeps_tags(client, make_task):
    task = make_task(tags=["android", "bug"])
    resp = client.patch(f"/tasks/{task['id']}", json={"status": "done"})
    assert resp.status_code == 200
    assert resp.get_json()["status"] == "done"
    assert client.get(f"/tasks/{task['id']}").get_json()["tags"] == ["android", "bug"]


def test_update_task_empty_tags_clears_tags(client, make_task):
    task = make_task(tags=["android", "bug"])
    resp = client.patch(f"/tasks/{task['id']}", json={"tags": []})
    assert resp.status_code == 200
    assert client.get(f"/tasks/{task['id']}").get_json()["tags"] == []


def test_update_task_tags_replaces_existing(client, make_task):
    task = make_task(tags=["android", "bug"])
    resp = client.patch(f"/tasks/{task['id']}", json={"tags": ["x"]})
    assert resp.status_code == 200
    assert client.get(f"/tasks/{task['id']}").get_json()["tags"] == ["x"]


def test_update_task_rejects_invalid_status(client, make_task):
    task = make_task()
    resp = client.patch(f"/tasks/{task['id']}", json={"status": "archived"})
    assert resp.status_code == 400


# --- list / filter / sort ---------------------------------------------------------


def test_list_tasks_newest_first(client, make_task):
    first = make_task(title="first")
    second = make_task(title="second")
    items = client.get("/tasks").get_json()["items"]
    assert [t["id"] for t in items] == [second["id"], first["id"]]


def test_list_tasks_filter_by_status(client, make_task):
    make_task(status="todo")
    done = make_task(status="done")
    items = client.get("/tasks?status=done").get_json()["items"]
    assert [t["id"] for t in items] == [done["id"]]


def test_list_tasks_search(client, make_task):
    match = make_task(title="Fix payment bug")
    make_task(title="Write release notes")
    items = client.get("/tasks?q=payment").get_json()["items"]
    assert [t["id"] for t in items] == [match["id"]]


def _search_ids(client, q):
    return [t["id"] for t in client.get("/tasks", query_string={"q": q}).get_json()["items"]]


def test_list_tasks_search_is_case_insensitive(client, make_task):
    match = make_task(title="Fix Login crash on Android 14")
    make_task(title="Write release notes")
    assert _search_ids(client, "login") == [match["id"]]


def test_list_tasks_search_same_result_regardless_of_case(client, make_task):
    make_task(title="Login with Google")
    make_task(title="Biometric login (Face ID)")
    make_task(title="Write release notes")
    expected = _search_ids(client, "Login")
    assert len(expected) == 2
    assert _search_ids(client, "login") == expected
    assert _search_ids(client, "LOGIN") == expected


def test_list_tasks_search_description_is_case_insensitive(client, make_task):
    match = make_task(title="Auth work", description="Investigate the LOGIN timeout")
    make_task(title="Write release notes")
    assert _search_ids(client, "login") == [match["id"]]


def test_list_tasks_search_treats_wildcards_literally(client, make_task):
    match = make_task(title="Raise coverage to 90%")
    make_task(title="Write release notes")
    assert _search_ids(client, "%") == [match["id"]]
    assert _search_ids(client, "_") == []


def test_list_tasks_search_non_ascii_case_is_not_folded(client, make_task):
    # Known limitation: SQLite's built-in lower() only folds ASCII letters.
    make_task(title="Éclair recipe")
    assert _search_ids(client, "éclair") == []
    assert len(_search_ids(client, "Éclair")) == 1


def test_list_tasks_sort_by_due_date(client, make_task):
    later = make_task(due_date="2030-05-01")
    no_date = make_task()
    sooner = make_task(due_date="2030-01-01")
    items = client.get("/tasks?sort=due_date").get_json()["items"]
    assert [t["id"] for t in items] == [sooner["id"], later["id"], no_date["id"]]


def test_list_tasks_sort_by_priority_high_medium_low(client, make_task):
    low = make_task(title="low task", priority="low")
    high = make_task(title="high task", priority="high")
    medium = make_task(title="medium task", priority="medium")
    items = client.get("/tasks?sort=priority").get_json()["items"]
    assert [t["id"] for t in items] == [high["id"], medium["id"], low["id"]]


def test_list_tasks_sort_by_priority_due_date_within_priority(client, make_task):
    high_later = make_task(title="high later", priority="high", due_date="2030-05-01")
    high_no_date = make_task(title="high no date", priority="high")
    high_sooner = make_task(title="high sooner", priority="high", due_date="2030-01-01")
    medium = make_task(title="medium task", priority="medium")
    items = client.get("/tasks?sort=priority").get_json()["items"]
    assert [t["id"] for t in items] == [
        high_sooner["id"],
        high_later["id"],
        high_no_date["id"],
        medium["id"],
    ]


def test_list_tasks_sort_by_priority_pagination(client, make_task):
    low = make_task(title="low", priority="low", due_date="2030-01-01")
    medium_no_date = make_task(title="medium no date", priority="medium")
    high_later = make_task(title="high later", priority="high", due_date="2030-05-01")
    medium_dated = make_task(title="medium dated", priority="medium", due_date="2030-03-01")
    high_sooner = make_task(title="high sooner", priority="high", due_date="2030-01-01")
    expected = [
        high_sooner["id"],
        high_later["id"],
        medium_dated["id"],
        medium_no_date["id"],
        low["id"],
    ]
    ids = []
    for page in (1, 2, 3):
        body = client.get(f"/tasks?sort=priority&per_page=2&page={page}").get_json()
        if page == 1:
            assert body["pagination"]["total"] == 5
        ids += [t["id"] for t in body["items"]]
    assert ids == expected


def test_list_tasks_rejects_unknown_sort(client):
    assert client.get("/tasks?sort=title").status_code == 400


def test_list_tasks_pagination(client, make_task):
    for i in range(20):
        make_task(title=f"task {i}")
    body = client.get("/tasks?per_page=10&page=2").get_json()
    assert len(body["items"]) == 10
    assert body["pagination"] == {
        "page": 2,
        "per_page": 10,
        "total": 20,
        "pages": 2,
        "has_next": False,
    }


def test_list_tasks_pagination_partial_last_page(client, make_task):
    for i in range(23):
        make_task(title=f"task {i}")
    body = client.get("/tasks?per_page=10&page=1").get_json()
    assert body["pagination"]["pages"] == 3
    body = client.get("/tasks?per_page=10&page=2").get_json()
    assert body["pagination"]["has_next"] is True
    resp = client.get("/tasks?per_page=10&page=3")
    assert resp.status_code == 200
    body = resp.get_json()
    assert len(body["items"]) == 3
    assert body["pagination"]["has_next"] is False


@pytest.mark.parametrize("per_page", [1, 3, 7, 10, 23, 50])
def test_list_tasks_pagination_reaches_every_task(client, make_task, per_page):
    created = [make_task(title=f"task {i}")["id"] for i in range(23)]
    collected = []
    page = 1
    while True:
        resp = client.get(f"/tasks?per_page={per_page}&page={page}")
        assert resp.status_code == 200
        body = resp.get_json()
        collected.extend(item["id"] for item in body["items"])
        if not body["pagination"]["has_next"]:
            break
        page += 1
    assert sorted(collected) == sorted(created)
    assert len(collected) == len(set(collected)) == 23


def test_list_tasks_pagination_empty_list(client):
    resp = client.get("/tasks?per_page=10&page=1")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["items"] == []
    assert body["pagination"] == {
        "page": 1,
        "per_page": 10,
        "total": 0,
        "pages": 1,
        "has_next": False,
    }


def test_list_tasks_pagination_page_past_last_is_400(client, make_task):
    for i in range(23):
        make_task(title=f"task {i}")
    assert client.get("/tasks?per_page=10&page=4").status_code == 400


# --- overdue ----------------------------------------------------------------------


def test_is_overdue_past_due_date():
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    assert is_overdue({"status": "todo", "due_date": yesterday}) is True


def test_is_overdue_future_due_date():
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    assert is_overdue({"status": "todo", "due_date": tomorrow}) is False


def test_done_task_is_never_overdue():
    assert is_overdue({"status": "done", "due_date": "2000-01-01"}) is False


def test_overdue_endpoint(client, make_task):
    yesterday = (date.today() - timedelta(days=1)).isoformat()
    late = make_task(due_date=yesterday)
    make_task(due_date=yesterday, status="done")
    make_task(due_date="2999-01-01")
    items = client.get("/tasks/overdue").get_json()["items"]
    assert [t["id"] for t in items] == [late["id"]]
