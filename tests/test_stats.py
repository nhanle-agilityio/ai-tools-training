from datetime import date, datetime, timedelta

from taskboard.db import get_db

EMPTY = {
    "projects": 0,
    "total": 0,
    "by_status": {"todo": 0, "in_progress": 0, "done": 0},
    "overdue": 0,
    "top_tags": [],
}


def _day(offset):
    return (date.today() + timedelta(days=offset)).isoformat()


def _stats(client, query=""):
    resp = client.get("/stats" + query)
    assert resp.status_code == 200
    return resp.get_json()


def _new_project(client, name):
    resp = client.post("/projects", json={"name": name})
    assert resp.status_code == 201
    return resp.get_json()


def _task(client, project_id, **fields):
    resp = client.post("/tasks", json={"project_id": project_id, "title": "T", **fields})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def _tagged(client, project_id, counts):
    for tag, n in counts.items():
        for _ in range(n):
            _task(client, project_id, tags=[tag])


def test_t2_1_empty_database(client):
    assert _stats(client) == EMPTY


def test_t2_2_only_deleted_project_gives_empty_body(client, project, make_task):
    make_task(tags=["bug"])
    assert client.delete(f"/projects/{project['id']}").status_code == 204
    assert _stats(client) == EMPTY


def test_t2_3_exactly_five_keys(client, make_task):
    make_task(tags=["bug"])
    assert set(_stats(client)) == {"projects", "total", "by_status", "overdue", "top_tags"}


def test_t2_4_by_status_keys_and_ints(client, make_task):
    make_task(status="done")
    by_status = _stats(client)["by_status"]
    assert set(by_status) == {"todo", "in_progress", "done"}
    assert all(isinstance(v, int) for v in by_status.values())


def test_t2_5_projects_counts_active_including_empty(client, project, make_task):
    make_task()
    make_task()
    _new_project(client, "B")
    c = _new_project(client, "C")
    assert client.delete(f"/projects/{c['id']}").status_code == 204
    assert _stats(client)["projects"] == 2


def test_t2_6_project_without_tasks(client, project):
    body = _stats(client)
    assert body["projects"] == 1
    assert body["total"] == 0


def test_t2_7_name_reused_after_delete(client, project):
    b = _new_project(client, "B")
    assert client.delete(f"/projects/{b['id']}").status_code == 204
    _new_project(client, "B")
    assert _stats(client)["projects"] == 2


def _status_data(client, a, b):
    _task(client, a, status="todo")
    _task(client, a, status="todo")
    _task(client, a, status="done")
    _task(client, b, status="in_progress")
    _task(client, b, status="todo")


def test_t2_8_total_and_by_status(client, project):
    b = _new_project(client, "B")
    _status_data(client, project["id"], b["id"])
    body = _stats(client)
    assert body["total"] == 5
    assert body["by_status"] == {"todo": 3, "in_progress": 1, "done": 1}


def test_t2_9_deleted_task_excluded(client, project):
    b = _new_project(client, "B")
    _status_data(client, project["id"], b["id"])
    extra = _task(client, project["id"], status="todo")
    assert client.delete(f"/tasks/{extra['id']}").status_code == 204
    body = _stats(client)
    assert body["total"] == 5
    assert body["by_status"]["todo"] == 3


def test_t2_10_deleted_project_tasks_excluded(client, project):
    b = _new_project(client, "B")
    _status_data(client, project["id"], b["id"])
    assert client.delete(f"/projects/{b['id']}").status_code == 204
    body = _stats(client)
    assert body["total"] == 3
    assert body["by_status"] == {"todo": 2, "in_progress": 0, "done": 1}


def test_t2_11_sums_equal_project_stats(client, project):
    b = _new_project(client, "B")
    _status_data(client, project["id"], b["id"])
    body = _stats(client)
    per_project = [client.get(f"/projects/{p['id']}/stats").get_json() for p in (project, b)]
    assert body["total"] == sum(s["total"] for s in per_project)
    for status in body["by_status"]:
        assert body["by_status"][status] == sum(s["by_status"][status] for s in per_project)
    assert sum(body["by_status"].values()) == body["total"]


def _overdue_data(client, a, b):
    _task(client, a, status="todo", due_date=_day(-1))
    _task(client, a, status="in_progress", due_date=_day(-3))
    _task(client, a, status="done", due_date=_day(-2))
    _task(client, a, status="todo", due_date=_day(0))
    _task(client, a, status="todo", due_date=_day(2))
    _task(client, b, status="todo", due_date=_day(-2))


def test_t2_12_overdue_same_rule(client, project):
    b = _new_project(client, "B")
    _overdue_data(client, project["id"], b["id"])
    assert _stats(client)["overdue"] == 3


def test_t2_13_due_today_not_overdue(client, project):
    _task(client, project["id"], status="todo", due_date=_day(0))
    assert _stats(client)["overdue"] == 0


def test_t2_14_overdue_equals_tasks_overdue(client, project):
    b = _new_project(client, "B")
    _overdue_data(client, project["id"], b["id"])
    gone = _task(client, project["id"], status="todo", due_date=_day(-4))
    assert client.delete(f"/tasks/{gone['id']}").status_code == 204
    c = _new_project(client, "C")
    _task(client, c["id"], status="todo", due_date=_day(-4))
    assert client.delete(f"/projects/{c['id']}").status_code == 204
    items = client.get("/tasks/overdue").get_json()["items"]
    assert _stats(client)["overdue"] == len(items) == 3


