import sqlite3
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from taskboard import create_app
from taskboard.db import init_db
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


FROZEN_TODAY = date(2026, 3, 15)


@pytest.fixture(params=["00:01", "23:59"])
def frozen_now(request, monkeypatch):
    frozen = datetime.combine(FROZEN_TODAY, time.fromisoformat(request.param))

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return frozen

    monkeypatch.setattr("taskboard.services.datetime", FrozenDatetime)
    return frozen


def test_task_due_today_is_not_overdue(client, make_task, frozen_now):
    task = make_task(due_date=FROZEN_TODAY.isoformat())
    assert client.get(f"/tasks/{task['id']}").get_json()["is_overdue"] is False
    items = client.get("/tasks/overdue").get_json()["items"]
    assert task["id"] not in [t["id"] for t in items]


def test_task_due_yesterday_is_overdue(client, make_task, frozen_now):
    task = make_task(due_date=(FROZEN_TODAY - timedelta(days=1)).isoformat())
    assert client.get(f"/tasks/{task['id']}").get_json()["is_overdue"] is True
    items = client.get("/tasks/overdue").get_json()["items"]
    assert [t["id"] for t in items] == [task["id"]]


def test_task_responses_hide_deleted_at(client, make_task):
    task = make_task()
    assert "deleted_at" not in task
    assert "deleted_at" not in client.get(f"/tasks/{task['id']}").get_json()


# --- soft delete ------------------------------------------------------------------


def _db_row(app, sql, params=()):
    from taskboard.db import get_db

    with app.app_context():
        return get_db().execute(sql, params).fetchall()


def test_delete_task_keeps_row_and_tags(app, client, make_task):
    task = make_task(tags=["a", "b"])
    assert client.delete(f"/tasks/{task['id']}").status_code == 204
    rows = _db_row(app, "SELECT deleted_at, updated_at FROM tasks WHERE id = ?", (task["id"],))
    assert len(rows) == 1
    assert rows[0]["deleted_at"] is not None
    assert rows[0]["updated_at"] == task["updated_at"]
    tags = _db_row(app, "SELECT tag FROM task_tags WHERE task_id = ? ORDER BY tag", (task["id"],))
    assert [r["tag"] for r in tags] == ["a", "b"]


def test_deleted_task_is_not_found(client, make_task):
    task = make_task()
    client.delete(f"/tasks/{task['id']}")
    expected = {"error": f"task {task['id']} not found"}
    for resp in (
        client.get(f"/tasks/{task['id']}"),
        client.patch(f"/tasks/{task['id']}", json={"title": "x"}),
        client.delete(f"/tasks/{task['id']}"),
    ):
        assert resp.status_code == 404
        assert resp.get_json() == expected


def test_deleted_task_absent_from_list_and_total(client, make_task):
    keep = make_task(title="keep")
    gone = make_task(title="gone")
    client.delete(f"/tasks/{gone['id']}")
    body = client.get("/tasks").get_json()
    assert [t["id"] for t in body["items"]] == [keep["id"]]
    assert body["pagination"]["total"] == 1


def test_deleted_task_absent_from_overdue(client, make_task):
    task = make_task(due_date="2000-01-01")
    assert [t["id"] for t in client.get("/tasks/overdue").get_json()["items"]] == [task["id"]]
    client.delete(f"/tasks/{task['id']}")
    assert client.get("/tasks/overdue").get_json()["items"] == []


# --- filter by tag (T1) ----------------------------------------------------------


def _ids(resp):
    return [t["id"] for t in resp.get_json()["items"]]


@pytest.fixture
def tagged(make_task):
    return {
        "a": make_task(title="A", tags=["bug", "ui"]),
        "b": make_task(title="B", tags=["bug"]),
        "c": make_task(title="C", tags=[]),
    }


def test_t1_1_tag_filter_returns_matching_tasks(client, tagged):
    resp = client.get("/tasks?tag=bug")
    assert resp.status_code == 200
    assert set(_ids(resp)) == {tagged["a"]["id"], tagged["b"]["id"]}
    assert resp.get_json()["pagination"]["total"] == 2


