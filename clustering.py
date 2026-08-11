"""
Mood clustering on tag-derived feature vectors.

Run find_optimal_k() first (produces an elbow plot) to pick a k value,
then run cluster_tracks() with that k for the actual assignment.
"""

import numpy as np
from sklearn.cluster import KMeans

from tag_features import CANONICAL_LABELS


def find_optimal_k(feature_matrix, k_range=range(2, 9)):
    """Compute inertia for a range of k values so you can eyeball the elbow.

    Returns a list of (k, inertia) tuples. Plot these (k on x, inertia on y)
    and look for where the curve starts to flatten out -- that's your k.
    """
    results = []
    for k in k_range:
        km = KMeans(n_clusters=k, random_state=42, n_init=10)
        km.fit(feature_matrix)
        results.append((k, km.inertia_))
    return results


def cluster_tracks(feature_matrix, k):
    """Run k-means with a chosen k. Returns (labels, cluster_centers)."""
    km = KMeans(n_clusters=k, random_state=42, n_init=10)
    labels = km.fit_predict(feature_matrix)
    return labels, km.cluster_centers_


def describe_clusters(cluster_centers):
    """For each cluster center, name the top 2 mood dimensions that define it.

    This gives you a human-readable label like 'energetic + party' instead
    of just 'cluster 3' -- run this once after clustering to build your
    cluster_id -> label mapping.
    """
    descriptions = {}
    for cluster_id, center in enumerate(cluster_centers):
        top_indices = np.argsort(center)[::-1][:2]
        top_labels = [CANONICAL_LABELS[i] for i in top_indices if center[i] > 0.05]
        if not top_labels:
            descriptions[cluster_id] = "mixed/unclear"
        else:
            descriptions[cluster_id] = " + ".join(top_labels)
    return descriptions
