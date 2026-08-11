"""
Turns raw, messy Last.fm tags into a numeric feature vector suitable
for clustering.

Raw tags are noisy: a track might come back tagged with genre labels
("indie pop"), mood labels ("chill"), meta labels ("seen live", "2026"),
and near-duplicates ("chill", "chillout", "chill vibes"). This module
filters down to a mood-relevant vocabulary and normalizes near-duplicates
before vectorizing.
"""

import numpy as np

# Curated mood vocabulary -- tune this list based on what you actually
# see in your pulled data. Keys are canonical labels; values are raw
# tag variants that should be folded into that label.
MOOD_VOCAB = {
    "chill": ["chill", "chillout", "chill vibes", "relaxing", "mellow"],
    "energetic": ["energetic", "upbeat", "high energy", "hype"],
    "happy": ["happy", "feel good", "uplifting", "fun"],
    "sad": ["sad", "melancholy", "melancholic", "heartbreak", "emotional"],
    "aggressive": ["aggressive", "angry", "intense", "hard"],
    "romantic": ["romantic", "love songs", "sensual"],
    "dark": ["dark", "moody", "brooding"],
    "party": ["party", "dance", "danceable", "club"],
    "dreamy": ["dreamy", "atmospheric", "ambient", "ethereal"],
    "nostalgic": ["nostalgic", "throwback", "sentimental"],
}

# Reverse lookup: raw tag string -> canonical mood label
_RAW_TO_CANONICAL = {
    variant: canonical
    for canonical, variants in MOOD_VOCAB.items()
    for variant in variants
}

CANONICAL_LABELS = list(MOOD_VOCAB.keys())


def normalize_tags(raw_tags):
    """Fold raw tag variants into canonical mood labels, summing counts.

    raw_tags: list of {"name": str, "count": int}
    Returns: dict of {canonical_label: summed_count}
    """
    scores = {label: 0 for label in CANONICAL_LABELS}
    for tag in raw_tags:
        name = tag["name"].lower().strip()
        canonical = _RAW_TO_CANONICAL.get(name)
        if canonical:
            scores[canonical] += tag["count"]
    return scores


def build_feature_matrix(tracks_with_tags):
    """Build a numeric feature matrix for clustering.

    tracks_with_tags: dict of {track_id: [raw_tag_dicts]}
    Returns: (track_ids list, feature_matrix as np.ndarray)

    Each row is a track; each column is a canonical mood label's
    normalized score (0-1 within that track, so tracks with more total
    tag volume don't dominate just from being more popular).
    """
    track_ids = list(tracks_with_tags.keys())
    matrix = []

    for tid in track_ids:
        scores = normalize_tags(tracks_with_tags[tid])
        values = np.array([scores[label] for label in CANONICAL_LABELS], dtype=float)
        total = values.sum()
        if total > 0:
            values = values / total  # normalize so it's a "mood profile", not raw volume
        matrix.append(values)

    return track_ids, np.array(matrix)
