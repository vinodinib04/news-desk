from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity


def group_news_items(news_items, threshold=0.19):
    """
    Groups raw incoming items that most likely describe the same
    real-world event, so a reporter isn't stuck reading 60 items
    one by one.

    Approach: TF-IDF over headline + body (unigrams, sublinear term
    frequency), cosine similarity between every pair, then union-find:
    any pair clearing `threshold` gets merged into the same connected
    component. That's what lets a chain of items (A~B, B~C) end up in
    one group even if A and C alone don't score high against each other -
    closer to how a person would actually judge "these are the same
    event" than a naive nearest-neighbour pass.

    This is intentionally simple and explainable rather than a black
    box - it's a first pass a reporter is expected to sanity check, not
    a final answer. Two items with real overlapping vocabulary (same
    event, different wording) score high; two similar-but-different
    events (e.g. two unrelated earthquakes) usually score lower because
    the specific nouns (place names, entities) differ. Sometimes the
    wording is different enough that truly-the-same event doesn't
    auto-cluster at all - that's why the reporter and editor also have a
    manual "same event as another story?" merge control in the UI.
    """

    if not news_items:
        return []

    if len(news_items) == 1:
        return [[news_items[0]]]

    texts = [item["headline"] + " " + item["content"] for item in news_items]

    vectorizer = TfidfVectorizer(stop_words="english", ngram_range=(1, 1), sublinear_tf=True)
    matrix = vectorizer.fit_transform(texts)
    similarity = cosine_similarity(matrix)

    n = len(news_items)
    parent = list(range(n))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    def union(a, b):
        ra, rb = find(a), find(b)
        if ra != rb:
            parent[ra] = rb

    for i in range(n):
        for j in range(i + 1, n):
            if similarity[i][j] >= threshold:
                union(i, j)

    clusters = {}
    for i in range(n):
        root = find(i)
        clusters.setdefault(root, []).append(i)

    return [[news_items[index] for index in group] for group in clusters.values()]