def test_t2_15_done_not_overdue(client, project):
    _task(client, project["id"], status="done", due_date=_day(-5))
    _task(client, project["id"], status="in_progress", due_date=_day(-5))
    assert _stats(client)["overdue"] == 1


def test_t2_16_tags_summed_across_projects(client, project):
    b = _new_project(client, "B")
    _task(client, project["id"], tags=["bug"])
    _task(client, project["id"], tags=["bug"])
    _task(client, b["id"], tags=["bug"])
    assert {"tag": "bug", "task_count": 3} in _stats(client)["top_tags"]


def test_t2_17_tags_count_any_status(client, project):
    for status in ("todo", "done", "in_progress"):
        _task(client, project["id"], status=status, tags=["bug"])
    assert _stats(client)["top_tags"] == [{"tag": "bug", "task_count": 3}]


def test_t2_18_top_tag_item_shape(client, project):
    _task(client, project["id"], tags=["bug", "ui"])
    items = _stats(client)["top_tags"]
    assert items
    for item in items:
        assert set(item) == {"tag", "task_count"}
        assert isinstance(item["tag"], str)
        assert isinstance(item["task_count"], int) and item["task_count"] >= 1


def test_t2_19_tags_normalized(client, project):
    _task(client, project["id"], tags=["Bug", "bug "])
    assert _stats(client)["top_tags"] == [{"tag": "bug", "task_count": 1}]


def test_t2_20_patched_tags_replace(client, project):
    task = _task(client, project["id"], tags=["bug"])
    assert client.patch(f"/tasks/{task['id']}", json={"tags": ["ui"]}).status_code == 200
    assert _stats(client)["top_tags"] == [{"tag": "ui", "task_count": 1}]


def test_t2_21_order_count_desc_then_tag_asc(client, project):
    _tagged(client, project["id"], {"a": 4, "b": 3, "c": 3, "d": 2, "e": 1})
    assert [t["tag"] for t in _stats(client)["top_tags"]] == ["a", "b", "c", "d", "e"]


def test_t2_22_at_most_five(client, project):
    _tagged(client, project["id"], {f"tag{i}": 7 - i for i in range(7)})
    items = _stats(client)["top_tags"]
    assert len(items) == 5
    assert [t["task_count"] for t in items] == [7, 6, 5, 4, 3]


def test_t2_23_two_tags_two_items(client, project):
    _tagged(client, project["id"], {"a": 2, "b": 1})
    assert len(_stats(client)["top_tags"]) == 2


def test_t2_24_tie_order_alphabetical(client, project):
    _tagged(client, project["id"], {t: 1 for t in ("zulu", "echo", "delta", "charlie", "bravo", "alpha")})
    assert [t["tag"] for t in _stats(client)["top_tags"]] == ["alpha", "bravo", "charlie", "delta", "echo"]


def test_t2_25_no_tags_empty_list(client, project):
    _task(client, project["id"])
    assert _stats(client)["top_tags"] == []


def test_t2_26_deleted_task_and_project_tags_excluded(client, project):
    ghost = _task(client, project["id"], tags=["ghost"])
    assert client.delete(f"/tasks/{ghost['id']}").status_code == 204
    other = _new_project(client, "Old")
    _task(client, other["id"], tags=["legacy"])
    assert client.delete(f"/projects/{other['id']}").status_code == 204
    _task(client, project["id"], tags=["live"])
    assert _stats(client)["top_tags"] == [{"tag": "live", "task_count": 1}]


def test_t2_27_deleted_task_not_counted_in_tag(client, project):
    _tagged(client, project["id"], {"bug": 2})
    gone = _task(client, project["id"], tags=["bug"])
    assert client.delete(f"/tasks/{gone['id']}").status_code == 204
    assert _stats(client)["top_tags"] == [{"tag": "bug", "task_count": 2}]


def test_t2_28_many_deleted_tags_do_not_crowd_out(client, project):
    for tag in ("d1", "d2", "d3", "d4", "d5"):
        for _ in range(3):
            gone = _task(client, project["id"], tags=[tag])
            assert client.delete(f"/tasks/{gone['id']}").status_code == 204
    _task(client, project["id"], tags=["x"])
    assert _stats(client)["top_tags"] == [{"tag": "x", "task_count": 1}]


def test_t2_29_project_deleted_in_db_contributes_nothing(app, client, project):
    b = _new_project(client, "B")
    _task(client, project["id"], status="todo", due_date=_day(-1), tags=["a"])
    _task(client, b["id"], status="todo", due_date=_day(-1), tags=["b"])
    with app.app_context():
        db = get_db()
        db.execute(
            "UPDATE projects SET deleted_at = ? WHERE id = ?",
            (datetime.now().isoformat(timespec="seconds"), b["id"]),
        )
        db.commit()
    body = _stats(client)
    assert body["projects"] == 1
    assert body["total"] == 1
    assert body["by_status"]["todo"] == 1
    assert body["overdue"] == 1
    assert body["top_tags"] == [{"tag": "a", "task_count": 1}]


def _mixed(client, project):
    b = _new_project(client, "B")
    _task(client, project["id"], status="todo", due_date=_day(-1), tags=["bug"])
    _task(client, b["id"], status="done", tags=["bug", "ui"])


def test_t2_30_query_params_ignored(client, project):
    _mixed(client, project)
    assert _stats(client, "?foo=bar") == _stats(client)


def test_t2_31_filter_like_params_ignored(client, project):
    _mixed(client, project)
    assert _stats(client, "?project_id=1&tag=bug&page=abc&per_page=0") == _stats(client)
