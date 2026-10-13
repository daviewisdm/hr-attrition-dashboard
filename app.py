import pandas as pd
import plotly.express as px
import streamlit as st

st.set_page_config(page_title="HR Attrition Dashboard", page_icon="👥", layout="wide")

DATA_FILE = "data/HR Data 2025 (1) (1).xlsx"
AGE_ORDER = ["Under 25", "25 - 34", "35 - 44", "45 - 54", "Over 55"]
COLORS = {"Current Employees": "#2E86AB", "Ex-Employees": "#E4572E"}


# data loading
@st.cache_data
def load_data(path: str) -> pd.DataFrame:
    df = pd.read_excel(path, sheet_name="HR data")
    # drop constant / helper columns that add no information
    df = df.drop(
        columns=["Employee Count", "Standard Hours", "Over18", "-2", "0", "CF_current Employee"],
        errors="ignore",
    )
    df = df.rename(columns={"CF_age band": "Age Band", "CF_attrition label": "Status"})
    df["Left"] = (df["Attrition"] == "Yes").astype(int)
    df["Age Band"] = pd.Categorical(df["Age Band"], categories=AGE_ORDER, ordered=True)
    return df


def attrition_rate(frame: pd.DataFrame, by: str) -> pd.DataFrame:
    out = (
        frame.groupby(by, observed=True)
        .agg(Headcount=("Left", "size"), Leavers=("Left", "sum"))
        .reset_index()
    )
    out["Attrition %"] = (out["Leavers"] / out["Headcount"] * 100).round(1)
    return out


df = load_data(DATA_FILE)

# sidebar slicers
st.sidebar.header("Filters")

dept = st.sidebar.multiselect("Department", sorted(df["Department"].unique()))
gender = st.sidebar.multiselect("Gender", sorted(df["Gender"].unique()))
age_band = st.sidebar.multiselect("Age band", AGE_ORDER)
marital = st.sidebar.multiselect("Marital status", sorted(df["Marital Status"].unique()))
travel = st.sidebar.multiselect("Business travel", sorted(df["Business Travel"].unique()))
overtime = st.sidebar.multiselect("Over time", sorted(df["Over Time"].unique()))

inc_min, inc_max = int(df["Monthly Income"].min()), int(df["Monthly Income"].max())
income = st.sidebar.slider("Monthly income", inc_min, inc_max, (inc_min, inc_max))

ten_min, ten_max = int(df["Years At Company"].min()), int(df["Years At Company"].max())
tenure = st.sidebar.slider("Years at company", ten_min, ten_max, (ten_min, ten_max))

# empty multiselect = no filter (Power BI slicer behaviour)
mask = df["Monthly Income"].between(*income) & df["Years At Company"].between(*tenure)
for col, chosen in [
    ("Department", dept),
    ("Gender", gender),
    ("Age Band", age_band),
    ("Marital Status", marital),
    ("Business Travel", travel),
    ("Over Time", overtime),
]:
    if chosen:
        mask &= df[col].isin(chosen)

df_f = df[mask]

st.title("👥 HR Attrition Dashboard")

if df_f.empty:
    st.warning("No employees match the current filters.")
    st.stop()

# KPI row is filled in after the cross-filter selection is known
kpi_area = st.container()

tab_overview, tab_drivers, tab_explorer = st.tabs(["Overview", "Attrition drivers", "Employee explorer"])

# Overview
with tab_overview:
    left, right = st.columns([3, 2])

    with left:
        st.subheader("Attrition rate by job role")
        st.caption("Click one or more bars to cross-filter every other visual on the page.")
        role_df = attrition_rate(df_f, "Job Role").sort_values("Attrition %")
        fig_role = px.bar(
            role_df,
            x="Attrition %",
            y="Job Role",
            orientation="h",
            text="Attrition %",
            hover_data=["Headcount", "Leavers"],
            color_discrete_sequence=["#2E86AB"],
        )
        fig_role.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0), clickmode="event+select")
        role_event = st.plotly_chart(
            fig_role, on_select="rerun", selection_mode="points", key="role_chart"
        )

    selected_roles = [p["y"] for p in role_event.selection.points] if role_event.selection.points else []
    df_x = df_f[df_f["Job Role"].isin(selected_roles)] if selected_roles else df_f

    with right:
        st.subheader("Headcount by department")
        dept_df = (
            df_x.groupby(["Department", "Status"], observed=True).size().reset_index(name="Employees")
        )
        fig_dept = px.bar(
            dept_df,
            x="Department",
            y="Employees",
            color="Status",
            barmode="stack",
            color_discrete_map=COLORS,
        )
        fig_dept.update_layout(height=420, margin=dict(l=0, r=0, t=10, b=0), legend_title=None)
        st.plotly_chart(fig_dept)

    if selected_roles:
        st.info(f"Cross-filtered to: {', '.join(selected_roles)}. Double-click empty space on the bar chart to clear.")

