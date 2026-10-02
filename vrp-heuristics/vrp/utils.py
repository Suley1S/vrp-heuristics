"""Small helpers shared by all three solvers.

Conventions used everywhere in this project:
  * Node 0 is the depot, nodes 1..n are customers.
  * A route is a list of customer numbers, e.g. [3, 1, 4].
    The depot is NOT stored in the list - every route implicitly
    starts at the depot and ends back at the depot.
  * A solution is a list of routes (one per vehicle).
"""

import math


def distance(a, b):
    """Straight-line (Euclidean) distance between two (x, y) points."""
    return math.hypot(a[0] - b[0], a[1] - b[1])


def build_distance_matrix(points):
    """dist[i][j] = distance from point i to point j."""
    return [[distance(p, q) for q in points] for p in points]


def route_length(route, dist):
    """Length of depot -> route[0] -> ... -> route[-1] -> depot."""
    if not route:
        return 0.0
    total = dist[0][route[0]]
    for a, b in zip(route, route[1:]):
        total += dist[a][b]
    total += dist[route[-1]][0]
    return total


def total_length(routes, dist):
    return sum(route_length(r, dist) for r in routes)


def validate_solution(routes, demands, capacity):
    """Raise an error if the solution breaks a VRP rule.

    demands[0] must be the depot (0); demands[i] is customer i.
    Checks that every customer is visited exactly once and that no
    vehicle carries more than its capacity.
    """
    n_customers = len(demands) - 1
    seen = [c for r in routes for c in r]

    if sorted(seen) != list(range(1, n_customers + 1)):
        missing = set(range(1, n_customers + 1)) - set(seen)
        repeated = {c for c in seen if seen.count(c) > 1}
        raise ValueError(f"Bad visits. missing={missing}, repeated={repeated}")

    for k, r in enumerate(routes, start=1):
        load = sum(demands[c] for c in r)
        if load > capacity:
            raise ValueError(f"Vehicle {k} is overloaded: {load} > {capacity}")
