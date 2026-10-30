import pytest

# --- create -------------------------------------------------------------------


def test_create_comment(client, make_task):
    task = make_task()
    resp = client.post(f"/tasks/{task['id']}/comments", json={"author": "Lan", "body": "Hi"})
    assert resp.status_code == 201
    comment = resp.get_json()
    assert set(comment) == {"id", "task_id", "author", "body", "created_at", "updated_at"}
    assert comment["task_id"] == task["id"]
    assert comment["author"] == "Lan"
    assert comment["body"] == "Hi"
    assert comment["updated_at"] == comment["created_at"]


def test_create_comment_strips_author_and_body(client, make_task):
    task = make_task()
    resp = client.post(f"/tasks/{task['id']}/comments", json={"author": "  Lan  ", "body": "  Hi  "})
    assert resp.status_code == 201
    assert resp.get_json()["author"] == "Lan"
    assert resp.get_json()["body"] == "Hi"


@pytest.mark.parametrize("author", [None, "", "   ", 5])
def test_create_comment_author_required(client, make_task, author):
    task = make_task()
    payload = {"body": "Hi"} if author is None else {"author": author, "body": "Hi"}
    resp = client.post(f"/tasks/{task['id']}/comments", json=payload)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "author is required"


def test_create_comment_author_length(client, make_task):
    task = make_task()
    url = f"/tasks/{task['id']}/comments"
    resp = client.post(url, json={"author": "a" * 101, "body": "Hi"})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "author must be at most 100 characters"
    assert client.post(url, json={"author": "a" * 100, "body": "Hi"}).status_code == 201


@pytest.mark.parametrize("body", [None, "", "   ", 5])
def test_create_comment_body_required(client, make_task, body):
    task = make_task()
    payload = {"author": "Lan"} if body is None else {"author": "Lan", "body": body}
    resp = client.post(f"/tasks/{task['id']}/comments", json=payload)
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "body is required"


def test_create_comment_body_length(client, make_task):
    task = make_task()
    url = f"/tasks/{task['id']}/comments"
    resp = client.post(url, json={"author": "Lan", "body": "b" * 2001})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "body must be at most 2000 characters"
    assert client.post(url, json={"author": "Lan", "body": "b" * 2000}).status_code == 201


def test_create_comment_non_object_body(client, make_task):
    task = make_task()
    resp = client.post(f"/tasks/{task['id']}/comments", json=[])
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "request body must be a JSON object"


def test_create_comment_missing_task_checked_before_body(client):
    for payload in ({"author": "Lan", "body": "Hi"}, {}, []):
        resp = client.post("/tasks/999/comments", json=payload)
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "task 999 not found"


def test_create_comment_on_deleted_task(client, make_task):
    task = make_task()
    client.delete(f"/tasks/{task['id']}")
    resp = client.post(f"/tasks/{task['id']}/comments", json={"author": "Lan", "body": "Hi"})
    assert resp.status_code == 404
    assert resp.get_json()["error"] == f"task {task['id']} not found"


def test_create_comment_on_task_of_deleted_project(client, project, make_task):
    task = make_task()
    client.delete(f"/projects/{project['id']}")
    resp = client.post(f"/tasks/{task['id']}/comments", json={"author": "Lan", "body": "Hi"})
    assert resp.status_code == 404
    assert resp.get_json()["error"] == f"task {task['id']} not found"


def test_create_comment_does_not_touch_task_updated_at(client, make_task, monkeypatch):
    from datetime import datetime

    task = make_task()

    class LaterDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2030, 1, 2, 3, 4, 5)

    monkeypatch.setattr("taskboard.services.datetime", LaterDatetime)
    client.post(f"/tasks/{task['id']}/comments", json={"author": "Lan", "body": "Hi"})
    assert client.get(f"/tasks/{task['id']}").get_json()["updated_at"] == task["updated_at"]


# --- read and edit a single comment -------------------------------------------


def _new_comment(client, task, **overrides):
    payload = {"author": "Lan", "body": "Hi", **overrides}
    return client.post(f"/tasks/{task['id']}/comments", json=payload).get_json()


def _freeze_later_clock(monkeypatch):
    from datetime import datetime

    class LaterDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2030, 1, 2, 3, 4, 5)

    monkeypatch.setattr("taskboard.services.datetime", LaterDatetime)
    return LaterDatetime.now().isoformat(timespec="seconds")


def test_get_comment(client, make_task):
    comment = _new_comment(client, make_task())
    resp = client.get(f"/comments/{comment['id']}")
    assert resp.status_code == 200
    assert resp.get_json() == comment


