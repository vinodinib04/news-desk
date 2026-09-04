import json
import os
from datetime import datetime

from flask import Flask, render_template, redirect, url_for, request, session, flash

from database.database import initialize_database, get_connection, log_activity
from ml.clustering import group_news_items

app = Flask(__name__)
app.secret_key = "newsdesk-dev-secret"  # fine for a prototype; would use env var in production

BASE_DIR = os.path.dirname(__file__)
NEWS_DATA_PATH = os.path.join(BASE_DIR, "data", "news_data.json")


# ---------------------------------------------------------------------------
# ROLE SWITCHING (simulated auth)
#
# This is a take-home prototype, not a production system, so instead of
# building real accounts/login we let the visitor pick which desk role they
# are acting as. The important behaviour the task asks for - reporters can
# never publish, only editors can - is still enforced server-side on every
# publish/merge route, regardless of what the UI shows.
# ---------------------------------------------------------------------------

ROLES = ["reporter", "editor", "desk_head"]


@app.context_processor
def inject_role():
    return {"current_role": session.get("role", "reporter")}


@app.route("/set-role/<role>")
def set_role(role):
    if role in ROLES:
        session["role"] = role
    next_url = request.args.get("next")
    return redirect(next_url or request.referrer or url_for("index"))


def require_role(role):
    """Server-side guard. Returns True if allowed."""
    return session.get("role", "reporter") == role


# ---------------------------------------------------------------------------
# SEED DATA
# ---------------------------------------------------------------------------

def load_raw_news():
    with open(NEWS_DATA_PATH, "r", encoding="utf-8") as file:
        return json.load(file)


def detect_category(headline, content=""):
    text = (headline + " " + content).lower()

    keyword_map = {
        "World": ["earthquake", "japan", "chile", "santiago", "hokkaido", "tsunami"],
        "Economy": ["bank", "interest rate", "inflation", "rate cut", "central bank"],
        "Technology": ["phone", "novatech", "smartphone", "handset", "camera system"],
        "Sports": ["cricket", "football", "match", "wicket", "innings", "stadium"],
        "Politics": ["government", "minister", "election", "parliament", "council", "mayor", "bill"],
        "Environment": ["drought", "harvest", "rainfall", "farmers", "water rationing"],
    }

    for category, words in keyword_map.items():
        if any(word in text for word in words):
            return category

    return "General"


def generate_draft(sources):
    """
    A short, deliberately mechanical first-pass summary built from the
    grouped sources. This is meant to save the reporter from staring at
    a blank page, not to be publish-ready - the brief is explicit that
    the editor rewrites it before it goes out.
    """
    seen = set()
    sentences = []

    for item in sources:
        first_sentence = item["content"].split(".")[0].strip()
        key = first_sentence.lower()
        if first_sentence and key not in seen:
            seen.add(key)
            sentences.append(first_sentence)

    if not sentences:
        return "No draft could be generated from the grouped sources."

    return ". ".join(sentences[:2]) + "."


