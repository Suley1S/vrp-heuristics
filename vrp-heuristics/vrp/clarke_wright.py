"""Clarke-Wright Savings heuristic (parallel version).

Idea: start with one tiny route per customer (depot -> i -> depot).
Joining the routes of i and j into depot -> ... i -> j ... -> depot
saves   s(i, j) = d(0, i) + d(0, j) - d(i, j)   distance.
Go through the pairs from biggest saving to smallest and merge whenever
it is allowed.

A merge is allowed only if:
  1. i and j are currently on different routes,
  2. the combined load fits in one vehicle, and
  3. i and j are both at an END of their routes (next to the depot).
     Rule 3 is what the original code was missing - without it, routes
     were glued together in the wrong places, which is why the old
     Clarke-Wright results were so far from optimal.
"""

import time

from .instances import DEPOT
from .utils import build_distance_matrix, total_length


def solve_clarke_wright(instance):
    points = [DEPOT] + instance["customers"]
    demands = [0] + instance["demands"]
    Q = instance["capacity"]
    n = len(points)

    start = time.perf_counter()
    dist = build_distance_matrix(points)

    # Every customer starts on its own route.
    route_of = {c: c for c in range(1, n)}        # customer -> route id
    routes = {c: [c] for c in range(1, n)}         # route id -> list of customers
    loads = {c: demands[c] for c in range(1, n)}   # route id -> total demand

    savings = [
        (dist[0][i] + dist[0][j] - dist[i][j], i, j)
        for i in range(1, n)
        for j in range(i + 1, n)
    ]
    savings.sort(reverse=True)

    for s, i, j in savings:
        if s <= 0:
            break  # merging no longer saves anything
        ri, rj = route_of[i], route_of[j]
        if ri == rj:
            continue
        if loads[ri] + loads[rj] > Q:
            continue

        a, b = routes[ri], routes[rj]
        # i and j must be endpoints of their routes.
        if i not in (a[0], a[-1]) or j not in (b[0], b[-1]):
            continue

        # Flip the routes so that a ends with i and b starts with j.
        # (Distances are symmetric, so reversing a route doesn't change its length.)
        if a[-1] != i:
            a.reverse()
        if b[0] != j:
            b.reverse()

        merged = a + b
        routes[ri] = merged
        loads[ri] += loads[rj]
        del routes[rj], loads[rj]
        for c in b:
            route_of[c] = ri

    final_routes = list(routes.values())
    runtime = time.perf_counter() - start
    return {
        "routes": final_routes,
        "distance": total_length(final_routes, dist),
        "time": runtime,
    }
