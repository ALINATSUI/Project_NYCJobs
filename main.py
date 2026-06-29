import pandas as pd
import resend
import dash
from dash import dcc, html, Input, Output
import plotly.express as px
from dotenv import load_dotenv
import os

load_dotenv()
resend.api_key = os.environ.get("RESEND_API_KEY")

import fetch_jobs
import process_jobs

app = dash.Dash()

# ── Data ──────────────────────────────────────────────────────────────────────

df = pd.read_parquet(
    "jobs-processed.parquet",
    columns=[
        "skills", "borough", "sector", "industry",
        "certifications", "education_level", "salary_max",
        "career_level", "apply_url", "number_of_positions", "title"
    ]
)

# ── Pre-compute job dropdown options ──────────────────────────────────────────

valid_boroughs = {"Manhattan", "Queens", "Brooklyn", "Bronx", "Staten Island"}

filtered_jobs = df[
    df["borough"].isin(valid_boroughs) &
    df["title"].notna() &
    (df["title"].str.strip() != "")
][["title", "borough"]].drop_duplicates()

job_options = sorted(
    [{"label": f"{row.title} — {row.borough}", "value": row.title}
     for _, row in filtered_jobs.iterrows()],
    key=lambda x: x["label"]
)

# ── Pre-computed figures (static) ─────────────────────────────────────────────

skill_counts = (
    df.explode("skills")
    .groupby("skills")
    .size()
    .reset_index(name="count")
    .sort_values("count", ascending=False)
    .head(15)
)
top_skills = skill_counts["skills"].tolist()

salary_by_skill = (
    df.explode("skills")
    .dropna(subset=["salary_max", "skills"])
    .query("skills in @top_skills")
    .groupby("skills")["salary_max"]
    .median()
    .reset_index(name="median_salary")
    .sort_values("median_salary", ascending=False)
)
salary_by_skill["skill_short"] = (
    salary_by_skill["skills"].str.replace(" and ", " & ").str[:20]
)

fig_salary = px.bar(
    salary_by_skill,
    x="skill_short",
    y="median_salary",
    color="skill_short",
    color_discrete_sequence=px.colors.qualitative.Pastel,
    labels={"median_salary": "Typical Top Salary by Skill ($)", "skills": "Skill"},
)
fig_salary.update_layout(
    legend=dict(
        title=dict(text="<b>Skill</b>", font=dict(size=14)),
        bgcolor="#f8f8f8",
        bordercolor="#cccccc",
        borderwidth=1.5,
        x=1.02, xanchor="left",
        y=0.5, yanchor="middle",
    ),
    xaxis=dict(title="Skills", showticklabels=False),
)

# ── Section helper ────────────────────────────────────────────────────────────

ACCENT = "#4f46e5"

def section(children, extra_style=None):
    style = {
        "display": "flex",
        "gap": "20px",
        "alignItems": "stretch",
        "padding": "28px 40px",
        "borderBottom": "0.5px solid #e5e7eb",
    }
    if extra_style:
        style.update(extra_style)
    return html.Div([
        html.Div(style={
            "width": "4px",
            "flexShrink": "0",
            "backgroundColor": ACCENT,
            "borderRadius": "0",
        }),
        html.Div(children, style={"flex": "1", "minWidth": "0"}),
    ], style=style)

# ── Layout ────────────────────────────────────────────────────────────────────

HEADING = {
    "fontFamily": "Inter, Segoe UI, sans-serif",
    "fontWeight": "600",
    "color": "#1a1a2e",
    "margin": "0 0 4px 0",
}

