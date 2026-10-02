"""Cluster-Enhanced Nearest Neighbor (CENN) - the custom heuristic.

Three phases, exactly as described in the report:
  1. Cluster   - group nearby customers with k-means, one cluster per vehicle,
                 then fix any cluster whose total demand is over capacity.
  2. Route     - inside each cluster, build a route with Nearest Neighbor
                 (always drive to the closest customer not yet visited).
  3. Refine    - improve each route with 2-opt (reverse a chunk of the route
                 whenever that makes it shorter) until nothing improves.

(The original code only did plain Nearest Neighbor - the clustering and 2-opt
described in the report were never actually implemented.)
"""

import math
import time

import numpy as np
from sklearn.cluster import KMeans

from .instances import DEPOT
from .utils import build_distance_matrix, distance, total_length


def _cluster_customers(points, demands, Q, seed):
    """Phase 1: split customers into capacity-feasible groups."""
    customers = list(range(1, len(points)))
    k = max(1, math.ceil(sum(demands) / Q))  # minimum number of vehicles

    coords = np.array([points[c] for c in customers])
    km = KMeans(n_clusters=k, n_init=10, random_state=seed).fit(coords)
    clusters = [[] for _ in range(k)]
    for c, label in zip(customers, km.labels_):
        clusters[label].append(c)
    centers = [tuple(cen) for cen in km.cluster_centers_]

    def load(cl):
        return sum(demands[c] for c in cl)

    # Capacity repair: while a cluster is too heavy, move its customer that is
    # farthest from the cluster centre to the closest cluster that has room.
    while True:
        heavy = [i for i, cl in enumerate(clusters) if load(cl) > Q]
        if not heavy:
            break
        h = heavy[0]
        c = max(clusters[h], key=lambda c: distance(points[c], centers[h]))
        clusters[h].remove(c)

        options = [
            i for i in range(len(clusters))
            if i != h and load(clusters[i]) + demands[c] <= Q
        ]
        if options:
            best = min(options, key=lambda i: distance(points[c], centers[i]))
            clusters[best].append(c)
        else:  # nobody has room: open a new vehicle
            clusters.append([c])
            centers.append(points[c])

    return [cl for cl in clusters if cl]


def _nearest_neighbor(cluster, dist):
    """Phase 2: greedy route starting from the depot."""
    route, unvisited, current = [], set(cluster), 0
    while unvisited:
        nxt = min(unvisited, key=lambda c: dist[current][c])
        route.append(nxt)
        unvisited.remove(nxt)
        current = nxt
    return route


def _two_opt(route, dist, max_passes=100):
    """Phase 3: keep reversing segments while it shortens the route."""
    tour = [0] + route + [0]  # include the depot at both ends
    for _ in range(max_passes):
        improved = False
        for i in range(1, len(tour) - 2):
            for j in range(i + 1, len(tour) - 1):
                a, b = tour[i - 1], tour[i]
                c, d = tour[j], tour[j + 1]
                # Replace edges (a,b) and (c,d) with (a,c) and (b,d)?
                change = dist[a][c] + dist[b][d] - dist[a][b] - dist[c][d]
                if change < -1e-9:
                    tour[i:j + 1] = reversed(tour[i:j + 1])
                    improved = True
        if not improved:  # termination: no more improvement
            break
    return tour[1:-1]


def solve_cenn(instance, seed=0):
    points = [DEPOT] + instance["customers"]
    demands = [0] + instance["demands"]
    Q = instance["capacity"]

    start = time.perf_counter()
    dist = build_distance_matrix(points)
    clusters = _cluster_customers(points, demands, Q, seed)
    routes = [_two_opt(_nearest_neighbor(cl, dist), dist) for cl in clusters]
    runtime = time.perf_counter() - start

    return {
        "routes": routes,
        "distance": total_length(routes, dist),
        "time": runtime,
    }
