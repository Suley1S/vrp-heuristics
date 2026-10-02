"""Exact method: Mixed-Integer Linear Programming (MILP) with PuLP + CBC.

Formulation: two-index CVRP with Miller-Tucker-Zemlin (MTZ) constraints.

  x[i, j] = 1 if some vehicle drives directly from node i to node j
  u[i]    = load the vehicle has delivered after visiting customer i

The MTZ constraints do two jobs at once: they forbid loops that never
return to the depot ("subtours") AND they enforce vehicle capacity,
because u[i] is bounded between demand[i] and the capacity Q.
"""

import math
import time

import pulp

from .instances import DEPOT
from .utils import build_distance_matrix, total_length


def solve_milp(instance, time_limit=60, start_routes=None):
    """Solve one instance exactly (or as well as possible within time_limit seconds).

    start_routes: optional known solution (e.g. from Clarke-Wright) given to the
    solver as a starting point ("warm start"). It doesn't change the optimal
    answer, it just means a time-limited run can never end up worse than it.

    Returns a dict with routes, distance, runtime and whether optimality was proven.
    """
    points = [DEPOT] + instance["customers"]
    demands = [0] + instance["demands"]
    Q = instance["capacity"]
    n = len(points)
    dist = build_distance_matrix(points)

    nodes = range(n)
    customers = range(1, n)
    # Only real arcs: no "drive from i to i" variables.
    arcs = [(i, j) for i in nodes for j in nodes if i != j]

    prob = pulp.LpProblem("CVRP", pulp.LpMinimize)
    x = pulp.LpVariable.dicts("x", arcs, cat="Binary")
    # FIX: u now has an upper bound of Q. In the original code u had no upper
    # bound, so the capacity limit was never actually enforced.
    u = pulp.LpVariable.dicts("u", customers, lowBound=0, upBound=Q)

    # Objective: minimise total distance driven.
    prob += pulp.lpSum(dist[i][j] * x[i, j] for (i, j) in arcs)

    # Every customer is entered exactly once and left exactly once.
    for j in customers:
        prob += pulp.lpSum(x[i, j] for i in nodes if i != j) == 1
    for i in customers:
        prob += pulp.lpSum(x[i, j] for j in nodes if j != i) == 1

    # FIX: vehicles leaving the depot must equal vehicles coming back.
    leaving = pulp.lpSum(x[0, j] for j in customers)
    returning = pulp.lpSum(x[j, 0] for j in customers)
    prob += leaving == returning
    # Helpful extra bound: we need at least ceil(total demand / Q) vehicles.
    prob += leaving >= math.ceil(sum(demands) / Q)

    # MTZ subtour-elimination + capacity constraints.
    for i in customers:
        prob += u[i] >= demands[i]  # FIX: missing lower bound in the original
    for i in customers:
        for j in customers:
            if i != j:
                prob += u[i] - u[j] + Q * x[i, j] <= Q - demands[j]

    if start_routes:
        _set_warm_start(start_routes, x, u, arcs, demands)

    start = time.perf_counter()
    prob.solve(pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit,
                                 warmStart=bool(start_routes)))
    runtime = time.perf_counter() - start

    if prob.sol_status not in (pulp.LpSolutionOptimal, pulp.LpSolutionIntegerFeasible):
        return {"routes": None, "distance": None, "time": runtime, "proven_optimal": False}

    # Rebuild the routes by following the arcs that were chosen (x = 1).
    succ = {}
    for (i, j) in arcs:
        if pulp.value(x[i, j]) > 0.5:
            succ.setdefault(i, []).append(j)

    routes = []
    for first in succ.get(0, []):
        route, node = [], first
        while node != 0:
            route.append(node)
            node = succ[node][0]
        routes.append(route)

    # If CBC hit the time limit, the answer is good but not *proven* best.
    proven = prob.sol_status == pulp.LpSolutionOptimal and runtime < time_limit * 0.98
    return {
        "routes": routes,
        "distance": total_length(routes, dist),
        "time": runtime,
        "proven_optimal": proven,
    }


def _set_warm_start(routes, x, u, arcs, demands):
    """Translate a list of routes into starting values for x and u."""
    used = set()
    for route in routes:
        tour = [0] + route + [0]
        used.update(zip(tour, tour[1:]))
        load = 0
        for c in route:
            load += demands[c]
            u[c].setInitialValue(load)
    for arc in arcs:
        x[arc].setInitialValue(1 if arc in used else 0)