app.layout = html.Div(children=[

    # Header
    html.Div([
        html.H2("NYC Job Skills Dashboard", style={
            **HEADING,
            "fontSize": "1.5rem",
            "letterSpacing": "-0.3px",
        }),
        html.P("Explore job postings, in-demand skills, and salaries across NYC boroughs.",
               style={"fontSize": "0.85rem", "color": "#888", "margin": "4px 0 0 0"}),
    ], style={"padding": "30px 40px 24px 40px", "borderBottom": f"3px solid {ACCENT}"}),

    # Body — two columns
    html.Div([

        # ── Left column: charts ───────────────────────────────────────────────
        html.Div([

            section([
                html.H3("Skills in Demand by Industry", style=HEADING),
                html.Div([
                    dcc.Dropdown(
                        id="borough-dropdown",
                        options=[{"label": b, "value": b} for b in sorted(df["borough"].dropna().unique())],
                        placeholder="Filter by Borough",
                        multi=True,
                        style={"width": "100%"}
                    ),
                    dcc.Dropdown(
                        id="industry-dropdown",
                        options=[{"label": i, "value": i} for i in sorted(df["industry"].dropna().unique())],
                        placeholder="Filter by Industry",
                        multi=True,
                        style={"width": "100%"}
                    ),
                ], style={"display": "flex", "gap": "12px", "margin": "12px 0"}),
                dcc.Graph(id="skills-chart", style={"height": "300px"}),
            ]),

            section([
                html.H3("Typical Top Salary by Skill", style=HEADING),
                html.P("Based on 43% of job postings with salary data",
                       style={"fontSize": "0.8rem", "color": "#888", "margin": "2px 0 0 0"}),
                dcc.Graph(figure=fig_salary),
            ], extra_style={"borderBottom": "none"}),

        ], style={"flex": "3", "minWidth": "0"}),

        # ── Right column: email sidebar ───────────────────────────────────────
        html.Div([
            html.Div([
                html.Div(style={
                    "width": "4px",
                    "backgroundColor": ACCENT,
                    "borderRadius": "0",
                    "marginBottom": "16px",
                    "height": "4px",
                    "width": "100%",
                }),
                html.H3("Get Job Details by Email", style={**HEADING, "fontSize": "1rem"}),
                html.P("Select a borough and job title, then send the listing to your inbox.",
                       style={"fontSize": "0.8rem", "color": "#888", "margin": "4px 0 16px 0"}),
                dcc.Dropdown(
                    id="job-borough-dropdown",
                    options=[{"label": b, "value": b} for b in sorted(valid_boroughs)],
                    placeholder="Filter by borough...",
                    style={"marginBottom": "10px"}
                ),
                dcc.Dropdown(
                    id="job-dropdown",
                    options=job_options,
                    placeholder="Select a job title...",
                    style={"marginBottom": "16px"}
                ),
                dcc.Input(
                    id="user-email",
                    type="email",
                    placeholder="you@example.com",
                    style={
                        "width": "100%", "padding": "8px", "borderRadius": "6px",
                        "border": "1px solid #ddd", "boxSizing": "border-box",
                        "marginBottom": "10px"
                    }
                ),
                html.Button(
                    "Send Me This Job →",
                    id="send-email-btn",
                    n_clicks=0,
                    style={
                        "width": "100%", "backgroundColor": ACCENT, "color": "white",
                        "padding": "10px", "borderRadius": "6px", "border": "none",
                        "cursor": "pointer", "fontWeight": "600"
                    }
                ),
                html.Div(id="email-status", style={"marginTop": "12px", "fontSize": "0.85rem"}),
            ], style={
                "position": "sticky",
                "top": "24px",
                "backgroundColor": "#f8f8ff",
                "border": f"1.5px solid {ACCENT}",
                "borderRadius": "10px",
                "padding": "20px",
            }),
        ], style={"flex": "1", "minWidth": "260px", "padding": "28px 40px 28px 0"}),

    ], style={"display": "flex", "alignItems": "flex-start", "gap": "0"}),

])

# ── Callbacks ─────────────────────────────────────────────────────────────────

@app.callback(
    Output("skills-chart", "figure"),
    Input("borough-dropdown", "value"),
    Input("industry-dropdown", "value")
)
def update_chart(selected_boroughs, selected_industries):
    filtered = df.copy()
    if selected_boroughs:
        filtered = filtered[filtered["borough"].isin(selected_boroughs)]
    if selected_industries:
        filtered = filtered[filtered["industry"].isin(selected_industries)]

    skill_counts = (
        filtered.explode("skills")
        .groupby("skills")
        .size()
        .reset_index(name="count")
        .sort_values("count", ascending=False)
        .head(15)
    )
    return px.bar(skill_counts, x="skills", y="count",
                  labels={"count": "Number of Job Postings", "skills": "Skill"})



@app.callback(
    Output("job-dropdown", "options"),
    Input("job-borough-dropdown", "value")
)
def filter_jobs_by_borough(selected_borough):
    if not selected_borough:
        return job_options
    filtered = filtered_jobs[filtered_jobs["borough"] == selected_borough]
    return sorted(
        [{"label": f"{row.title} — {row.borough}", "value": row.title}
         for _, row in filtered.iterrows()],
        key=lambda x: x["label"]
    )


@app.callback(
    Output("email-status", "children"),
    Input("send-email-btn", "n_clicks"),
    Input("job-dropdown", "value"),
    Input("user-email", "value"),
    prevent_initial_call=True
)
def send_job_email(n_clicks, selected_title, user_email):
    if not n_clicks or not selected_title or not user_email:
        return ""

    match = df[df["title"] == selected_title].dropna(subset=["apply_url"])
    if match.empty:
        return html.P("No application link found.", style={"color": "#888"})

    row = match.iloc[0]

    body = f"""
    <html><body>
    <p>Hi,</p>
    <p>Here's the job you were looking at:</p>
    <h3>{row['title']}</h3>
    <p>Borough: {row['borough']}</p>
    <p>
        <a href="{row['apply_url']}"
           style="background:#4f46e5;color:white;padding:10px 20px;
                  border-radius:6px;text-decoration:none;">
            Apply Now →
        </a>
    </p>
    <p>Good luck!</p>
    </body></html>
    """

    try:
        resend.Emails.send({
            "from": "jobs@cloudwithme.net",
            "to": user_email,
            "subject": f"Job Opportunity: {selected_title}",
            "html": body
        })
        return html.P("✓ Email sent!", style={"color": "green", "fontWeight": "600"})
    except Exception as e:
        return html.P(f"Failed to send: {e}", style={"color": "red"})


# ── Run ───────────────────────────────────────────────────────────────────────
server = app.server

if __name__ == "__main__":
    app.run(debug=True)