def test_get_comment_not_found(client):
    resp = client.get("/comments/999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "comment 999 not found"


def test_patch_comment_body(client, make_task, monkeypatch):
    comment = _new_comment(client, make_task())
    later = _freeze_later_clock(monkeypatch)
    resp = client.patch(f"/comments/{comment['id']}", json={"body": "New"})
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["body"] == "New"
    assert data["author"] == "Lan"
    assert data["updated_at"] == later
    assert data["created_at"] == comment["created_at"]
    assert client.get(f"/comments/{comment['id']}").get_json() == data


def test_patch_comment_strips_body(client, make_task):
    comment = _new_comment(client, make_task())
    resp = client.patch(f"/comments/{comment['id']}", json={"body": "  New  "})
    assert resp.status_code == 200
    assert resp.get_json()["body"] == "New"


def test_patch_comment_empty_object_touches_updated_at(client, make_task, monkeypatch):
    comment = _new_comment(client, make_task())
    later = _freeze_later_clock(monkeypatch)
    resp = client.patch(f"/comments/{comment['id']}", json={})
    assert resp.status_code == 200
    assert resp.get_json()["body"] == comment["body"]
    assert resp.get_json()["updated_at"] == later


def test_patch_comment_ignores_other_fields(client, make_task):
    comment = _new_comment(client, make_task())
    payload = {"author": "X", "task_id": 99, "id": 5, "created_at": "x"}
    resp = client.patch(f"/comments/{comment['id']}", json=payload)
    assert resp.status_code == 200
    data = resp.get_json()
    for key in ("author", "task_id", "id", "created_at"):
        assert data[key] == comment[key]


@pytest.mark.parametrize("body", ["", "  ", 5])
def test_patch_comment_body_required(client, make_task, body):
    comment = _new_comment(client, make_task())
    resp = client.patch(f"/comments/{comment['id']}", json={"body": body})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "body is required"


def test_patch_comment_body_length(client, make_task):
    comment = _new_comment(client, make_task())
    resp = client.patch(f"/comments/{comment['id']}", json={"body": "b" * 2001})
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "body must be at most 2000 characters"


def test_patch_comment_non_object_body(client, make_task):
    comment = _new_comment(client, make_task())
    resp = client.patch(f"/comments/{comment['id']}", json=[])
    assert resp.status_code == 400
    assert resp.get_json()["error"] == "request body must be a JSON object"


def test_patch_comment_missing_checked_before_body(client):
    for payload in ({"body": "New"}, {"body": ""}, []):
        resp = client.patch("/comments/999", json=payload)
        assert resp.status_code == 404
        assert resp.get_json()["error"] == "comment 999 not found"


def test_comment_unreachable_after_task_delete(client, make_task):
    task = make_task()
    comment = _new_comment(client, task)
    client.delete(f"/tasks/{task['id']}")
    for call in (client.get, lambda url: client.patch(url, json={"body": "New"})):
        resp = call(f"/comments/{comment['id']}")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == f"comment {comment['id']} not found"


def test_comment_unreachable_after_project_delete(client, project, make_task):
    comment = _new_comment(client, make_task())
    client.delete(f"/projects/{project['id']}")
    for call in (client.get, lambda url: client.patch(url, json={"body": "New"})):
        resp = call(f"/comments/{comment['id']}")
        assert resp.status_code == 404
        assert resp.get_json()["error"] == f"comment {comment['id']} not found"


def test_patch_comment_does_not_touch_task_updated_at(client, make_task, monkeypatch):
    task = make_task()
    comment = _new_comment(client, task)
    _freeze_later_clock(monkeypatch)
    client.patch(f"/comments/{comment['id']}", json={"body": "New"})
    assert client.get(f"/tasks/{task['id']}").get_json()["updated_at"] == task["updated_at"]


# --- list ---------------------------------------------------------------------


def _post_comment(client, task_id, body):
    resp = client.post(f"/tasks/{task_id}/comments", json={"author": "Lan", "body": body})
    assert resp.status_code == 201, resp.get_json()
    return resp.get_json()


def test_list_comments_empty(client, make_task):
    task = make_task()
    resp = client.get(f"/tasks/{task['id']}/comments")
    assert resp.status_code == 200
    assert resp.get_json() == {"items": []}


def test_list_comments_oldest_first(client, make_task, monkeypatch):
    from datetime import datetime

    task = make_task()
    for day, body in ((1, "A"), (2, "B"), (3, "C")):

        class FrozenDatetime(datetime):
            @classmethod
            def now(cls, tz=None, _day=day):
                return cls(2030, 1, _day, 0, 0, 0)

        monkeypatch.setattr("taskboard.services.datetime", FrozenDatetime)
        _post_comment(client, task["id"], body)
    items = client.get(f"/tasks/{task['id']}/comments").get_json()["items"]
    assert [c["body"] for c in items] == ["A", "B", "C"]


def test_list_comments_same_created_at_ordered_by_id(client, make_task, monkeypatch):
    from datetime import datetime

    class FrozenDatetime(datetime):
        @classmethod
        def now(cls, tz=None):
            return cls(2030, 1, 1, 0, 0, 0)

    monkeypatch.setattr("taskboard.services.datetime", FrozenDatetime)
    task = make_task()
    created = [_post_comment(client, task["id"], body) for body in ("A", "B", "C")]
    assert len({c["created_at"] for c in created}) == 1
    items = client.get(f"/tasks/{task['id']}/comments").get_json()["items"]
    assert [c["id"] for c in items] == sorted(c["id"] for c in created)


def test_list_comments_only_own_task(client, make_task):
    task = make_task()
    other = make_task(title="Other")
    _post_comment(client, task["id"], "mine")
    _post_comment(client, other["id"], "theirs")
    items = client.get(f"/tasks/{task['id']}/comments").get_json()["items"]
    assert [c["body"] for c in items] == ["mine"]


def test_list_comments_has_no_deleted_at(client, make_task):
    task = make_task()
    _post_comment(client, task["id"], "Hi")
    items = client.get(f"/tasks/{task['id']}/comments").get_json()["items"]
    assert set(items[0]) == {"id", "task_id", "author", "body", "created_at", "updated_at"}


def test_list_comments_missing_task(client):
    resp = client.get("/tasks/999/comments")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "task 999 not found"


def test_list_comments_on_deleted_task(client, make_task):
    task = make_task()
    _post_comment(client, task["id"], "Hi")
    client.delete(f"/tasks/{task['id']}")
    resp = client.get(f"/tasks/{task['id']}/comments")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == f"task {task['id']} not found"


def test_list_comments_on_task_of_deleted_project(client, project, make_task):
    task = make_task()
    _post_comment(client, task["id"], "Hi")
    client.delete(f"/projects/{project['id']}")
    resp = client.get(f"/tasks/{task['id']}/comments")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == f"task {task['id']} not found"


# --- delete -------------------------------------------------------------------


def _comment_row(app, comment_id):
    from taskboard.db import get_db

    with app.app_context():
        return get_db().execute("SELECT * FROM task_comments WHERE id = ?", (comment_id,)).fetchone()


def test_delete_comment(app, client, make_task):
    task = make_task()
    comment = _post_comment(client, task["id"], "Hi")
    resp = client.delete(f"/comments/{comment['id']}")
    assert resp.status_code == 204
    assert resp.data == b""
    row = _comment_row(app, comment["id"])
    assert row is not None
    assert row["deleted_at"] is not None


def test_deleted_comment_is_gone_for_get_patch_delete(client, make_task):
    task = make_task()
    comment = _post_comment(client, task["id"], "Hi")
    client.delete(f"/comments/{comment['id']}")
    url = f"/comments/{comment['id']}"
    for resp in (client.get(url), client.patch(url, json={"body": "x"}), client.delete(url)):
        assert resp.status_code == 404
        assert resp.get_json()["error"] == f"comment {comment['id']} not found"


def test_deleted_comment_not_listed_others_stay(client, make_task):
    task = make_task()
    first = _post_comment(client, task["id"], "A")
    _post_comment(client, task["id"], "B")
    client.delete(f"/comments/{first['id']}")
    items = client.get(f"/tasks/{task['id']}/comments").get_json()["items"]
    assert [c["body"] for c in items] == ["B"]


def test_delete_missing_comment(client):
    resp = client.delete("/comments/999")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == "comment 999 not found"


def test_delete_comment_on_deleted_task(client, make_task):
    task = make_task()
    comment = _post_comment(client, task["id"], "Hi")
    client.delete(f"/tasks/{task['id']}")
    resp = client.delete(f"/comments/{comment['id']}")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == f"comment {comment['id']} not found"


def test_delete_comment_on_deleted_project(client, project, make_task):
    comment = _new_comment(client, make_task())
    client.delete(f"/projects/{project['id']}")
    resp = client.delete(f"/comments/{comment['id']}")
    assert resp.status_code == 404
    assert resp.get_json()["error"] == f"comment {comment['id']} not found"


def test_delete_comment_keeps_task_updated_at(client, make_task, monkeypatch):
    task = make_task()
    comment = _new_comment(client, task)
    _freeze_later_clock(monkeypatch)
    resp = client.delete(f"/comments/{comment['id']}")
    assert resp.status_code == 204
    assert client.get(f"/tasks/{task['id']}").get_json()["updated_at"] == task["updated_at"]