def seed_database_if_empty():
    connection = get_connection()
    existing = connection.execute("SELECT COUNT(*) AS count FROM stories").fetchone()

    if existing["count"] > 0:
        connection.close()
        return

    raw_items = load_raw_news()
    groups = group_news_items(raw_items, threshold=0.19)

    for group in groups:
        first = group[0]
        title = first["headline"]
        category = detect_category(first["headline"], first["content"])
        draft = generate_draft(group)
        created_at = min(item.get("received_at", datetime.now().isoformat()) for item in group)

        cursor = connection.execute(
            """
            INSERT INTO stories (title, category, draft, status, created_at)
            VALUES (?, ?, ?, 'DRAFT', ?)
            """,
            (title, category, draft, created_at),
        )
        story_id = cursor.lastrowid

        for item in group:
            connection.execute(
                """
                INSERT INTO story_sources (story_id, source, headline, content, received_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (story_id, item["source"], item["headline"], item["content"], item.get("received_at")),
            )

        log_activity(connection, story_id, "system", "GROUPED",
                     f"{len(group)} incoming item(s) grouped automatically.")

    connection.commit()
    connection.close()


initialize_database()
seed_database_if_empty()


# ---------------------------------------------------------------------------
# SHARED QUERIES
# ---------------------------------------------------------------------------

def fetch_story(connection, story_id):
    return connection.execute("SELECT * FROM stories WHERE id = ?", (story_id,)).fetchone()


def fetch_sources(connection, story_id):
    return connection.execute(
        "SELECT * FROM story_sources WHERE story_id = ? ORDER BY received_at ASC, id ASC",
        (story_id,),
    ).fetchall()


def fetch_log(connection, story_id):
    return connection.execute(
        "SELECT * FROM activity_log WHERE story_id = ? ORDER BY created_at ASC, id ASC",
        (story_id,),
    ).fetchall()


def stories_with_counts(connection, where_clause="", params=()):
    query = f"""
        SELECT stories.*, COUNT(story_sources.id) AS sources_count
        FROM stories
        LEFT JOIN story_sources ON stories.id = story_sources.story_id
        {where_clause}
        GROUP BY stories.id
        ORDER BY stories.created_at DESC
    """
    return connection.execute(query, params).fetchall()


# ---------------------------------------------------------------------------
# HOME
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    connection = get_connection()
    counts = {}
    for status in ("DRAFT", "IN_REVIEW", "PUBLISHED"):
        row = connection.execute(
            "SELECT COUNT(*) AS c FROM stories WHERE status = ?", (status,)
        ).fetchone()
        counts[status] = row["c"]
    connection.close()
    return render_template("index.html", counts=counts)


# ---------------------------------------------------------------------------
# REPORTER
# ---------------------------------------------------------------------------

@app.route("/reporter")
def reporter():
    connection = get_connection()
    draft_stories = stories_with_counts(connection, "WHERE stories.status = 'DRAFT'")
    submitted_stories = stories_with_counts(connection, "WHERE stories.status = 'IN_REVIEW'")
    published_stories = stories_with_counts(connection, "WHERE stories.status = 'PUBLISHED'")
    connection.close()

    return render_template(
        "reporter.html",
        draft_stories=draft_stories,
        submitted_stories=submitted_stories,
        published_stories=published_stories,
        desk_role="reporter",
    )


@app.route("/reporter/story/<int:story_id>")
def reporter_story(story_id):
    connection = get_connection()
    story = fetch_story(connection, story_id)
    if not story:
        connection.close()
        return "Story not found", 404

    sources = fetch_sources(connection, story_id)

    # Other draft/in-review stories, so a reporter can fold a stray item in
    # if the automatic grouping missed a connection between two stories.
    other_stories = connection.execute(
        """
        SELECT id, title FROM stories
        WHERE id != ? AND status IN ('DRAFT', 'IN_REVIEW')
        ORDER BY created_at DESC
        """,
        (story_id,),
    ).fetchall()

    log = fetch_log(connection, story_id)
    connection.close()

    return render_template(
        "story_detail.html",
        story=story,
        sources=sources,
        other_stories=other_stories,
        log=log,
        view="reporter",
        desk_role="reporter",
    )


@app.route("/reporter/save/<int:story_id>", methods=["POST"])
def reporter_save(story_id):
    if not require_role("reporter"):
        return "Only reporters can edit drafts.", 403

    connection = get_connection()
    story = fetch_story(connection, story_id)

    if not story:
        connection.close()
        return "Story not found", 404

    if story["status"] != "DRAFT":
        connection.close()
        flash("This story has already moved past drafting.", "error")
        return redirect(url_for("reporter_story", story_id=story_id))

    new_draft = request.form.get("draft", "").strip() or story["draft"]
    action = request.form.get("action", "save")

    if action == "submit":
        connection.execute(
            """
            UPDATE stories SET draft = ?, status = 'IN_REVIEW', submitted_at = ?, editor_note = NULL
            WHERE id = ?
            """,
            (new_draft, datetime.now().isoformat(), story_id),
        )
        log_activity(connection, story_id, "reporter", "SUBMITTED", "Sent to editor for review.")
        flash("Sent to the editor for review.", "success")
    else:
        connection.execute("UPDATE stories SET draft = ? WHERE id = ?", (new_draft, story_id))
        log_activity(connection, story_id, "reporter", "SAVED_DRAFT", "Draft updated.")
        flash("Draft saved.", "success")

    connection.commit()
    connection.close()
    return redirect(url_for("reporter_story", story_id=story_id))


@app.route("/reporter/attach/<int:story_id>", methods=["POST"])
def reporter_attach(story_id):
    """Manually fold another draft/in-review story into this one - covers
    the case where the automatic grouping missed that two items are the
    same event, *before* anything has published."""
    if not require_role("reporter"):
        return "Only reporters can regroup stories.", 403

    other_id = request.form.get("other_story_id", type=int)
    connection = get_connection()

    story = fetch_story(connection, story_id)
    other = fetch_story(connection, other_id) if other_id else None

    if not story or not other or other["status"] not in ("DRAFT", "IN_REVIEW"):
        connection.close()
        flash("Couldn't merge those two items.", "error")
        return redirect(url_for("reporter_story", story_id=story_id))

    connection.execute(
        "UPDATE story_sources SET story_id = ? WHERE story_id = ?", (story_id, other_id)
    )
    connection.execute(
        "UPDATE stories SET status = 'MERGED', merged_into_id = ? WHERE id = ?",
        (story_id, other_id),
    )
    log_activity(connection, story_id, "reporter", "MERGED_IN",
                 f"Folded in story #{other_id} ('{other['title']}') - same event, missed by auto-grouping.")
    connection.commit()
    connection.close()
    flash("Items combined into one story.", "success")
    return redirect(url_for("reporter_story", story_id=story_id))


@app.route("/reporter/delete/<int:story_id>", methods=["POST"])
def reporter_delete(story_id):
    """Discard a grouped item that's actually noise (bad grouping, not a
    real story, duplicate the auto-grouping missed). Only before it's gone
    to the editor - once it's submitted, use reject instead of delete."""
    if not require_role("reporter"):
        return "Only reporters can discard drafts.", 403

    connection = get_connection()
    story = fetch_story(connection, story_id)

    if not story:
        connection.close()
        return "Story not found", 404

    if story["status"] != "DRAFT":
        connection.close()
        flash("Only items still in drafting can be discarded here.", "error")
        return redirect(url_for("reporter_story", story_id=story_id))

    connection.execute("DELETE FROM activity_log WHERE story_id = ?", (story_id,))
    connection.execute("DELETE FROM story_sources WHERE story_id = ?", (story_id,))
    connection.execute("DELETE FROM stories WHERE id = ?", (story_id,))
    connection.commit()
    connection.close()

    flash("Discarded.", "success")
    return redirect(url_for("reporter"))