def test_t1_4_t1_5_multiple_tags_are_anded(client, make_task, tagged):
    d = make_task(title="D", tags=["ui"])
    for query in ("tag=bug&tag=ui", "tag=ui&tag=bug"):
        resp = client.get(f"/tasks?{query}")
        assert resp.status_code == 200
        assert _ids(resp) == [tagged["a"]["id"]]
        assert resp.get_json()["pagination"]["total"] == 1
    assert d["id"] not in _ids(client.get("/tasks?tag=bug&tag=ui"))


@pytest.mark.parametrize("query", ["tag=Bug", "tag=%20bug%20", "tag=%09BUG%0A"])
def test_t1_7_t1_8_tag_is_normalised(client, tagged, query):
    resp = client.get(f"/tasks?{query}")
    assert resp.status_code == 200
    assert set(_ids(resp)) == {tagged["a"]["id"], tagged["b"]["id"]}
    assert resp.get_json()["pagination"]["total"] == 2


def test_t1_13_duplicate_tags_count_once(client, tagged):
    for query in ("tag=bug&tag=BUG", "tag=bug&tag=%20Bug%20&tag=bug"):
        resp = client.get(f"/tasks?{query}")
        assert set(_ids(resp)) == {tagged["a"]["id"], tagged["b"]["id"]}
        assert resp.get_json()["pagination"]["total"] == 2


def test_t1_15_unknown_tag_returns_empty(client, tagged):
    resp = client.get("/tasks?tag=nope")
    assert resp.status_code == 200
    assert resp.get_json()["items"] == []
    assert resp.get_json()["pagination"]["total"] == 0


def test_t1_18_filtered_tasks_keep_full_tags(client, tagged):
    by_id = {t["id"]: t for t in client.get("/tasks?tag=bug").get_json()["items"]}
    assert by_id[tagged["a"]["id"]]["tags"] == ["bug", "ui"]
    assert by_id[tagged["b"]["id"]]["tags"] == ["bug"]


def test_t1_20_tag_combines_with_project_id(client, make_task, project):
    a = make_task(tags=["bug"])
    other = client.post("/projects", json={"name": "Other"}).get_json()
    make_task(project_id=other["id"], tags=["bug"])
    resp = client.get(f"/tasks?tag=bug&project_id={project['id']}")
    assert _ids(resp) == [a["id"]]
    assert resp.get_json()["pagination"]["total"] == 1


def test_t1_22_tag_combines_with_status(client, make_task):
    make_task(tags=["bug"], status="todo")
    b = make_task(tags=["bug"], status="done")
    make_task(tags=[], status="done")
    resp = client.get("/tasks?tag=bug&status=done")
    assert _ids(resp) == [b["id"]]
    assert resp.get_json()["pagination"]["total"] == 1


def test_t1_23_tag_combines_with_q(client, make_task):
    a = make_task(title="Login crash", tags=["bug"])
    make_task(title="Docs", tags=["bug"])
    make_task(title="Login form", tags=[])
    resp = client.get("/tasks?tag=bug&q=login")
    assert _ids(resp) == [a["id"]]
    assert resp.get_json()["pagination"]["total"] == 1


def test_t1_24_tag_combines_with_sort(client, make_task):
    low = make_task(tags=["bug"], priority="low")
    high = make_task(tags=["bug"], priority="high")
    med = make_task(tags=["bug"], priority="medium")
    make_task(tags=[], priority="high")
    assert _ids(client.get("/tasks?tag=bug&sort=priority")) == [high["id"], med["id"], low["id"]]


def test_t1_25_tag_combines_with_pagination(client, make_task):
    for _ in range(3):
        make_task(tags=["bug"])
    for _ in range(2):
        make_task(tags=[])
    body = client.get("/tasks?tag=bug&per_page=2&page=2").get_json()
    assert len(body["items"]) == 1
    assert body["pagination"] == {"page": 2, "per_page": 2, "total": 3, "pages": 2, "has_next": False}


def test_t1_27_out_of_range_page_uses_filtered_total(client, make_task):
    make_task(tags=["bug"])
    for _ in range(15):
        make_task(tags=[])
    resp = client.get("/tasks?tag=bug&page=2")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "page 2 is out of range (1-1)"}


