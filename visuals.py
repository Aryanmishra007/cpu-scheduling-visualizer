import pandas as pd
import plotly.colors as colors
import plotly.graph_objects as go
from plotly.subplots import make_subplots

from algorithms import Process, Slice
from metrics import AVG_TAT, AVG_WT, UTILIZATION, context_switches


def gantt_chart(processes: list[Process], timeline: list[Slice]) -> go.Figure:
    palette = colors.qualitative.Dark24
    color_by_pid = {
        process.pid: (
            palette[index]
            if index < len(palette)
            else f"hsl({round(index * 137.508) % 360}, 68%, 60%)"
        )
        for index, process in enumerate(processes)
    }

    figure = go.Figure()
    groups: dict[str | None, list[Slice]] = {}
    for segment in timeline:
        groups.setdefault(segment.pid, []).append(segment)

    for pid, segments in groups.items():
        label = "Idle" if pid is None else pid
        figure.add_trace(
            go.Bar(
                name=label,
                y=["CPU"] * len(segments),
                x=[segment.end - segment.start for segment in segments],
                base=[segment.start for segment in segments],
                customdata=[[segment.start, segment.end] for segment in segments],
                text=[label] * len(segments),
                textposition="inside",
                insidetextanchor="middle",
                orientation="h",
                width=0.48,
                marker={
                    "color": "#8C96A5" if pid is None else color_by_pid[pid],
                    "line": {"color": "#FCFCFC", "width": 1},
                },
                hovertemplate=(
                    "%{fullData.name}<br>Start: %{customdata[0]}"
                    "<br>End: %{customdata[1]}<br>Duration: %{x}<extra></extra>"
                ),
            )
        )

    switches = context_switches(timeline)
    if switches:
        figure.add_trace(
            go.Scatter(
                name="Context switch",
                x=[time for time, _, _ in switches],
                y=[1] * len(switches),
                yaxis="y2",
                mode="markers",
                marker={"symbol": "diamond", "size": 8, "color": "#8839EF"},
                customdata=[[source, target] for _, source, target in switches],
                hovertemplate=(
                    "Switch at %{x}<br>%{customdata[0]} → %{customdata[1]}<extra></extra>"
                ),
            )
        )

    figure.update_layout(
        barmode="overlay",
        uniformtext={"minsize": 10, "mode": "hide"},
        height=310,
        xaxis={"title": "Time units", "range": [0, timeline[-1].end], "rangemode": "tozero"},
        yaxis={"fixedrange": True},
        yaxis2={
            "overlaying": "y",
            "range": [0, 1.25],
            "visible": False,
            "fixedrange": True,
        },
        legend={"orientation": "h", "y": -0.35},
        margin={"l": 35, "r": 20, "t": 25, "b": 65},
    )
    return figure


def comparison_chart(comparison: pd.DataFrame) -> go.Figure:
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.15,
        subplot_titles=("Waiting and turnaround time", "CPU utilization"),
    )
    for metric, color in ((AVG_WT, "#5468FF"), (AVG_TAT, "#00A389")):
        figure.add_trace(
            go.Bar(
                x=comparison["Algorithm"],
                y=comparison[metric],
                name=metric,
                marker_color=color,
                hovertemplate="%{x}<br>%{y:.2f} time units<extra>%{fullData.name}</extra>",
            ),
            row=1,
            col=1,
        )

    figure.add_trace(
        go.Bar(
            x=comparison["Algorithm"],
            y=comparison[UTILIZATION],
            name="CPU utilization",
            marker_color="#AD58D6",
            hovertemplate="%{x}<br>%{y:.2f}%<extra>CPU utilization</extra>",
        ),
        row=2,
        col=1,
    )
    figure.update_yaxes(title_text="Time units", rangemode="tozero", row=1, col=1)
    figure.update_yaxes(title_text="Percent", range=[0, 105], row=2, col=1)
    figure.update_layout(barmode="group", height=540, legend={"orientation": "h"})
    return figure
