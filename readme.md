# News Brief Desk

A working prototype of a newsroom workflow that turns a large stream of raw news items into concise, editor-approved stories.

The system:

* Groups incoming items that are likely about the same real-world event
* Generates a first-pass brief from the grouped sources
* Lets reporters edit and submit drafts
* Prevents reporters from publishing
* Lets editors review, rewrite, reject, and publish
* Handles stories discovered to be duplicates after publication
* Gives the desk head visibility into published stories and turnaround time

## Demo

**Live application:** [YOUR DEPLOYED URL]

**Demo video:** [YOUR VIDEO URL]

**GitHub:** [YOUR REPOSITORY URL]

---

## How to run locally

### Requirements

* Python 3.10+
* pip

### Setup

```bash
git clone [YOUR REPOSITORY URL]
cd News-app

pip install -r requirements.txt
python app.py
```

Then open:

```text
http://127.0.0.1:5000
```

The application uses SQLite. The database and seed data are created automatically on first run.

No API keys or external services are required.

### Reset the demo

To restore the application to its initial state:

```text
/reset-demo
```

---

## How to use the application

The prototype has three roles:

### Reporter

The reporter:

1. Reviews incoming stories
2. Checks the automatically generated grouping
3. Edits the generated brief
4. Submits the brief to the editor
5. Revises briefs that are sent back

A reporter cannot publish a story.

### Editor

The editor:

1. Reviews submitted briefs
2. Reviews the underlying sources
3. Rewrites the brief
4. Sends it back to the reporter if changes are needed
5. Publishes the final version

### Desk Head

The desk head can:

* See what stories were published
* See story subjects
* Review turnaround time
* Manage the story list

For this take-home prototype, an "Acting as" switcher is used instead of implementing real authentication.

Importantly, permissions are enforced server-side, so changing the UI does not give a reporter permission to publish.

---

## Story grouping

Incoming items are automatically grouped into likely-same-event stories.

The current implementation uses:

**TF-IDF → cosine similarity → threshold → union-find**

I chose this approach instead of using an LLM for clustering because it is:

* Fast
* Free
* Deterministic
* Explainable
* Simple to run locally

The clustering is intentionally treated as a **first pass**, not as the final editorial decision.

The newsroom workflow therefore includes manual controls for correcting incorrect groupings.

### Test data

The seed dataset contains 18 realistic-looking raw items across approximately six subjects.

It deliberately includes:

* Three differently worded reports about the same Hokkaido earthquake
* Two stories that share similar vocabulary but are actually different water/drought events
* Different source types including wire-style copy, press releases, blogs, and social posts

This allows the grouping workflow to be tested for both duplicate detection and over-grouping.

---

## Publishing and merging

### Before publication

If two unpublished stories are determined to describe the same event:

* Their sources are combined
* One story remains as the primary story
* The other is marked `MERGED`

### After publication

Published stories are treated as permanent records.

If another story is later determined to describe the same event:

* The published brief is not rewritten
* Its `published_at` timestamp is not changed
* Additional sources can be attached
* The change is recorded in the activity log

This preserves the principle that once a brief is published, it is out.

---

## State model

The main story workflow is:

```text
DRAFT
   ↓
IN_REVIEW
   ↓
PUBLISHED
```

A story can also enter:

```text
MERGED
```

when it is combined with another story.

When an editor sends a story back, it returns to `DRAFT` with an editor note for the reporter.

---

## Permissions

Reporter permissions are enforced on the server rather than only through the UI.

Write operations independently verify the current role, including:

* Publishing
* Rejecting
* Merging
* Deleting
* Saving reporter drafts

Therefore, attempting to access a protected action directly as a Reporter results in a server-side authorization failure.

The role switcher is only a convenience for demonstrating the three workflows without requiring a full authentication system.

---

## Data and architecture

The prototype uses:

* **Python / Flask** — application and HTTP routes
* **SQLite** — local persistence
* **scikit-learn** — TF-IDF and cosine similarity
* **HTML/CSS/templates** — user interface
* **JSON** — initial seed data

The architecture was intentionally kept lightweight because the task is a 48-hour prototype and does not require live feeds or a hosted database.

---

## Decisions and assumptions

The brief intentionally leaves several implementation details open.

### No live feeds

I created a local dataset instead of connecting to live news feeds because the task explicitly says live feeds are not required.

### No real authentication

The prototype uses an "Acting as" role switcher rather than implementing user accounts.

This keeps the demo simple while still enforcing authorization on the server.

### AI is not responsible for final editorial decisions

Automation is used to reduce repetitive work, but the editor remains responsible for the final published brief.

### Rejection returns to draft

I chose to return an edited/rejected brief to `DRAFT` rather than introduce a separate rejection state. This keeps the primary workflow simple while retaining the editor's note and activity history.

### Published stories are immutable

Once published, the original brief and publication timestamp are preserved.

---

## AI tools used

I used **Claude (Anthropic)** during development for:

* Flask/application scaffolding
* Exploring and iterating on the clustering implementation
* UI/template development
* Debugging and UX iteration

I did not use an LLM as the final story-clustering mechanism. I chose TF-IDF and cosine similarity because I wanted a deterministic and explainable first-pass approach.

I reviewed and tested generated changes by running the application and manually walking through the workflows.

---

## What I would do with another week

### 1. Better duplicate detection

Create a dedicated "possible duplicates" interface ranked by similarity rather than showing every other open story.

### 2. Better event understanding

Use named entities such as locations, people, organizations, and dates to distinguish stories that share a topic but describe different events.

### 3. Photo and screenshot intake

Allow screenshots/photos to be uploaded and use OCR/vision to extract the relevant text before sending it through the existing grouping pipeline.

### 4. Real authentication

Replace the demo role switcher with proper user accounts and role-based access control.

### 5. Better editorial analytics

Add metrics such as:

* Rejection/send-back rate
* Average turnaround time
* Turnaround by subject
* Stories that required multiple revisions

### 6. More robust evaluation

Create a larger labelled dataset and measure:

* Duplicate detection precision
* Duplicate detection recall
* False merge rate
* Missed duplicate rate

This would make it possible to tune the clustering threshold based on measurable performance rather than manual inspection alone.

---

## Known limitations

This is a prototype rather than a production newsroom system.

Current limitations include:

* TF-IDF is based primarily on lexical similarity and can miss semantic relationships
* There is no real authentication
* Seed data is local rather than a live news feed
* Only text input is supported
* The clustering threshold is currently global
* The prototype has not been evaluated against a large labelled dataset

These are deliberate trade-offs for the scope and time constraints of the task.

---

## Project structure

```text
News-app/
├── app.py
├── requirements.txt
├── newsdesk.db
├── data/
│   └── news_data.json
├── ml/
│   └── clustering.py
├── templates/
├── static/
└── README.md
```

## Summary

The main design principle behind this prototype is:

> Automate the repetitive first pass, keep the source material visible, and keep the final publishing decision with the editor.

The system is designed around that principle from ingestion through grouping, drafting, review, publication, and reporting.
