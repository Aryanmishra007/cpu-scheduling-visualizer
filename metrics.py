from dataclasses import dataclass
from statistics import mean

import pandas as pd

from algorithms import ALGORITHMS, Process, Slice, schedule


AVG_WT = "Average WT"
AVG_TAT = "Average TAT"
AVG_RT = "Average RT"
UTILIZATION = "CPU Utilization (%)"
THROUGHPUT = "Throughput"
SWITCHES = "Context Switches"


@dataclass(frozen=True)
class Result:
    timeline: list[Slice]
    detail: pd.DataFrame
    summary: dict[str, int | float]


def context_switches(timeline: list[Slice]) -> list[tuple[int, str, str]]:
    switches = []
    for previous, current in zip(timeline, timeline[1:]):
        if (
            previous.pid is not None
            and current.pid is not None
            and previous.pid != current.pid
        ):
            switches.append((current.start, previous.pid, current.pid))
    return switches


def analyze(processes: list[Process], timeline: list[Slice]) -> Result:
    first_start: dict[str, int] = {}
    completion: dict[str, int] = {}
    for segment in timeline:
        if segment.pid is None:
            continue
        first_start.setdefault(segment.pid, segment.start)
        completion[segment.pid] = segment.end

    rows = []
    for process in processes:
        end = completion[process.pid]
        turnaround = end - process.arrival
        rows.append(
            {
                "Process ID": process.pid,
                "AT": process.arrival,
                "BT": process.burst,
                "Priority": process.priority,
                "CT": end,
                "TAT": turnaround,
                "WT": turnaround - process.burst,
                "RT": first_start[process.pid] - process.arrival,
            }
        )

    makespan = timeline[-1].end
    busy_time = sum(
        segment.end - segment.start for segment in timeline if segment.pid is not None
    )
    summary = {
        AVG_WT: mean(row["WT"] for row in rows),
        AVG_TAT: mean(row["TAT"] for row in rows),
        AVG_RT: mean(row["RT"] for row in rows),
        UTILIZATION: 100 * busy_time / makespan,
        THROUGHPUT: len(processes) / makespan,
        SWITCHES: len(context_switches(timeline)),
    }
    return Result(timeline, pd.DataFrame(rows), summary)


def compare(
    processes: list[Process], quantum: int, lower_is_higher: bool
) -> tuple[dict[str, Result], pd.DataFrame]:
    results = {
        name: analyze(processes, schedule(processes, name, quantum, lower_is_higher))
        for name in ALGORITHMS
    }
    comparison = pd.DataFrame(
        [{"Algorithm": name, **result.summary} for name, result in results.items()]
    )
    return results, comparison


def recommendations(
    processes: list[Process],
    results: dict[str, Result],
    comparison: pd.DataFrame,
    quantum: int,
) -> tuple[str, list[str]]:
    # All means use the same workload size, so integer sums give exact ties.
    def score(name: str) -> tuple[int, int, int]:
        result = results[name]
        return (
            int(result.detail["WT"].sum()),
            int(result.detail["RT"].sum()),
            int(result.summary[SWITCHES]),
        )

    best_score = min(score(name) for name in results)
    winners = [name for name in results if score(name) == best_score]
    best = results[winners[0]].summary
    headline = (
        f"Recommended: {', '.join(winners)}"
        if len(winners) == 1
        else f"Joint recommendation: {', '.join(winners)}"
    )
    notes = [
        f"Ranked by lowest average waiting time, then average response time, "
        f"then switch count. The recommended result has {best[AVG_WT]:.2f} "
        f"average waiting time, {best[AVG_RT]:.2f} average response time, "
        f"and {best[SWITCHES]} context switches."
    ]

    if comparison[UTILIZATION].nunique() == 1:
        notes.append(
            f"All six variants reach {best[UTILIZATION]:.2f}% CPU utilization. "
            "They are work-conserving and the simulation assigns no time to switches."
        )

    fcfs = results["FCFS"]
    first = next(segment for segment in fcfs.timeline if segment.pid is not None)
    shorter = [
        process
        for process in processes
        if process.pid != first.pid
        and process.arrival < first.end
        and process.burst < first.end - first.start
    ]
    if shorter:
        longest_delay = max(first.end - process.arrival for process in shorter)
        notes.append(
            f"FCFS shows a convoy pattern. {len(shorter)} shorter job(s) waited "
            f"behind {first.pid} during its initial {first.end - first.start}-unit run. "
            f"The longest delay attributable to that run was {longest_delay} units."
        )

    for name in ("SJF", "SRTF", "Priority NP", "Priority P"):
        detail = results[name].detail
        delayed = detail.loc[detail["WT"].idxmax()]
        notes.append(
            f"{name}'s longest observed wait was {delayed['WT']} units "
            f"for {delayed['Process ID']}. With continuing arrivals, jobs that rank "
            "poorly can keep being deferred. Every job in this finite workload completed."
        )

    rr = results["RR"].summary
    extra_switches = rr[SWITCHES] - min(comparison[SWITCHES])
    notes.append(
        f"RR with quantum {quantum} averaged {rr[AVG_RT]:.2f} units to first dispatch "
        f"and made {rr[SWITCHES]} switches, {extra_switches} above the lowest "
        "switch count. On a real system, additional switches can add overhead."
    )
    return headline, notes