# ---------------------------------------------------------------------------
# EDITOR
# ---------------------------------------------------------------------------

@app.route("/editor")
def editor():
    connection = get_connection()
    queue = stories_with_counts(connection, "WHERE stories.status = 'IN_REVIEW'")
    published_stories = stories_with_counts(connection, "WHERE stories.status = 'PUBLISHED'")
    connection.close()
    return render_template("editor.html", queue=queue, published_stories=published_stories, desk_role="editor")


@app.route("/editor/story/<int:story_id>")
def editor_story(story_id):
    connection = get_connection()
    story = fetch_story(connection, story_id)
    if not story:
        connection.close()
        return "Story not found", 404

    sources = fetch_sources(connection, story_id)

    mergeable = connection.execute(
        """
        SELECT id, title, status FROM stories
        WHERE id != ? AND status IN ('IN_REVIEW', 'PUBLISHED')
        ORDER BY created_at DESC
        """,
        (story_id,),
    ).fetchall()

    log = fetch_log(connection, story_id)
    connection.close()

    return render_template(
        "story_detail.html",
        story=story,
        sources=sources,
        other_stories=mergeable,
        log=log,
        view="editor",
        desk_role="editor",
    )


@app.route("/editor/publish/<int:story_id>", methods=["POST"])
def publish(story_id):
    if not require_role("editor"):
        return "Only editors can publish.", 403

    connection = get_connection()
    story = fetch_story(connection, story_id)

    if not story:
        connection.close()
        return "Story not found", 404

    if story["status"] != "IN_REVIEW":
        connection.close()
        flash("Only stories currently with the editor can be published.", "error")
        return redirect(url_for("editor_story", story_id=story_id) if story["status"] != "MERGED" else url_for("editor"))

    final_text = request.form.get("final_text", "").strip() or story["draft"]
    now = datetime.now().isoformat()

    connection.execute(
        """
        UPDATE stories
        SET final_text = ?, status = 'PUBLISHED', published_at = ?
        WHERE id = ?
        """,
        (final_text, now, story_id),
    )
    log_activity(connection, story_id, "editor", "PUBLISHED", "Story published and locked.")
    connection.commit()
    connection.close()

    flash("Published. This brief is now locked.", "success")
    return redirect(url_for("editor"))


