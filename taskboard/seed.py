"""Demo data so the API has something to show right after `make seed`."""

from datetime import date, timedelta

from . import services

PROJECTS = [
    {"name": "Mobile App", "description": "Flutter app for end users"},
    {"name": "Website", "description": "Marketing site and customer portal"},
]

# (title, status, priority, due in N days or None, tags)
MOBILE_TASKS = [
    ("Fix Login crash on Android 14", "in_progress", "high", 0, ["bug", "android"]),
    ("Add dark mode toggle", "todo", "medium", 7, ["feature", "ui"]),
    ("Push notification for new messages", "todo", "high", 3, ["feature"]),
    ("Update app icon", "done", "low", -5, ["ui"]),
    ("Crash when uploading avatar > 5MB", "todo", "high", -1, ["bug"]),
    ("Translate settings screen to Vietnamese", "todo", "low", 14, ["i18n"]),
    ("Offline mode for task list", "todo", "medium", 21, ["feature"]),
    ("Refactor API client", "in_progress", "medium", None, ["tech-debt"]),
    ("Login with Google", "done", "high", -10, ["feature", "auth"]),
    ("Fix typo on onboarding screen", "done", "low", None, ["bug", "ui"]),
    ("Add unit tests for cart", "todo", "medium", 5, ["test"]),
    ("Biometric login (Face ID)", "todo", "medium", 30, ["feature", "auth"]),
    ("Reduce app start time", "in_progress", "high", 2, ["performance"]),
    ("Session expires too early", "todo", "high", 0, ["bug", "auth"]),
    ("Analytics events for checkout", "todo", "low", 10, ["analytics"]),
    ("Upgrade Flutter SDK", "done", "medium", -3, ["tech-debt"]),
    ("Accessibility labels for buttons", "todo", "medium", 12, ["a11y", "ui"]),
    ("Deep link to task detail", "todo", "low", None, ["feature"]),
    ("Fix logout button not responding", "done", "high", -2, ["bug"]),
    ("In-app feedback form", "todo", "low", 25, ["feature"]),
    ("Cache images on device", "todo", "medium", 8, ["performance"]),
    ("Handle 401 from API globally", "in_progress", "high", 1, ["auth", "tech-debt"]),
    ("Release notes for v2.3", "todo", "low", 4, ["docs"]),
]

WEBSITE_TASKS = [
    ("Redesign pricing page", "in_progress", "high", 6, ["ui"]),
    ("SEO meta tags for blog", "todo", "medium", 9, ["seo"]),
    ("Contact form sends duplicate emails", "todo", "high", -4, ["bug"]),
    ("Cookie consent banner", "done", "medium", -7, ["legal"]),
    ("Customer portal login page", "todo", "high", 0, ["auth", "ui"]),
]


def _add_tasks(db, project_id, tasks, today):
    for title, status, priority, due_in, tags in tasks:
        services.create_task(
            db,
            {
                "project_id": project_id,
                "title": title,
                "status": status,
                "priority": priority,
                "due_date": (today + timedelta(days=due_in)).isoformat() if due_in is not None else None,
                "tags": tags,
            },
        )


def seed(db):
    today = date.today()
    mobile = services.create_project(db, PROJECTS[0])
    website = services.create_project(db, PROJECTS[1])
    _add_tasks(db, mobile["id"], MOBILE_TASKS, today)
    _add_tasks(db, website["id"], WEBSITE_TASKS, today)
    services.create_project(db, {"name": "Game Prototype", "description": "Unity prototype, not started"})
