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


def test_create_comment_does_not_touch_task_updated_at(client, make_task):
    task = make_task()
    client.post(f"/tasks/{task['id']}/comments", json={"author": "Lan", "body": "Hi"})
    assert client.get(f"/tasks/{task['id']}").get_json()["updated_at"] == task["updated_at"]
