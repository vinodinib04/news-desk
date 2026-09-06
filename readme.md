# News Brief Desk

A newsroom workflow prototype that helps a small news desk turn incoming raw news items into grouped stories, prepare first-pass briefs, review them editorially, and publish them once.

## Live Demo

**Deployed Application:** https://news-desk-bhhv.onrender.com/

**Demo Video:** https://www.loom.com/share/9c3e41a4553e4f96a1d07a589e34fc29


## Overview
A newsroom workflow prototype that groups incoming news items into stories, creates a first-pass brief, and moves it through reporter and editor review before publication.

The main workflow is:

**Incoming Items → Story Grouping → Reporter → Editor → Published**

The application focuses on reducing duplicate work while keeping the final editorial decision with the editor.

## Key Features

* Groups duplicate news items into one story
* Shows all sources for each story
* Creates a first draft for the reporter
* Reporter can edit and submit the story
* Editor can review, reject, or publish
* Published stories cannot be changed
* Later duplicate sources can be added
* Dashboard shows published stories and turnaround time

# Story Grouping

## Approach

I used a deterministic text-similarity approach:

**Headline + Body → TF-IDF → Cosine Similarity → Similarity Threshold → Union-Find → Story Groups**

The implementation is available in:

`ml/clustering.py`

### Why TF-IDF + Cosine Similarity?

For this 48-hour prototype, I chose a lightweight and explainable approach rather than depending on an external AI API for story grouping.

The advantages are:

* Deterministic results
* Low cost
* Fast execution
* Easy to run locally
* Easy to debug
* Easy to explain

The grouping is intended as a first-pass recommendation for the newsroom rather than a replacement for editorial judgment.

## Current Limitation

Text similarity does not always mean two items describe the same real-world event.

Two different events can contain similar words, while two reports about the same event can use very different wording.

With more time, I would improve the grouping by incorporating additional signals such as:

* Named entities
* Locations
* Dates and timestamps
* Semantic similarity
* A larger labelled evaluation dataset


# Editorial Workflow

The system separates responsibilities between the three newsroom roles.

### Reporter

**Review → Edit → Submit**

The reporter prepares the first-pass brief and sends it to the editor.

### Editor

**Review → Rewrite/Reject → Publish**

The editor has final publishing authority.

### Desk Head

**Monitor → Analyze**

The desk head can see what has been published and review publication turnaround.


## Important Product Decisions

* **Reporter cannot publish:** Only editors can publish stories; permissions are checked on the backend.
* **Published stories are locked:** Published content and publication time cannot be changed.
* **Later duplicates:** New duplicates are added as sources without changing the published story.
* **Human editorial control:** Grouping and drafting assist the newsroom, while the final content is reviewed by humans.

## Seed Data

Since no dataset was provided, I created realistic sample news items with:

* Multiple versions of the same event
* Different wording and source types
* Similar-looking but different stories

This demonstrates both duplicate grouping and avoiding incorrect merges.


# Tech Stack

* **Backend:** Python / Flask
* **Frontend:** HTML / CSS / Flask templates
* **Database:** SQLite
* **Clustering:** Python + scikit-learn using TF-IDF and cosine similarity
* **Seed Data:** JSON
* **Deployment:** Render

### Main Files

* `app.py` — main application and newsroom workflow
* `ml/clustering.py` — story grouping implementation
* `templates/` — application UI/templates
* `static/` — frontend assets
* `requirements.txt` — Python dependencies


# AI Tools Used

I used **Claude** during development for:

* Initial project scaffolding
* Iterating on the story-grouping implementation
* Debugging
* UI development and iteration
* UX improvements

I used AI as a development assistant, while making the product decisions, workflow decisions, assumptions, and trade-offs for the implementation.

## Challenges

* **Duplicate vs similar stories:** Distinguishing the same event from similar but separate stories.
* **Post-publication duplicates:** Adding later sources without changing published content.
* **Draft quality:** Ensuring first-pass briefs are useful while keeping human review.
* **Editorial permissions:** Preventing reporters from bypassing the editor and publishing directly.

## What I Would Do With Another Week

* Improve grouping using **entities, location, dates, and semantic similarity**.
* Evaluate clustering with **precision, recall, false merges, and missed duplicates**.
* Improve brief generation and add **draft quality validation**.
* Add **real authentication, automated tests, monitoring, and better error handling**.
* Support additional inputs such as **screenshots and photos**.

# Running Locally


```bash
git clone https://github.com/vinodinib04/news-desk.git
cd news-desk

python -m venv venv
```

### Install dependencies

```bash
pip install -r requirements.txt
```

## Run

```bash
python app.py
```

Open the local URL shown by Flask in your browser.

---

# Conclusion

The main goal of this project was to build a complete working newsroom workflow within the 48-hour constraint.

I prioritized:

* Duplicate story grouping
* Source visibility
* Reporter/editor workflow
* Editorial control
* Published-story immutability
* Post-publication duplicate handling
* Desk-head reporting

The current implementation is a prototype, with the main future areas being more accurate event detection, better brief generation, stronger evaluation, and production-level authentication and monitoring.