def test_t1_29_soft_deleted_tasks_not_returned_or_counted(client, make_task):
    a = make_task(tags=["bug"])
    b = make_task(tags=["bug"])
    client.delete(f"/tasks/{b['id']}")
    resp = client.get("/tasks?tag=bug")
    assert _ids(resp) == [a["id"]]
    assert resp.get_json()["pagination"]["total"] == 1


@pytest.mark.parametrize("query", ["tag=", "tag=%20", "tag", "tag=bug&tag=%20%09", "tag=&page=99"])
def test_t1_31_t1_32_blank_tag_is_rejected(client, tagged, query):
    resp = client.get(f"/tasks?{query}")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "tag must not be empty"}


def test_t1_35_eleven_distinct_tags_rejected(client):
    query = "&".join(f"tag=t{i}" for i in range(1, 12))
    resp = client.get(f"/tasks?{query}")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "at most 10 tags can be filtered"}


def test_t1_36_ten_distinct_tags_with_duplicates_allowed(client):
    query = "&".join(f"tag=t{i}" for i in range(1, 11)) + "&tag=T1&tag=%20t2%20"
    assert client.get(f"/tasks?{query}").status_code == 200


def test_t1_38_blank_checked_before_too_many(client):
    query = "&".join(f"tag=t{i}" for i in range(1, 12)) + "&tag="
    assert client.get(f"/tasks?{query}").get_json() == {"error": "tag must not be empty"}


def test_t1_39_t1_40_existing_status_error_wins(client, tagged):
    expected = client.get("/tasks?status=bogus")
    assert expected.status_code == 400
    for query in ("tag=bug&status=bogus", "tag=&status=bogus"):
        resp = client.get(f"/tasks?{query}")
        assert resp.status_code == 400
        assert resp.get_json() == expected.get_json()


def test_t1_44_without_tag_behaves_as_before(client, make_task):
    a = make_task(tags=["bug"])
    c = make_task(tags=[])
    body = client.get("/tasks").get_json()
    assert {t["id"] for t in body["items"]} == {a["id"], c["id"]}
    assert set(body) == {"items", "pagination"}
    assert set(body["pagination"]) == {"page", "per_page", "total", "pages", "has_next"}
    assert {"tags", "is_overdue", "comment_count"} <= set(body["items"][0])


# --- sort=comments (#58) --------------------------------------------------------

SORT_ERROR = "sort must be one of created_at, due_date, priority, comments"


def _comment(client, task_id, n=1):
    ids = []
    for i in range(n):
        resp = client.post(f"/tasks/{task_id}/comments", json={"author": "Lan", "body": f"c{i}"})
        assert resp.status_code == 201, resp.get_json()
        ids.append(resp.get_json()["id"])
    return ids


def _by_comments(client, query=""):
    resp = client.get(f"/tasks?sort=comments{query}")
    assert resp.status_code == 200, resp.get_json()
    return resp.get_json()


def _body_ids(body):
    return [item["id"] for item in body["items"]]


def _body_counts(body):
    return [item["comment_count"] for item in body["items"]]


def test_sort_comments_t1_1_sort_comments_orders_most_first(client, make_task):
    a, b, c = make_task(title="A"), make_task(title="B"), make_task(title="C")
    _comment(client, b["id"], 2)
    _comment(client, c["id"], 1)
    body = _by_comments(client)
    assert _body_ids(body) == [b["id"], c["id"], a["id"]]
    assert _body_counts(body) == [2, 1, 0]


def test_sort_comments_t1_2_sort_comments_zero_comments_fall_back_to_default_order(client, make_task):
    x, y = make_task(title="X"), make_task(title="Y")
    body = _by_comments(client)
    assert _body_ids(body) == [y["id"], x["id"]]
    assert _body_counts(body) == [0, 0]


def test_sort_comments_t1_3_sort_comments_empty_list(client):
    body = _by_comments(client)
    assert body["items"] == []
    assert body["pagination"]["total"] == 0


