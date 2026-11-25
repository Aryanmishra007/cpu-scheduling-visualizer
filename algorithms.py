from collections import deque
from dataclasses import dataclass
from heapq import heappop, heappush


ALGORITHMS = {
    "FCFS": "First-Come, First-Served",
    "SJF": "Shortest Job First (non-preemptive)",
    "SRTF": "Shortest Remaining Time First",
    "Priority NP": "Priority (non-preemptive)",
    "Priority P": "Priority (preemptive)",
    "RR": "Round Robin",
}


@dataclass(frozen=True)
class Process:
    pid: str
    arrival: int
    burst: int
    priority: int


@dataclass(frozen=True)
class Slice:
    pid: str | None
    start: int
    end: int


def schedule(
    processes: list[Process],
    algorithm: str,
    quantum: int = 3,
    lower_is_higher: bool = True,
) -> list[Slice]:
    """Return the scheduling timeline, including idle time from time zero."""
    if algorithm not in ALGORITHMS:
        raise ValueError(f"Unknown algorithm: {algorithm}")
    if not processes:
        raise ValueError("Add at least one process.")
    if any(process.arrival < 0 or process.burst <= 0 for process in processes):
        raise ValueError("Arrivals must be nonnegative and bursts must be positive.")
    if len({process.pid for process in processes}) != len(processes):
        raise ValueError("Process IDs must be unique.")
    if quantum < 1:
        raise ValueError("The Round Robin quantum must be positive.")

    # Python's stable sort preserves input order among simultaneous arrivals.
    ordered = sorted(processes, key=lambda process: process.arrival)
    remaining = [process.burst for process in ordered]
    ready_queue: deque[int] = deque()
    ready_heap: list[tuple[int, int]] = []
    timeline: list[Slice] = []
    next_arrival = 0
    time = 0

    fifo = algorithm in {"FCFS", "RR"}
    preemptive = algorithm in {"SRTF", "Priority P"}

    def rank(index: int) -> int:
        if algorithm in {"SJF", "SRTF"}:
            return remaining[index]
        priority = ordered[index].priority
        return priority if lower_is_higher else -priority

    def enqueue(index: int) -> None:
        if fifo:
            ready_queue.append(index)
        else:
            heappush(ready_heap, (rank(index), index))

    def admit_arrivals() -> None:
        nonlocal next_arrival
        while next_arrival < len(ordered) and ordered[next_arrival].arrival <= time:
            enqueue(next_arrival)
            next_arrival += 1

    while next_arrival < len(ordered) or ready_queue or ready_heap:
        admit_arrivals()

        if not ready_queue and not ready_heap:
            arrival = ordered[next_arrival].arrival
            timeline.append(Slice(None, time, arrival))
            time = arrival
            continue

        index = ready_queue.popleft() if fifo else heappop(ready_heap)[1]
        start = time

        if preemptive:
            while remaining[index]:
                completion = time + remaining[index]
                if next_arrival < len(ordered):
                    stop = min(completion, ordered[next_arrival].arrival)
                else:
                    stop = completion

                remaining[index] -= stop - time
                time = stop
                admit_arrivals()

                # Equal ranks leave the current process on the CPU.
                if remaining[index] and ready_heap and ready_heap[0][0] < rank(index):
                    break
        else:
            duration = remaining[index]
            if algorithm == "RR":
                duration = min(duration, quantum)
            time += duration
            remaining[index] -= duration

            # At a quantum boundary, new arrivals queue before the expired job.
            admit_arrivals()

        timeline.append(Slice(ordered[index].pid, start, time))
        if remaining[index]:
            enqueue(index)

    return timeline