# Drivers
with tab_drivers:
    c1, c2 = st.columns(2)

    with c1:
        st.subheader("Attrition rate by age band")
        age_df = attrition_rate(df_x, "Age Band")
        fig_age = px.bar(age_df, x="Age Band", y="Attrition %", text="Attrition %",
                         hover_data=["Headcount", "Leavers"], color_discrete_sequence=["#E4572E"])
        fig_age.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_age)

    with c2:
        st.subheader("Attrition rate: over time vs not")
        ot_df = attrition_rate(df_x, ["Over Time", "Department"])
        fig_ot = px.bar(ot_df, x="Department", y="Attrition %", color="Over Time",
                        barmode="group", text="Attrition %",
                        color_discrete_map={"Yes": "#E4572E", "No": "#2E86AB"})
        fig_ot.update_layout(margin=dict(l=0, r=0, t=10, b=0))
        st.plotly_chart(fig_ot)

    c3, c4 = st.columns(2)

    with c3:
        st.subheader("Monthly income distribution")
        fig_inc = px.histogram(df_x, x="Monthly Income", color="Status", nbins=30,
                               barmode="overlay", opacity=0.7, color_discrete_map=COLORS)
        fig_inc.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend_title=None)
        st.plotly_chart(fig_inc)

    with c4:
        st.subheader("Average satisfaction scores")
        sat_cols = [
            "Job Satisfaction",
            "Environment Satisfaction",
            "Relationship Satisfaction",
            "Work Life Balance",
        ]
        sat = df_x.groupby("Status")[sat_cols].mean().round(2).reset_index().melt(
            id_vars="Status", var_name="Measure", value_name="Average score"
        )
        fig_sat = px.bar(sat, x="Measure", y="Average score", color="Status",
                         barmode="group", color_discrete_map=COLORS, text="Average score")
        fig_sat.update_layout(margin=dict(l=0, r=0, t=10, b=0), legend_title=None)
        st.plotly_chart(fig_sat)

# Explorer
with tab_explorer:
    st.subheader("Tenure vs income")
    st.caption("Box-select or lasso a group of points to list those employees below.")
    fig_sc = px.scatter(
        df_x.reset_index(drop=True),
        x="Years At Company",
        y="Monthly Income",
        color="Status",
        color_discrete_map=COLORS,
        hover_data=["emp no", "Job Role", "Department", "Age"],
        opacity=0.7,
    )
    fig_sc.update_layout(height=450, margin=dict(l=0, r=0, t=10, b=0), legend_title=None)
    sc_event = st.plotly_chart(
        fig_sc, on_select="rerun", selection_mode=["box", "lasso", "points"], key="scatter"
    )

    plot_df = df_x.reset_index(drop=True)
    if sc_event.selection.points:
        ids = [p["customdata"][0] for p in sc_event.selection.points]
        table = plot_df[plot_df["emp no"].isin(ids)]
        st.write(f"**{len(table)} employees selected**")
    else:
        table = plot_df
        st.write(f"**Showing all {len(table)} employees in the current view**")

    show_cols = ["emp no", "Job Role", "Department", "Age", "Gender", "Monthly Income",
                 "Years At Company", "Over Time", "Job Satisfaction", "Status"]
    st.dataframe(table[show_cols], hide_index=True)
    st.download_button(
        "Download this view as CSV",
        table[show_cols].to_csv(index=False).encode("utf-8"),
        file_name="hr_selection.csv",
        mime="text/csv",
    )

# KPIs (top of page)
with kpi_area:
    k1, k2, k3, k4, k5 = st.columns(5)
    k1.metric("Headcount", f"{len(df_x):,}")
    k2.metric("Leavers", f"{int(df_x['Left'].sum()):,}")
    k3.metric("Attrition rate", f"{df_x['Left'].mean() * 100:.1f}%",
              delta=f"{(df_x['Left'].mean() - df['Left'].mean()) * 100:+.1f} pts vs company",
              delta_color="inverse")
    k4.metric("Avg monthly income", f"{df_x['Monthly Income'].mean():,.0f}")
    k5.metric("Avg tenure (yrs)", f"{df_x['Years At Company'].mean():.1f}")