@app.route("/editor/reject/<int:story_id>", methods=["POST"])
def reject(story_id):
    """Editor sends a submitted draft back to the reporter desk instead of
    publishing it - e.g. the writing needs another pass or a source looks
    thin. It goes back to DRAFT, not straight to the trash."""
    if not require_role("editor"):
        return "Only editors can send stories back.", 403

    connection = get_connection()
    story = fetch_story(connection, story_id)

    if not story:
        connection.close()
        return "Story not found", 404

    if story["status"] != "IN_REVIEW":
        connection.close()
        flash("Only stories currently in review can be sent back.", "error")
        return redirect(url_for("editor"))

    note = request.form.get("note", "").strip()

    connection.execute(
        """
        UPDATE stories
        SET status = 'DRAFT', submitted_at = NULL, editor_note = ?
        WHERE id = ?
        """,
        (note, story_id),
    )
    log_activity(connection, story_id, "editor", "REJECTED",
                 note or "Sent back to reporter for another pass.")
    connection.commit()
    connection.close()

    flash("Sent back to the reporter desk.", "success")
    return redirect(url_for("editor"))


@app.route("/editor/merge", methods=["POST"])
def editor_merge():
    """
    Handles the case the brief specifically calls out: two items looked
    like separate stories, but turn out to be the same event - and one of
    them may already be published.

    - If the target is NOT published: sources move over, drafts combine,
      the losing story is marked MERGED.
    - If the target IS published: the published brief text/timestamp is
      never touched (once out, it's out) - instead the merged sources are
      attached as a logged update, visible on the story page as
      "added after publish", and the desk head's activity log shows it.
    """
    if not require_role("editor"):
        return "Only editors can merge stories.", 403

    keep_id = request.form.get("keep_id", type=int)
    absorb_id = request.form.get("absorb_id", type=int)

    if not keep_id or not absorb_id or keep_id == absorb_id:
        flash("Pick two different stories to merge.", "error")
        return redirect(request.referrer or url_for("editor"))

    connection = get_connection()
    keep = fetch_story(connection, keep_id)
    absorb = fetch_story(connection, absorb_id)

    if not keep or not absorb:
        connection.close()
        flash("Couldn't find one of those stories.", "error")
        return redirect(url_for("editor"))

    absorbed_sources = fetch_sources(connection, absorb_id)

    if keep["status"] == "PUBLISHED":
        for source in absorbed_sources:
            connection.execute(
                """
                INSERT INTO story_sources
                    (story_id, source, headline, content, received_at, added_after_publish)
                VALUES (?, ?, ?, ?, ?, 1)
                """,
                (keep_id, source["source"], source["headline"], source["content"], source["received_at"]),
            )
        connection.execute(
            "UPDATE stories SET status = 'MERGED', merged_into_id = ? WHERE id = ?",
            (keep_id, absorb_id),
        )
        log_activity(
            connection, keep_id, "editor", "MERGED_AFTER_PUBLISH",
            f"Story #{absorb_id} ('{absorb['title']}') turned out to be the same event and was "
            f"attached here as {len(absorbed_sources)} additional source(s). "
            f"Published text and publish time were not changed.",
        )
        flash("Linked as the same event. The published brief itself was not changed.", "success")
    else:
        combined_draft = (keep["draft"] or "") + "\n\n" + (absorb["draft"] or "")
        connection.execute(
            "UPDATE stories SET draft = ? WHERE id = ?", (combined_draft.strip(), keep_id)
        )
        for source in absorbed_sources:
            connection.execute(
                "UPDATE story_sources SET story_id = ? WHERE id = ?", (keep_id, source["id"])
            )
        connection.execute(
            "UPDATE stories SET status = 'MERGED', merged_into_id = ? WHERE id = ?",
            (keep_id, absorb_id),
        )
        log_activity(
            connection, keep_id, "editor", "MERGED",
            f"Combined with story #{absorb_id} ('{absorb['title']}') before publishing.",
        )
        flash("Stories combined.", "success")

    connection.commit()
    connection.close()
    return redirect(url_for("editor_story", story_id=keep_id))