def test_sort_comments_t1_4_soft_deleted_comments_do_not_count(client, make_task):
    c = make_task(title="C")
    _comment(client, c["id"], 2)
    b = make_task(title="B")
    comment_ids = _comment(client, b["id"], 3)
    for cid in comment_ids[:2]:
        assert client.delete(f"/comments/{cid}").status_code == 204
    body = _by_comments(client)
    assert _body_ids(body) == [c["id"], b["id"]]
    assert _body_counts(body) == [2, 1]


def test_sort_comments_t1_5_all_comments_deleted_ties_with_zero(client, make_task):
    e = make_task(title="E")
    d = make_task(title="D")
    for cid in _comment(client, d["id"], 2):
        assert client.delete(f"/comments/{cid}").status_code == 204
    body = _by_comments(client)
    assert _body_ids(body) == [d["id"], e["id"]]
    assert _body_counts(body) == [0, 0]


def test_sort_comments_t1_6_ties_with_same_created_at_resolve_by_id_desc(client, make_task):
    p, q, r = make_task(title="P"), make_task(title="Q"), make_task(title="R")
    for task in (p, q, r):
        _comment(client, task["id"], 1)
    assert _body_ids(_by_comments(client)) == [r["id"], q["id"], p["id"]]


def test_sort_comments_t1_7_ties_order_by_created_at_before_id(app, client, make_task):
    p, q = make_task(title="P"), make_task(title="Q")
    _comment(client, p["id"], 1)
    _comment(client, q["id"], 1)
    conn = sqlite3.connect(app.config["DATABASE"])
    try:
        conn.execute("UPDATE tasks SET created_at = ? WHERE id = ?", ("2099-01-01T00:00:00", p["id"]))
        conn.commit()
    finally:
        conn.close()
    assert _body_ids(_by_comments(client)) == [p["id"], q["id"]]


def _filter_data(client, project, make_task):
    p2 = client.post("/projects", json={"name": "Other"}).get_json()
    m1 = make_task(title="fix x", status="todo", tags=["bug"])
    m2 = make_task(title="fix x again", status="todo", tags=["bug"])
    _comment(client, m1["id"], 1)
    _comment(client, m2["id"], 3)
    others = [
        make_task(project_id=p2["id"], title="fix x", status="todo", tags=["bug"]),
        make_task(title="fix x", status="done", tags=["bug"]),
        make_task(title="fix x", status="todo", tags=["ui"]),
        make_task(title="patch y", status="todo", tags=["bug"]),
    ]
    for task in others:
        _comment(client, task["id"], 5)
    return m1, m2, others


def test_sort_comments_t1_8_sort_comments_combined_with_filters(client, project, make_task):
    m1, m2, _ = _filter_data(client, project, make_task)
    body = _by_comments(client, f"&project_id={project['id']}&status=todo&tag=bug&q=x")
    assert _body_ids(body) == [m2["id"], m1["id"]]
    assert body["pagination"]["total"] == 2


def test_sort_comments_t1_9_sort_comments_with_status_keeps_total_and_ids(client, project, make_task):
    _filter_data(client, project, make_task)
    plain = client.get("/tasks?status=todo&per_page=50").get_json()
    body = _by_comments(client, "&status=todo&per_page=50")
    assert body["pagination"]["total"] == plain["pagination"]["total"]
    assert sorted(_body_ids(body)) == sorted(_body_ids(plain))
    counts = _body_counts(body)
    assert counts == sorted(counts, reverse=True)


def _five_tasks(client, make_task):
    tasks = [make_task(title=f"T{n}") for n in range(5)]
    for n, task in enumerate(tasks):
        _comment(client, task["id"], n)
    return tasks


def test_sort_comments_t1_10_sort_comments_pagination_covers_every_task_once(client, make_task):
    tasks = _five_tasks(client, make_task)
    seen, counts, sizes = [], [], []
    for page in (1, 2, 3):
        body = _by_comments(client, f"&per_page=2&page={page}")
        assert body["pagination"]["total"] == 5
        sizes.append(len(body["items"]))
        seen += _body_ids(body)
        counts += _body_counts(body)
    assert sizes == [2, 2, 1]
    assert sorted(seen) == sorted(t["id"] for t in tasks)
    assert counts == [4, 3, 2, 1, 0]


