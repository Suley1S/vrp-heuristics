"""Run all three methods on all 10 instances, check the answers, and save results.

Usage:
    python run_experiments.py                     # full run (MILP gets 60 s per instance)
    python run_experiments.py --milp-time-limit 10
    python run_experiments.py --skip-milp         # heuristics only, takes about a second
"""

import argparse
import csv
import os

import matplotlib

matplotlib.use("Agg")  # save plots to files instead of opening windows
import matplotlib.pyplot as plt

from vrp import (DEPOT, INSTANCES, solve_cenn, solve_clarke_wright, solve_milp,
                 validate_solution)

RESULTS_DIR = "results"


def gap(value, reference):
    """How many % worse than the reference (MILP) solution."""
    if value is None or reference is None:
        return None
    return 100 * (value - reference) / reference


def fmt(v, digits=2):
    return "-" if v is None else f"{v:.{digits}f}"


def plot_routes(instance, solutions, path):
    """Draw each method's routes side by side for one instance."""
    fig, axes = plt.subplots(1, len(solutions), figsize=(5 * len(solutions), 5))
    pts = [DEPOT] + instance["customers"]
    for ax, (name, sol) in zip(axes, solutions.items()):
        for route in sol["routes"]:
            xs = [DEPOT[0]] + [pts[c][0] for c in route] + [DEPOT[0]]
            ys = [DEPOT[1]] + [pts[c][1] for c in route] + [DEPOT[1]]
            ax.plot(xs, ys, "-o", markersize=3, linewidth=1.2)
        ax.plot(*DEPOT, "ks", markersize=9, label="Depot")
        ax.set_title(f"{name}\n{sol['distance']:.1f} distance, {len(sol['routes'])} vehicles")
        ax.set_aspect("equal")
        ax.legend(loc="upper right", fontsize=8)
    fig.suptitle(f"{instance['name']} ({len(instance['customers'])} customers)", fontsize=14)
    fig.tight_layout(rect=(0, 0, 1, 0.93))  # leave room for the big title
    fig.savefig(path, dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--milp-time-limit", type=int, default=60)
    parser.add_argument("--skip-milp", action="store_true")
    args = parser.parse_args()
    os.makedirs(RESULTS_DIR, exist_ok=True)

    rows = []
    for inst in INSTANCES:
        demands = [0] + inst["demands"]
        print(f"\n=== {inst['name']} ({len(inst['customers'])} customers, "
              f"total demand {sum(demands)}, capacity {inst['capacity']}) ===")

        cw = solve_clarke_wright(inst)
        cenn = solve_cenn(inst)
        sols = {}
        if not args.skip_milp:
            # Warm-start the MILP with the better of the two heuristic answers.
            best = min((cw, cenn), key=lambda s: s["distance"])
            sols["MILP"] = solve_milp(inst, time_limit=args.milp_time_limit,
                                      start_routes=best["routes"])
        sols["Clarke-Wright"] = cw
        sols["CENN"] = cenn

        for name, sol in sols.items():
            if sol["routes"] is None:
                print(f"  {name:14s} no solution found")
                continue
            validate_solution(sol["routes"], demands, inst["capacity"])  # raises if broken
            note = ""
            if name == "MILP":
                note = "  (proven optimal)" if sol["proven_optimal"] else "  (time limit hit - best found)"
            print(f"  {name:14s} distance={sol['distance']:8.2f}  vehicles={len(sol['routes'])}"
                  f"  time={sol['time']:.4f}s{note}")

        milp = sols.get("MILP", {})
        ref = milp.get("distance")
        rows.append({
            "instance": inst["name"],
            "customers": len(inst["customers"]),
            "milp_distance": ref,
            "milp_proven_optimal": milp.get("proven_optimal"),
            "milp_time_s": milp.get("time"),
            "cw_distance": sols["Clarke-Wright"]["distance"],
            "cw_vehicles": len(sols["Clarke-Wright"]["routes"]),
            "cw_time_s": sols["Clarke-Wright"]["time"],
            "cw_gap_pct": gap(sols["Clarke-Wright"]["distance"], ref),
            "cenn_distance": sols["CENN"]["distance"],
            "cenn_vehicles": len(sols["CENN"]["routes"]),
            "cenn_time_s": sols["CENN"]["time"],
            "cenn_gap_pct": gap(sols["CENN"]["distance"], ref),
        })

        if inst is INSTANCES[-1] and all(s["routes"] for s in sols.values()):
            plot_routes(inst, sols, os.path.join(RESULTS_DIR, "routes_instance10.png"))

    # ---- Save the table as CSV and as a Markdown table (for the README) ----
    with open(os.path.join(RESULTS_DIR, "results.csv"), "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=rows[0].keys())
        writer.writeheader()
        writer.writerows(rows)

    with open(os.path.join(RESULTS_DIR, "results.md"), "w") as f:
        f.write("| Instance | Customers | MILP | CW | CW gap | CENN | CENN gap | MILP time (s) | CW time (s) | CENN time (s) |\n")
        f.write("|---|---|---|---|---|---|---|---|---|---|\n")
        for r in rows:
            star = "" if r["milp_proven_optimal"] in (True, None) else "*"
            f.write(f"| {r['instance'].split()[-1]} | {r['customers']} | {fmt(r['milp_distance'])}{star} "
                    f"| {fmt(r['cw_distance'])} | {fmt(r['cw_gap_pct'], 1)}% "
                    f"| {fmt(r['cenn_distance'])} | {fmt(r['cenn_gap_pct'], 1)}% "
                    f"| {fmt(r['milp_time_s'], 1)} | {fmt(r['cw_time_s'], 4)} | {fmt(r['cenn_time_s'], 4)} |\n")

    # ---- Plots ----
    sizes = [r["customers"] for r in rows]

    fig, ax = plt.subplots(figsize=(7, 4.5))
    if not args.skip_milp:
        ax.plot(sizes, [r["milp_distance"] for r in rows], "-o", label="MILP (exact / best found)")
    ax.plot(sizes, [r["cw_distance"] for r in rows], "-o", label="Clarke-Wright")
    ax.plot(sizes, [r["cenn_distance"] for r in rows], "-o", label="CENN")
    ax.set_xlabel("Number of customers")
    ax.set_ylabel("Total route length")
    ax.set_title("Solution quality vs problem size")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, "solution_quality.png"), dpi=130)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(7, 4.5))
    if not args.skip_milp:
        ax.plot(sizes, [r["milp_time_s"] for r in rows], "-o", label="MILP")
    ax.plot(sizes, [r["cw_time_s"] for r in rows], "-o", label="Clarke-Wright")
    ax.plot(sizes, [r["cenn_time_s"] for r in rows], "-o", label="CENN")
    ax.set_yscale("log")  # log scale so tiny and huge times both show up
    ax.set_xlabel("Number of customers")
    ax.set_ylabel("Computation time (seconds, log scale)")
    ax.set_title("Computation time vs problem size")
    ax.legend()
    ax.grid(alpha=0.3, which="both")
    fig.tight_layout()
    fig.savefig(os.path.join(RESULTS_DIR, "computation_time.png"), dpi=130)
    plt.close(fig)

    print(f"\nSaved results and plots to ./{RESULTS_DIR}/")


if __name__ == "__main__":
    main()