# ---------------------------------------------------------------------------
# DESK HEAD DASHBOARD
# ---------------------------------------------------------------------------

@app.route("/dashboard")
def dashboard():
    connection = get_connection()

    published = connection.execute(
        "SELECT * FROM stories WHERE status = 'PUBLISHED' ORDER BY published_at DESC"
    ).fetchall()

    subjects = {}
    turnaround_minutes = []
    rows = []

    for story in published:
        subjects[story["category"]] = subjects.get(story["category"], 0) + 1

        minutes = None
        try:
            created = datetime.fromisoformat(story["created_at"])
            published_at = datetime.fromisoformat(story["published_at"])
            minutes = round((published_at - created).total_seconds() / 60)
            turnaround_minutes.append(minutes)
        except Exception:
            pass

        merges = connection.execute(
            "SELECT COUNT(*) AS c FROM activity_log WHERE story_id = ? AND action = 'MERGED_AFTER_PUBLISH'",
            (story["id"],),
        ).fetchone()["c"]

        rows.append({"story": story, "minutes": minutes, "merges_after": merges})

    average_minutes = round(sum(turnaround_minutes) / len(turnaround_minutes)) if turnaround_minutes else 0

    in_review_count = connection.execute(
        "SELECT COUNT(*) AS c FROM stories WHERE status = 'IN_REVIEW'"
    ).fetchone()["c"]

    draft_count = connection.execute(
        "SELECT COUNT(*) AS c FROM stories WHERE status = 'DRAFT'"
    ).fetchone()["c"]

    # Manage view - desk head can look at every story regardless of status
    # (not just published ones) and clean up anything that's stuck or dead.
    view_filter = request.args.get("view", "all")
    valid_filters = ["all", "DRAFT", "IN_REVIEW", "PUBLISHED", "MERGED"]
    if view_filter not in valid_filters:
        view_filter = "all"

    if view_filter == "all":
        all_stories = connection.execute(
            "SELECT * FROM stories ORDER BY created_at DESC"
        ).fetchall()
    else:
        all_stories = connection.execute(
            "SELECT * FROM stories WHERE status = ? ORDER BY created_at DESC",
            (view_filter,),
        ).fetchall()

    connection.close()

    return render_template(
        "dashboard.html",
        rows=rows,
        subjects=subjects,
        average_minutes=average_minutes,
        published_count=len(published),
        in_review_count=in_review_count,
        draft_count=draft_count,
        all_stories=all_stories,
        view_filter=view_filter,
        desk_role="desk_head",
    )


@app.route("/dashboard/delete/<int:story_id>", methods=["POST"])
def dashboard_delete(story_id):
    """Desk head cleanup: remove a story that's stuck or was created by
    mistake. Published stories are locked and can't be deleted here -
    they're the record of what actually went out."""
    if not require_role("desk_head"):
        return "Only the desk head can delete from here.", 403

    connection = get_connection()
    story = fetch_story(connection, story_id)

    if not story:
        connection.close()
        return "Story not found", 404

    if story["status"] == "PUBLISHED":
        connection.close()
        flash("Published stories are the record of what went out and can't be deleted.", "error")
        return redirect(url_for("dashboard"))

    connection.execute("DELETE FROM activity_log WHERE story_id = ?", (story_id,))
    connection.execute("DELETE FROM story_sources WHERE story_id = ?", (story_id,))
    connection.execute("DELETE FROM stories WHERE id = ?", (story_id,))
    connection.commit()
    connection.close()

    flash("Story deleted.", "success")
    return redirect(url_for("dashboard", view=request.form.get("view", "all")))


# ---------------------------------------------------------------------------
# ADMIN / DEV HELPER - reset the demo data
# ---------------------------------------------------------------------------

@app.route("/reset-demo")
def reset_demo():
    initialize_database(reset=True)
    seed_database_if_empty()
    flash("Demo data reset.", "success")
    return redirect(url_for("index"))


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)