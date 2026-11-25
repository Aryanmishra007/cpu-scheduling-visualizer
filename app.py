import csv
import io
import random
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation

import pandas as pd
import streamlit as st

from algorithms import ALGORITHMS, Process
from metrics import (
    AVG_RT,
    AVG_TAT,
    AVG_WT,
    SWITCHES,
    THROUGHPUT,
    UTILIZATION,
    compare,
    recommendations,
)
from visuals import comparison_chart, gantt_chart


COLUMNS = ["process_id", "arrival_time", "burst_time", "priority"]
MAX_PROCESSES = 50
MAX_TOTAL_BURST = 2_000
MAX_ARRIVAL = 1_000_000
PID_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,31}")
DEFAULT_WORKLOAD = [
    ("P1", 0, 9, 3),
    ("P2", 1, 3, 1),
    ("P3", 2, 2, 2),
    ("P4", 6, 4, 1),
    ("P5", 22, 3, 2),
]


def integer_field(value: object, label: str, low: int, high: int) -> int:
    try:
        number = Decimal(str(value).strip())
    except InvalidOperation as error:
        raise ValueError(f"{label} must be an integer from {low} to {high}.") from error

    if not number.is_finite() or not low <= number <= high or number != int(number):
        raise ValueError(f"{label} must be an integer from {low} to {high}.")
    return int(number)


def read_processes(frame: pd.DataFrame) -> list[Process]:
    if not 1 <= len(frame) <= MAX_PROCESSES:
        raise ValueError(f"Enter between 1 and {MAX_PROCESSES} processes.")

    processes = []
    seen = set()
    for row_number, row in enumerate(frame[COLUMNS].itertuples(index=False), start=1):
        raw_pid, arrival, burst, priority = row
        pid = "" if pd.isna(raw_pid) else str(raw_pid).strip()

        if PID_PATTERN.fullmatch(pid) is None or pid.casefold() == "idle":
            raise ValueError(
                f"Row {row_number}: use 1–32 letters, digits, underscores, "
                "periods or hyphens for the ID, starting with a letter or digit. "
                "The name Idle is reserved."
            )
        if pid in seen:
            raise ValueError(f"Row {row_number}: duplicate process ID {pid}.")
        seen.add(pid)

        processes.append(
            Process(
                pid,
                integer_field(arrival, f"Row {row_number} arrival time", 0, MAX_ARRIVAL),
                integer_field(burst, f"Row {row_number} burst time", 1, MAX_TOTAL_BURST),
                integer_field(priority, f"Row {row_number} priority", -9999, 9999),
            )
        )

    if sum(process.burst for process in processes) > MAX_TOTAL_BURST:
        raise ValueError(f"Total burst time must be at most {MAX_TOTAL_BURST} units.")
    return processes


def import_workload(raw: bytes) -> list[Process]:
    if len(raw) > 64 * 1024:
        raise ValueError("Upload a CSV of at most 64 KiB.")

    try:
        with io.StringIO(raw.decode("utf-8-sig"), newline="") as stream:
            reader = csv.reader(stream, strict=True)
            header = [column.strip() for column in next(reader, [])]
            if len(header) != len(COLUMNS) or set(header) != set(COLUMNS):
                raise ValueError(f"Required CSV headers: {', '.join(COLUMNS)}.")

            rows = []
            for row in reader:
                if not row or not any(cell.strip() for cell in row):
                    continue
                if len(row) != len(COLUMNS):
                    raise ValueError(f"CSV line {reader.line_num} needs four fields.")
                rows.append(row)
                if len(rows) > MAX_PROCESSES:
                    raise ValueError(f"Import at most {MAX_PROCESSES} processes.")
    except (UnicodeError, csv.Error) as error:
        raise ValueError(f"Could not read the CSV as UTF-8: {error}") from error

    return read_processes(pd.DataFrame(rows, columns=header))


def replace_editor(rows: list[tuple[str, int, int, int]]) -> None:
    st.session_state.workload = pd.DataFrame(rows, columns=COLUMNS)
    st.session_state.editor_version += 1


def random_workload(count: int) -> list[tuple[str, int, int, int]]:
    return [
        (f"P{index}", random.randint(0, 18), random.randint(1, 12), random.randint(1, 5))
        for index in range(1, count + 1)
    ]


def csv_download(
    label: str,
    frame: pd.DataFrame,
    filename: str,
    timestamp: datetime,
    quantum: int,
    lower_is_higher: bool,
) -> None:
    export = frame.copy()
    export.insert(0, "Generated At (UTC)", timestamp.isoformat(timespec="seconds"))
    export["RR Quantum"] = quantum
    export["Lower Number Is Higher Priority"] = lower_is_higher
    suffix = timestamp.strftime("%Y%m%dT%H%M%S%fZ")
    st.download_button(
        label,
        data=export.to_csv(index=False).encode("utf-8-sig"),
        file_name=f"{filename}_{suffix}.csv",
        mime="text/csv",
        on_click="ignore",
    )


