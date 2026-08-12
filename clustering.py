"""
Mood clustering on tag-derived feature vectors.

Run find_optimal_k() first (produces an elbow plot) to pick a k value,
then run cluster_tracks() with that k for the actual assignment.
"""

import numpy as np
from sklearn.cluster import KMeans


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


def describe_clusters(cluster_centers, vocabulary, top_k=3):
    """For each cluster center, name the top-k tags that define it.

    vocabulary: the same tag list passed to build_feature_matrix, in the
    same order -- needed to translate feature indices back into tag names.

    This gives you a human-readable label like 'indie rock, alternative,
    dream pop' instead of just 'cluster 3' -- run this once after
    clustering to build your cluster_id -> label mapping.
    """
    descriptions = {}
    for cluster_id, center in enumerate(cluster_centers):
        top_indices = np.argsort(center)[::-1][:top_k]
        top_labels = [vocabulary[i] for i in top_indices if center[i] > 0.03]
        descriptions[cluster_id] = ", ".join(top_labels) if top_labels else "mixed/unclear"
    return descriptions
