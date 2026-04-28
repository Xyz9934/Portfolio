import re

from assistant_memory import (
    add_fact,
    add_task,
    complete_task,
    delete_task,
    get_due_reminders,
    get_latest_task,
    get_profile_snapshot,
    get_recent_summaries,
    get_task_snapshot,
    list_completed_tasks,
    list_overdue_tasks,
    list_tasks,
    list_today_tasks,
    mark_task_reminder_sent,
    rename_task,
    reschedule_task,
    search_profile,
    search_tasks,
    set_preference,
)


def _clean(text):
    return re.sub(r"\s+", " ", (text or "").strip())


def _extract_due_text(text):
    patterns = [
        r"\b(?:by|on)\s+(.+)$",
        r"\b(?:tomorrow|today)(?:\s+at\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?)?\b",
        r"\bat\s+\d{1,2}(?::\d{2})?\s*(?:am|pm)?\b",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            if match.groups():
                return match.group(1).strip(" .")
            return match.group(0).strip(" .")
    return ""


def _strip_due_text(task_text, due_text):
    cleaned_task = (task_text or "").strip()
    cleaned_due = (due_text or "").strip()
    if not cleaned_due:
        return cleaned_task

    patterns = [
        rf"\b(?:by|on)\s+{re.escape(cleaned_due)}\b",
        rf"\b{re.escape(cleaned_due)}\b",
    ]
    updated = cleaned_task
    for pattern in patterns:
        updated = re.sub(pattern, "", updated, flags=re.IGNORECASE).strip(" .")
    return re.sub(r"\s+", " ", updated).strip(" .")


def _extract_recurrence(text):
    normalized = (text or "").lower()
    patterns = [
        ("daily", r"\b(every day|daily)\b"),
        ("weekly", r"\b(every week|weekly)\b"),
        ("monthly", r"\b(every month|monthly)\b"),
    ]
    for label, pattern in patterns:
        if re.search(pattern, normalized):
            return label
    return ""


def _strip_recurrence_text(task_text, recurrence):
    if not recurrence:
        return task_text.strip()
    patterns = {
        "daily": r"\b(every day|daily)\b",
        "weekly": r"\b(every week|weekly)\b",
        "monthly": r"\b(every month|monthly)\b",
    }
    cleaned = re.sub(patterns.get(recurrence, r"$^"), "", task_text, flags=re.IGNORECASE)
    return re.sub(r"\s+", " ", cleaned).strip(" .")


def _render_task_list(title, tasks, empty_message, include_completed=False):
    if not tasks:
        return empty_message
    lines = [title]
    for index, task in enumerate(tasks[:8], start=1):
        due = f" (due: {task['due']})" if task.get("due") else ""
        status = " [done]" if include_completed else ""
        recurrence = f" [{task['recurrence']}]" if task.get("recurrence") else ""
        lines.append(f"{index}. {task.get('title', '')}{due}{recurrence}{status}")
    return "\n".join(lines)


def _extract_new_due_text(text):
    patterns = [
        r"\bto\s+(.+)$",
        r"\bfor\s+(.+)$",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            return match.group(1).strip(" .")
    return ""


def _resolve_task_reference(query):
    cleaned = _clean(query)
    if cleaned.lower() in {"this reminder", "this task", "that reminder", "that task"}:
        latest = get_latest_task(include_done=False)
        if latest:
            return latest.get("title", "")
    return cleaned


def handle_assistant_command(text):
    original = (text or "").strip()
    normalized = original.lower().strip()
    if not normalized:
        return None

    if normalized in {
        "show my tasks",
        "my tasks",
        "what are my tasks",
        "what's on my task list",
        "task list",
        "todo list",
    }:
        tasks = list_tasks(status="open")
        if not tasks:
            return "You don't have any open tasks right now."
        lines = ["Here are your open tasks:"]
        for index, task in enumerate(tasks[:8], start=1):
            due = f" (due: {task['due']})" if task.get("due") else ""
            recurrence = f" [{task['recurrence']}]" if task.get("recurrence") else ""
            lines.append(f"{index}. {task.get('title', '')}{due}{recurrence}")
        return "\n".join(lines)

    if normalized in {"today's tasks", "todays tasks", "show today's tasks", "show todays tasks", "what are my tasks today"}:
        return _render_task_list(
            "Here are your tasks for today:",
            list_today_tasks(),
            "You don't have any tasks due today.",
        )

    if normalized in {"overdue tasks", "show overdue tasks", "what is overdue", "what's overdue"}:
        return _render_task_list(
            "These tasks are overdue:",
            list_overdue_tasks(),
            "You don't have any overdue tasks.",
        )

    if normalized in {"completed tasks", "show completed tasks", "finished tasks", "done tasks"}:
        return _render_task_list(
            "Here are your completed tasks:",
            list_completed_tasks(limit=10),
            "You don't have any completed tasks yet.",
            include_completed=True,
        )

    if normalized in {"check reminders", "show reminders", "any reminders", "what should i do now"}:
        reminders = get_due_reminders()
        if not reminders:
            return "You don't have any reminders due right now."
        lines = ["You have reminders due now:"]
        for task in reminders[:6]:
            due = f" (due: {task['due']})" if task.get("due") else ""
            lines.append(f"- {task.get('title', '')}{due}")
            mark_task_reminder_sent(task.get("id"))
        return "\n".join(lines)

    if normalized in {
        "what do you remember about me",
        "remember me",
        "my profile",
        "what do you know about me",
    }:
        profile = get_profile_snapshot()
        tasks = get_task_snapshot(limit=5)
        summaries = get_recent_summaries(limit=2)
        items = profile + tasks + summaries
        if not items:
            return "I don't have much saved about you yet. You can tell me preferences, facts, or tasks to remember."
        return "Here's what I currently remember:\n- " + "\n- ".join(items[:12])

    if normalized in {"what is my name", "what's my name"}:
        profile = get_profile_snapshot()
        for item in profile:
            if item.lower().startswith("preference - name:"):
                return item.replace("Preference - name:", "Your name is").strip()
        return "You haven't told me your name yet."

    if normalized in {"what do i prefer", "what are my preferences", "what do you know about my preferences"}:
        profile = [item for item in get_profile_snapshot() if item.lower().startswith("preference - ")]
        if not profile:
            return "I don't have any saved preferences for you yet."
        return "Here are the preferences I remember:\n- " + "\n- ".join(profile[:8])

    remember_match = re.match(r"^(remember that|remember)\s+(.+)$", original, re.IGNORECASE)
    if remember_match:
        fact = _clean(remember_match.group(2))
        if add_fact(fact):
            return f"I'll remember that: {fact}"
        return "I already had that in memory."

    name_match = re.match(r"^(my name is|i am|i'm)\s+(.+)$", original, re.IGNORECASE)
    if name_match and len(original.split()) <= 8:
        name = _clean(name_match.group(2))
        set_preference("name", name)
        return f"Got it. I'll remember your name as {name}."

    preference_patterns = [
        (r"^i prefer\s+(.+)$", "preference"),
        (r"^my favorite\s+(.+?)\s+is\s+(.+)$", "favorite"),
        (r"^i like\s+(.+)$", "likes"),
        (r"^i use\s+(.+)$", "tools"),
    ]
    for pattern, key in preference_patterns:
        match = re.match(pattern, original, re.IGNORECASE)
        if match:
            if key == "favorite":
                pref_key = f"favorite {match.group(1).strip()}"
                pref_value = _clean(match.group(2))
            else:
                pref_key = key
                pref_value = _clean(match.group(1))
            set_preference(pref_key, pref_value)
            return f"I'll remember your {pref_key} as {pref_value}."

    task_match = re.match(
        r"^(remind me to|add task|add todo|todo|task)\s+(.+)$",
        original,
        re.IGNORECASE,
    )
    if task_match:
        task_text = _clean(task_match.group(2))
        recurrence = _extract_recurrence(task_text)
        due_text = _extract_due_text(task_text)
        if due_text:
            title = _strip_due_text(task_text, due_text)
        else:
            title = task_text
        title = _strip_recurrence_text(title, recurrence)
        task = add_task(title=title, due_text=due_text, recurrence=recurrence)
        if task is None:
            return "Tell me the task you want me to track."
        due_suffix = f" Due: {task['due']}." if task.get("due") else ""
        reminder_suffix = " I'll remind you before it is due." if task.get("remind_at") else ""
        recurrence_suffix = f" Recurrence: {task['recurrence']}." if task.get("recurrence") else ""
        return f"Task added: {task['title']}.{due_suffix}{recurrence_suffix}{reminder_suffix}"

    reschedule_match = re.match(
        r"^(reschedule|move|change time for|change due for|update due for)\s+(.+)$",
        original,
        re.IGNORECASE,
    )
    if reschedule_match:
        remainder = _clean(reschedule_match.group(2))
        due_text = _extract_new_due_text(remainder)
        query = _resolve_task_reference(re.sub(r"\b(to|for)\s+.+$", "", remainder, flags=re.IGNORECASE).strip(" ."))
        task = reschedule_task(query, due_text)
        if task:
            return f"Rescheduled task: {task['title']}. New due time: {task.get('due', 'updated')}."
        return "I couldn't find that task or understand the new time."

    rename_match = re.match(
        r"^(rename task|rename reminder|rename)\s+(.+?)\s+\bto\b\s+(.+)$",
        original,
        re.IGNORECASE,
    )
    if rename_match:
        old_name = _resolve_task_reference(rename_match.group(2))
        new_name = _clean(rename_match.group(3))
        task = rename_task(old_name, new_name)
        if task:
            return f"Renamed task. It is now called: {task['title']}."
        return "I couldn't find that task to rename."

    delete_match = re.match(
        r"^(delete task|delete reminder|remove task|remove reminder|delete)\s+(.+)$",
        original,
        re.IGNORECASE,
    )
    if delete_match:
        query = _resolve_task_reference(delete_match.group(2))
        task = delete_task(query)
        if task:
            return f"Deleted task: {task['title']}."
        return "I couldn't find that task to delete."

    complete_match = re.match(r"^(complete task|mark task done|finish task|done with)\s+(.+)$", original, re.IGNORECASE)
    if complete_match:
        task = complete_task(complete_match.group(2))
        if task:
            if task.get("recurrence"):
                return f"Marked recurring task complete: {task['title']}. Next reminder set for {task.get('due', 'the next cycle')}."
            return f"Marked task complete: {task['title']}."
        return "I couldn't find a matching open task to complete."

    return None


def get_assistant_context(question):
    normalized = (question or "").lower()
    context = []

    if any(phrase in normalized for phrase in ("about me", "my name", "my preference", "my favorite", "i prefer", "i like")):
        context.extend(get_profile_snapshot())
    else:
        context.extend(search_profile(question, limit=4))

    if any(phrase in normalized for phrase in ("task", "todo", "remind", "deadline")):
        context.extend(get_task_snapshot(limit=6))
    else:
        context.extend(search_tasks(question, limit=4))

    context.extend(get_recent_summaries(limit=2))

    merged = []
    for item in context:
        if item and item not in merged:
            merged.append(item)
    return merged[:10]