@st.cache_data(max_entries=32, show_spinner=False)
def run_workload(
    processes: tuple[Process, ...], quantum: int, lower_is_higher: bool
):
    return compare(list(processes), quantum, lower_is_higher)


def main() -> None:
    st.set_page_config(page_title="CPU Scheduling Visualizer", layout="wide")
    st.title("CPU Scheduling Visualizer & Performance Analyzer")

    if "workload" not in st.session_state:
        st.session_state.workload = pd.DataFrame(DEFAULT_WORKLOAD, columns=COLUMNS)
        st.session_state.editor_version = 0

    with st.sidebar:
        st.header("Scheduling settings")
        selected = st.selectbox(
            "Algorithm for the timeline",
            options=list(ALGORITHMS),
            format_func=ALGORITHMS.__getitem__,
        )
        quantum = int(st.number_input("Round Robin quantum", 1, MAX_TOTAL_BURST, 3))
        lower_is_higher = st.checkbox("Lower number means higher priority", value=True)

        st.header("Load a workload")
        count = st.slider("Random process count", 5, 10, 6)
        if st.button("Generate random workload"):
            replace_editor(random_workload(count))

        upload = st.file_uploader(
            "Process CSV",
            type="csv",
            help="UTF-8 CSV with process_id, arrival_time, burst_time, priority headers.",
        )
        if st.button("Load CSV into editor", disabled=upload is None) and upload is not None:
            try:
                imported = import_workload(upload.getvalue())
            except ValueError as error:
                st.error(str(error))
            else:
                replace_editor(
                    [(p.pid, p.arrival, p.burst, p.priority) for p in imported]
                )

    st.subheader("Process workload")
    st.caption(
        f"Add or edit rows below. Equal arrivals follow the displayed row order. "
        f"Maximum {MAX_PROCESSES} processes and {MAX_TOTAL_BURST} total burst units."
    )
    editor = st.data_editor(
        st.session_state.workload,
        key=f"process_editor_{st.session_state.editor_version}",
        num_rows="dynamic",
        hide_index=True,
        use_container_width=True,
        column_config={
            "process_id": st.column_config.TextColumn("Process ID", required=True),
            "arrival_time": st.column_config.NumberColumn(
                "Arrival Time", min_value=0, max_value=MAX_ARRIVAL,
                step=1, format="%d", required=True,
            ),
            "burst_time": st.column_config.NumberColumn(
                "Burst Time", min_value=1, max_value=MAX_TOTAL_BURST,
                step=1, format="%d", required=True,
            ),
            "priority": st.column_config.NumberColumn(
                "Priority", min_value=-9999, max_value=9999,
                step=1, format="%d", required=True,
            ),
        },
    )

    try:
        processes = read_processes(editor)
    except ValueError as error:
        st.error(str(error))
        return

    results, comparison = run_workload(tuple(processes), quantum, lower_is_higher)
    timestamp = datetime.now(timezone.utc)
    simulation, analyzer = st.tabs(["Simulation", "Compare All Algorithms"])

    with simulation:
        result = results[selected]
        summary = result.summary
        st.subheader(ALGORITHMS[selected])

        for column, (label, value) in zip(
            st.columns(3),
            (
                ("Average waiting time", f"{summary[AVG_WT]:.2f}"),
                ("Average turnaround time", f"{summary[AVG_TAT]:.2f}"),
                ("Average response time", f"{summary[AVG_RT]:.2f}"),
            ),
        ):
            column.metric(label, value)

        for column, (label, value) in zip(
            st.columns(3),
            (
                ("CPU utilization", f"{summary[UTILIZATION]:.2f}%"),
                ("Throughput (jobs/unit)", f"{summary[THROUGHPUT]:.4f}"),
                ("Total context switches", str(summary[SWITCHES])),
            ),
        ):
            column.metric(label, value)

        st.plotly_chart(gantt_chart(processes, result.timeline), use_container_width=True)
        st.caption(
            "Gray represents idle time. Diamonds mark context switches. "
            "Hover over a slice or switch for exact times. "
            "Utilization and throughput use the full timeline from time zero."
        )
        st.dataframe(result.detail, hide_index=True, use_container_width=True)
        detail_export = result.detail.assign(Algorithm=selected)
        csv_download(
            "Download detailed process metrics CSV",
            detail_export,
            "process_metrics",
            timestamp,
            quantum,
            lower_is_higher,
        )

    with analyzer:
        heading, evidence = recommendations(processes, results, comparison, quantum)
        st.success(heading)
        for note in evidence:
            st.write(note)

        st.dataframe(comparison.round(4), hide_index=True, use_container_width=True)
        st.plotly_chart(comparison_chart(comparison), use_container_width=True)
        csv_download(
            "Download algorithm comparison CSV",
            comparison,
            "algorithm_comparison",
            timestamp,
            quantum,
            lower_is_higher,
        )


if __name__ == "__main__":
    main()
