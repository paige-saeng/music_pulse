"""
Genre/style feature vectorization from raw Last.fm tags.

v2 -- pivoted away from a fixed mood vocabulary (chill/energetic/sad/...)
after real data showed Last.fm tagging is overwhelmingly genre-based, not
mood-based, with a long tail of noise tags (memes, usernames, one-offs
like "donald trump" or random strings applied by a single user).

This version builds its vocabulary FROM the data itself: the most common
tags across the tracked set, filtered to tags that appear on more than
one track (this is what drops the one-off noise tags).
"""

from collections import Counter
import numpy as np

MIN_TRACK_COUNT = 2   # a tag must appear on at least this many DIFFERENT tracks to count as signal
TOP_N_TAGS = 40        # size of the feature vocabulary


def build_vocabulary(tracks_with_tags, min_track_count=MIN_TRACK_COUNT, top_n=TOP_N_TAGS):
    """Determine the feature vocabulary from the data itself.

    tracks_with_tags: dict of {track_id: [raw_tag_dicts]}
    Returns: list of tag names, ordered by how many distinct tracks use them
    (most common first).
    """
    track_doc_counts = Counter()
    for tags in tracks_with_tags.values():
        # count each tag once per track, regardless of its tag_count weight --
        # this measures how many DIFFERENT tracks use the tag, not total volume
        seen_in_this_track = set(t["name"].lower().strip() for t in tags)
        track_doc_counts.update(seen_in_this_track)

    filtered = [(tag, count) for tag, count in track_doc_counts.items()
                if count >= min_track_count]
    filtered.sort(key=lambda x: x[1], reverse=True)

    return [tag for tag, _ in filtered[:top_n]]


def build_feature_matrix(tracks_with_tags, vocabulary):
    """Build a numeric feature matrix for clustering, using the given vocabulary.

    tracks_with_tags: dict of {track_id: [raw_tag_dicts]}
    vocabulary: list of tag names (from build_vocabulary)
    Returns: (track_ids list, feature_matrix as np.ndarray)

    Each row is a track; each column is one vocabulary tag's normalized
    weight (based on Last.fm's tag_count), so tracks with more total tag
    volume don't dominate just from being more heavily tagged overall.
    Tracks with no vocabulary-matching tags get an all-zero row -- these
    will cluster together by virtue of being identical, which is itself
    a meaningful "untagged/unclassifiable" group worth knowing about.
    """
    track_ids = list(tracks_with_tags.keys())
    vocab_index = {tag: i for i, tag in enumerate(vocabulary)}
    matrix = np.zeros((len(track_ids), len(vocabulary)))

    for row, tid in enumerate(track_ids):
        for t in tracks_with_tags[tid]:
            name = t["name"].lower().strip()
            if name in vocab_index:
                matrix[row, vocab_index[name]] = t.get("count", 0)

    row_sums = matrix.sum(axis=1, keepdims=True)
    row_sums[row_sums == 0] = 1  # avoid divide-by-zero for untagged tracks
    matrix = matrix / row_sums

    return track_ids, matrix