def test_sort_comments_t1_11_sort_comments_page_out_of_range(client, make_task):
    _five_tasks(client, make_task)
    resp = client.get("/tasks?sort=comments&per_page=2&page=4")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": "page 4 is out of range (1-3)"}


def test_sort_comments_t1_12_unknown_sort_lists_comments_in_error(client):
    resp = client.get("/tasks?sort=title")
    assert resp.status_code == 400
    assert resp.get_json() == {"error": SORT_ERROR}


@pytest.mark.parametrize("value", ["Comments", "", "-comments", "comment"])
def test_sort_comments_t1_13_near_miss_sort_values_return_400(client, value):
    resp = client.get("/tasks", query_string={"sort": value})
    assert resp.status_code == 400
    assert resp.get_json() == {"error": SORT_ERROR}


def test_sort_comments_t1_14_repeated_sort_uses_first_value(client, make_task):
    a, b = make_task(title="A"), make_task(title="B")
    _comment(client, a["id"], 2)
    resp = client.get("/tasks?sort=comments&sort=title")
    assert resp.status_code == 200
    assert _body_ids(resp.get_json()) == [a["id"], b["id"]]
    assert client.get("/tasks?sort=title&sort=comments").status_code == 400


def test_sort_comments_t1_15_list_comment_count_matches_detail(client, make_task):
    make_task(title="A")
    b = make_task(title="B")
    c = make_task(title="C")
    deleted = _comment(client, b["id"], 3)[0]
    assert client.delete(f"/comments/{deleted}").status_code == 204
    _comment(client, c["id"], 1)
    body = _by_comments(client)
    assert len(body["items"]) == 3
    for item in body["items"]:
        detail = client.get(f"/tasks/{item['id']}").get_json()
        assert item["comment_count"] == detail["comment_count"]


def test_sort_comments_t1_16_soft_deleted_tasks_not_listed(client, make_task):
    t = make_task(title="T")
    _comment(client, t["id"], 5)
    assert client.delete(f"/tasks/{t['id']}").status_code == 204
    u = make_task(title="U")
    _comment(client, u["id"], 1)
    body = _by_comments(client)
    assert _body_ids(body) == [u["id"]]
    assert body["pagination"]["total"] == 1


def _comment_selects(client, url):
    statements = []
    original = sqlite3.connect

    def traced_connect(*args, **kwargs):
        conn = original(*args, **kwargs)
        conn.set_trace_callback(statements.append)
        return conn

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(sqlite3, "connect", traced_connect)
        assert client.get(url).status_code == 200
    return [s for s in statements if "SELECT" in s.upper() and "task_comments" in s]


def test_sort_comments_t1_18_existing_sorts_run_one_task_comments_select(client, make_task):
    for n in range(3):
        _comment(client, make_task(title=f"T{n}")["id"], 1)
    for url in ("/tasks", "/tasks?sort=due_date", "/tasks?sort=priority"):
        assert len(_comment_selects(client, url)) == 1, url


def test_sort_comments_t1_19_sort_comments_has_no_n_plus_one(client, make_task, tmp_path):
    for n in range(3):
        _comment(client, make_task(title=f"T{n}")["id"], 1)
    small = len(_comment_selects(client, "/tasks?sort=comments"))

    big_app = create_app({"TESTING": True, "DATABASE": str(tmp_path / "big.sqlite")})
    with big_app.app_context():
        init_db()
    big = big_app.test_client()
    pid = big.post("/projects", json={"name": "Big"}).get_json()["id"]
    for n in range(10):
        task = big.post("/tasks", json={"project_id": pid, "title": f"T{n}"}).get_json()
        _comment(big, task["id"], 1)
    large = len(_comment_selects(big, "/tasks?sort=comments"))

    assert small >= 1
    assert small == large


def test_sort_comments_t1_20_readme_lists_comments_sort_value():
    readme = Path(__file__).resolve().parent.parent / "README.md"
    rows = [line for line in readme.read_text().splitlines() if line.startswith("| GET | `/tasks` |")]
    assert len(rows) == 1
    assert "`priority` \\| `comments`" in rows[0]
