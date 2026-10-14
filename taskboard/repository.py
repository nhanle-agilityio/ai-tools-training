"""Thin data-access layer. Functions take a sqlite3 connection and return rows/dicts."""

SORT_CLAUSES = {
    "created_at": "t.created_at DESC, t.id DESC",
    "due_date": "t.due_date IS NULL, t.due_date ASC, t.id ASC",
    "priority": "t.priority ASC, t.id ASC",
}


# --- projects -----------------------------------------------------------------


def insert_project(db, name, description, now):
    cur = db.execute(
        "INSERT INTO projects (name, description, created_at) VALUES (?, ?, ?)",
        (name, description, now),
    )
    db.commit()
    return cur.lastrowid


def get_project(db, project_id):
    return db.execute("SELECT * FROM projects WHERE id = ?", (project_id,)).fetchone()


def get_project_by_name(db, name):
    return db.execute("SELECT * FROM projects WHERE name = ?", (name,)).fetchone()


def list_projects(db):
    return db.execute("SELECT * FROM projects ORDER BY name").fetchall()


def count_tasks_by_status(db, project_id):
    rows = db.execute(
        "SELECT status, COUNT(*) AS n FROM tasks WHERE project_id = ? GROUP BY status",
        (project_id,),
    ).fetchall()
    return {row["status"]: row["n"] for row in rows}


# --- tasks --------------------------------------------------------------------


def insert_task(db, fields, now):
    cur = db.execute(
        """
        INSERT INTO tasks
            (project_id, title, description, status, priority, due_date, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            fields["project_id"],
            fields["title"],
            fields["description"],
            fields["status"],
            fields["priority"],
            fields["due_date"],
            now,
            now,
        ),
    )
    db.commit()
    return cur.lastrowid


def get_task(db, task_id):
    return db.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()


def update_task(db, task_id, fields, now):
    db.execute(
        """
        UPDATE tasks
           SET title = ?, description = ?, status = ?, priority = ?, due_date = ?, updated_at = ?
         WHERE id = ?
        """,
        (
            fields["title"],
            fields["description"],
            fields["status"],
            fields["priority"],
            fields["due_date"],
            now,
            task_id,
        ),
    )
    db.commit()


def delete_task(db, task_id):
    db.execute("DELETE FROM tasks WHERE id = ?", (task_id,))
    db.commit()


def _task_filters(project_id, status, q):
    where, params = [], []
    if project_id is not None:
        where.append("t.project_id = ?")
        params.append(project_id)
    if status is not None:
        where.append("t.status = ?")
        params.append(status)
    if q:
        where.append("(instr(t.title, ?) > 0 OR instr(t.description, ?) > 0)")
        params.extend([q, q])
    clause = f"WHERE {' AND '.join(where)}" if where else ""
    return clause, params


def list_tasks(db, *, project_id=None, status=None, q=None, sort="created_at", limit, offset):
    clause, params = _task_filters(project_id, status, q)
    total = db.execute(f"SELECT COUNT(*) FROM tasks t {clause}", params).fetchone()[0]
    rows = db.execute(
        f"SELECT t.* FROM tasks t {clause} ORDER BY {SORT_CLAUSES[sort]} LIMIT ? OFFSET ?",
        [*params, limit, offset],
    ).fetchall()
    return rows, total


def list_open_tasks_with_due_date(db):
    return db.execute(
        "SELECT * FROM tasks WHERE status != 'done' AND due_date IS NOT NULL ORDER BY due_date, id"
    ).fetchall()


# --- tags ---------------------------------------------------------------------


def get_tags(db, task_ids):
    if not task_ids:
        return {}
    placeholders = ",".join("?" for _ in task_ids)
    rows = db.execute(
        f"SELECT task_id, tag FROM task_tags WHERE task_id IN ({placeholders}) ORDER BY tag",
        list(task_ids),
    ).fetchall()
    tags = {task_id: [] for task_id in task_ids}
    for row in rows:
        tags[row["task_id"]].append(row["tag"])
    return tags


def set_tags(db, task_id, tags):
    db.execute("DELETE FROM task_tags WHERE task_id = ?", (task_id,))
    db.executemany(
        "INSERT INTO task_tags (task_id, tag) VALUES (?, ?)",
        [(task_id, tag) for tag in tags],
    )
    db.commit()
