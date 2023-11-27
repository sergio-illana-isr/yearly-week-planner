import datetime as dt

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import requests
import streamlit as st
from plotly.subplots import make_subplots

API_TOKEN = "pk_4766013_B2OOP9MBMY9AOWTTZ9MDIJ9XADGEVNS6"
PROJECTS_LIST_ID = "901500802874"
PHASES_LIST_ID = "901500901825"
CONTRACTS_LIST_ID = "901501061808"

projects = pd.DataFrame(
    [
        {
            "id": p["id"],
            "name": p["name"],
            "status": p["status"]["status"],
            "type": next(
                cf["type_config"]["options"][cf["value"]]["name"]
                if "value" in cf
                else None
                for cf in p["custom_fields"]
                if cf["name"] == "Type"
            ),
            "field": next(
                cf["type_config"]["options"][cf["value"]]["name"]
                if "value" in cf
                else None
                for cf in p["custom_fields"]
                if cf["name"] == "Field"
            ),
            "priority": p["priority"]["priority"]
            if p["priority"] is not None
            else None,
        }
        for p in requests.request(
            "GET",
            f"https://api.clickup.com/api/v2/list/{PROJECTS_LIST_ID}/task",
            headers={
                "Authorization": API_TOKEN,
            },
        ).json()["tasks"]
    ]
).astype(
    {
        "id": "string",
        "name": "string",
        "status": "category",
        "type": "category",
        "field": "category",
        "priority": "category",
    }
)
phases = (
    pd.DataFrame(
        [
            {
                "id": p["id"],
                "name": p["name"],
                "status": p["status"]["status"],
                "time_estimate": p["time_estimate"] / 3600000
                if p["time_estimate"] is not None
                else None,
                "duration": next(
                    float(cf["value"]) if "value" in cf else None
                    for cf in p["custom_fields"]
                    if cf["name"] == "Duration"
                ),
                "start_date": dt.datetime.combine(
                    dt.datetime.fromtimestamp(
                        int(p["start_date"]) / 1000, dt.timezone.utc
                    ),
                    dt.time.min,
                    tzinfo=dt.timezone.utc,
                )
                if p["start_date"] is not None
                else None,
                "due_date": dt.datetime.combine(
                    dt.datetime.fromtimestamp(
                        int(p["due_date"]) / 1000, dt.timezone.utc
                    )
                    + dt.timedelta(days=1),
                    dt.time.min,
                    tzinfo=dt.timezone.utc,
                )
                if p["due_date"] is not None
                else None,
                "project_id": next(
                    cf["value"][0]["id"] if "value" in cf else None
                    for cf in p["custom_fields"]
                    if cf["name"] == "Project"
                ),
            }
            for p in requests.request(
                "GET",
                f"https://api.clickup.com/api/v2/list/{PHASES_LIST_ID}/task",
                headers={
                    "Authorization": API_TOKEN,
                },
            ).json()["tasks"]
        ]
    )
    .astype(
        {
            "id": "string",
            "name": "string",
            "status": "category",
            "time_estimate": "timedelta64[h]",
            "duration": "timedelta64[W]",
            "start_date": "datetime64[ns, UTC]",
            "due_date": "datetime64[ns, UTC]",
            "project_id": "string",
        }
    )
    .merge(
        projects[["id", "priority"]],
        left_on="project_id",
        right_on="id",
        suffixes=(None, "_r"),
    )
    .drop(columns="id_r")
    .rename(columns={"priority_x": "priority"})
    .assign(
        priority_order=lambda df: df.priority.map(
            lambda el: {"urgent": 0, "high": 1, "normal": 2, "low": 3}[el]
        )
    )
    .sort_values(
        ["priority_order", "project_id", "start_date"], ascending=[True, True, False]
    )
)
work_load = (
    pd.concat(
        [
            *phases.dropna(subset=["start_date", "due_date"])
            .merge(
                projects[["id", "field"]],
                left_on="project_id",
                right_on="id",
                suffixes=(None, "_y"),
            )
            .apply(
                lambda row: pd.bdate_range(
                    start=row.start_date,
                    end=row.due_date,
                    freq="W-MON",
                    inclusive="left",
                )
                .to_frame(index=False, name="interval")
                .assign(
                    time_estimate=lambda df: row.time_estimate / len(df),
                    field=row.field,
                ),
                axis=1,
            )
            .to_list(),
            pd.bdate_range(
                start=dt.datetime(2023, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc),
                end=dt.datetime(2025, 12, 31, 0, 0, 0, tzinfo=dt.timezone.utc),
                freq="W-MON",
                inclusive="left",
            )
            .to_frame(index=False, name="interval")
            .assign(
                time_estimate=pd.Timedelta(0),
                field="Engineering",
            ),
            pd.bdate_range(
                start=dt.datetime(2023, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc),
                end=dt.datetime(2025, 12, 31, 0, 0, 0, tzinfo=dt.timezone.utc),
                freq="W-MON",
                inclusive="left",
            )
            .to_frame(index=False, name="interval")
            .assign(
                time_estimate=pd.Timedelta(0),
                field="Artificial Intelligent",
            ),
        ]
    )
    .groupby(["field", "interval"], as_index=False)
    .agg({"time_estimate": "sum", "field": lambda gs: gs.iloc[0]})
)
contracts = pd.DataFrame(
    [
        {
            "id": p["id"],
            "name": p["name"],
            "status": p["status"]["status"],
            "start_date": dt.datetime.combine(
                dt.datetime.fromtimestamp(int(p["start_date"]) / 1000, dt.timezone.utc),
                dt.time.min,
                tzinfo=dt.timezone.utc,
            )
            if p["start_date"] is not None
            else None,
            "due_date": dt.datetime.combine(
                dt.datetime.fromtimestamp(int(p["due_date"]) / 1000, dt.timezone.utc)
                + dt.timedelta(days=1),
                dt.time.min,
                tzinfo=dt.timezone.utc,
            )
            if p["due_date"] is not None
            else None,
            "weekly_work_capacity": next(
                float(cf["value"]) if "value" in cf else None
                for cf in p["custom_fields"]
                if cf["name"] == "Weekly work capacity"
            ),
            "field": next(
                cf["type_config"]["options"][cf["value"]]["name"]
                if "value" in cf
                else None
                for cf in p["custom_fields"]
                if cf["name"] == "Field"
            ),
        }
        for p in requests.request(
            "GET",
            f"https://api.clickup.com/api/v2/list/{CONTRACTS_LIST_ID}/task",
            headers={
                "Authorization": API_TOKEN,
            },
        ).json()["tasks"]
    ]
).astype(
    {
        "id": "string",
        "name": "string",
        "status": "string",
        "start_date": "datetime64[ns, UTC]",
        "due_date": "datetime64[ns, UTC]",
        "weekly_work_capacity": "timedelta64[h]",
        "field": "string",
    }
)
work_capacity = (
    pd.concat(
        [
            *contracts.apply(
                lambda row: pd.bdate_range(
                    start=row.start_date,
                    end=row.due_date,
                    freq="W-MON",
                    inclusive="left",
                )
                .to_frame(index=False, name="interval")
                .assign(weekly_work_capacity=row.weekly_work_capacity, field=row.field),
                axis=1,
            ).to_list(),
            pd.bdate_range(
                start=dt.datetime(2023, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc),
                end=dt.datetime(2025, 12, 31, 0, 0, 0, tzinfo=dt.timezone.utc),
                freq="W-MON",
                inclusive="left",
            )
            .to_frame(index=False, name="interval")
            .assign(
                weekly_work_capacity=pd.Timedelta(0),
                field="Engineering",
            ),
            pd.bdate_range(
                start=dt.datetime(2023, 1, 1, 0, 0, 0, tzinfo=dt.timezone.utc),
                end=dt.datetime(2025, 12, 31, 0, 0, 0, tzinfo=dt.timezone.utc),
                freq="W-MON",
                inclusive="left",
            )
            .to_frame(index=False, name="interval")
            .assign(
                weekly_work_capacity=pd.Timedelta(0),
                field="Artificial Intelligent",
            ),
        ]
    )
    .groupby(["field", "interval"], as_index=False)
    .agg({"weekly_work_capacity": "sum", "field": lambda gs: gs.iloc[0]})
)
timeline = (
    px.timeline(
        phases.dropna(subset=["start_date", "due_date"]),
        x_start="start_date",
        x_end="due_date",
        y="id",
        text="name",
        color="project_id",
        labels={"id": "Phase", "project_id": "Project"},
        hover_name="name",
        hover_data={
            "id": False,
            "name": False,
            "Workload": (
                phases.dropna(subset=["start_date", "due_date"]).time_estimate
                / pd.Timedelta(hours=1)
            ).astype("string")
            + " hours",
            "Field": phases.dropna(subset=["start_date", "due_date"])
            .merge(
                projects[["id", "field"]],
                left_on="project_id",
                right_on="id",
                how="left",
            )
            .field,
            "Priority": phases.dropna(subset=["start_date", "due_date"]).priority,
        },
    )
    .update_xaxes(
        tickformat="%V",
        dtick=7 * 24 * 60 * 60 * 1000,
        ticklabelmode="period",
        rangebreaks=[dict(bounds=["sat", "mon"])],
        tickfont_color="white",
    )
    .update_yaxes(showticklabels=False, visible=False)
    .update_traces(textposition="outside")
    .update_layout(legend_traceorder="reversed")
)
timeline.for_each_trace(
    lambda t: t.update(
        name=projects.set_index("id").loc[t.name, "name"][:30],
        legendgroup=projects.set_index("id").loc[t.name, "name"],
        hovertemplate=t.hovertemplate.replace(
            t.name, projects.set_index("id").loc[t.name, "name"]
        )
        .replace("start_date", "Start week")
        .replace("due_date", "Due week"),
    )
)
fig = make_subplots(
    rows=3,
    cols=1,
    figure=timeline,
    row_heights=[0.7, 0.15, 0.15],
    shared_xaxes=True,
    vertical_spacing=0.04,
    subplot_titles=[
        "ISR innovation area roadmap 2024",
        "Artificial intelligent weekly work [h]",
        "Engineering weekly work [h]",
    ],
)
fig.append_trace(
    go.Scatter(
        x=work_load[work_load.field == "Artificial Intelligent"].interval.to_list(),
        y=(
            work_load[work_load.field == "Artificial Intelligent"].time_estimate
            / pd.Timedelta(hours=1)
        ).to_list(),
        mode="lines",
        xperiod=7 * 24 * 60 * 60 * 1000,
        xperiodalignment="middle",
        fill="tozeroy",
        fillcolor="rgba(240, 128, 128, 0.5)",
        line_color="rgba(255, 127, 80, 0.5)",
        name="AI weekly workload [h]",
        hovertemplate="<b>AI weekly workload [h]</b><br><br>Week: %{x}<br>Hours: %{y}<extra></extra>",
    ),
    row=2,
    col=1,
)
fig.append_trace(
    go.Scatter(
        x=work_capacity[
            work_capacity.field == "Artificial Intelligent"
        ].interval.to_list(),
        y=(
            work_capacity[
                work_capacity.field == "Artificial Intelligent"
            ].weekly_work_capacity
            / pd.Timedelta(hours=1)
        ).to_list(),
        mode="lines",
        xperiod=7 * 24 * 60 * 60 * 1000,
        xperiodalignment="middle",
        fill="tozeroy",
        fillcolor="rgba(32, 178, 170, 0.5)",
        line_color="rgba(46, 139, 87, 0.5)",
        name="AI weekly work capacity [h]",
        hovertemplate="<b>AI weekly work capacity [h]</b><br><br>Week: %{x}<br>Hours: %{y}<extra></extra>",
    ),
    row=2,
    col=1,
)
fig.append_trace(
    go.Scatter(
        x=work_load[work_load.field == "Engineering"].interval.to_list(),
        y=(
            work_load[work_load.field == "Engineering"].time_estimate
            / pd.Timedelta(hours=1)
        ).to_list(),
        mode="lines",
        xperiod=7 * 24 * 60 * 60 * 1000,
        xperiodalignment="middle",
        fill="tozeroy",
        fillcolor="rgba(255, 160, 122, 0.5)",
        line_color="rgba(250, 128, 114, 0.5)",
        name="Eng weekly workload [h]",
        hovertemplate="<b>Eng weekly workload [h]</b><br><br>Week: %{x}<br>Hours: %{y}<extra></extra>",
    ),
    row=3,
    col=1,
)
fig.append_trace(
    go.Scatter(
        x=work_capacity[work_capacity.field == "Engineering"].interval.to_list(),
        y=(
            work_capacity[work_capacity.field == "Engineering"].weekly_work_capacity
            / pd.Timedelta(hours=1)
        ).to_list(),
        mode="lines",
        xperiod=7 * 24 * 60 * 60 * 1000,
        xperiodalignment="middle",
        fill="tozeroy",
        fillcolor="rgba(144, 238, 144, 0.5)",
        line_color="rgba(0, 128, 0, 0.5)",
        name="Eng weekly work capacity [h]",
        hovertemplate="<b>Eng weekly work capacity [h]</b><br><br>Week: %{x}<br>Hours: %{y}<extra></extra>",
    ),
    row=3,
    col=1,
)
fig.update_xaxes(
    dtick=7 * 24 * 60 * 60 * 1000,
    ticklabelmode="period",
    rangebreaks=[dict(bounds=["sat", "mon"])],
    showticklabels=True,
    showgrid=True,
    tickangle=0,
    range=[dt.datetime(2024, 1, 1, 0, 0, 0), dt.datetime(2025, 1, 1, 0, 0, 0)],
    showspikes=True,
    spikesnap="cursor",
    spikethickness=1,
    spikemode="across",
)
fig.update_layout(
    xaxis3_tickformat="%V\n%b %Y",
    yaxis2_range=[
        0,
        1.05
        * max(
            (
                work_load[work_load.field == "Artificial Intelligent"].time_estimate
                / pd.Timedelta(hours=1)
            ).max(),
            (
                work_capacity[
                    work_capacity.field == "Artificial Intelligent"
                ].weekly_work_capacity
                / pd.Timedelta(hours=1)
            ).max(),
        ),
    ],
    yaxis2_minor_showgrid=True,
    yaxis3_range=[
        0,
        1.05
        * max(
            (
                work_load[work_load.field == "Engineering"].time_estimate
                / pd.Timedelta(hours=1)
            ).max(),
            (
                work_capacity[work_capacity.field == "Engineering"].weekly_work_capacity
                / pd.Timedelta(hours=1)
            ).max(),
        ),
    ],
    yaxis3_minor_showgrid=True,
    xaxis2_tickformat="%V",
    xaxis2_tickfont_color="white",
    height=1000,
).update_yaxes(
    title_standoff=20,
    showspikes=True,
    spikesnap="cursor",
    spikethickness=1,
    spikemode="across",
)
for timestamp in pd.date_range(
    start=dt.datetime(2024, 1, 1, 0, 0, 0),
    end=dt.datetime(2025, 1, 1, 0, 0, 0),
    freq="MS",
):
    fig.add_vline(x=timestamp, line_width=1, row=1, col=1)
    fig.add_vline(x=timestamp, line_width=1, row=2, col=1)
    fig.add_vline(x=timestamp, line_width=1, row=3, col=1)
st.set_page_config(layout="wide")
st.plotly_chart(fig, use_container_width=True, theme=None)
