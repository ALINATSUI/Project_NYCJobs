import random
import pandas as pd
import plotly.graph_objects as go

random.seed(10)

# 6 Charts

boroughs = ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island"]
counts = [11802, 8467, 4211, 2478, 571]
total_jobs = 28545

# UPDATED BOROUGH COLORS
colors = {
    "Manhattan": "#0057B8",       # premium blue
    "Brooklyn": "#1B8E3E",        # green
    "Queens": "#F28C00",          # orange
    "Bronx": "#E52521",           # red
    "Staten Island": "#8E44AD",   # purple
}

category_labels = [
    "Health Policy, Research<br>& Analysis",
    "Education & Training",
    "Social Services",
    "Administrative & Clerical",
    "Engineering",
    "Information Technology",
    "Public Safety",
    "Other",
]

category_values = [6310, 5081, 3797, 3511, 2540, 2055, 1741, 3396]

# UPDATED HIGH-CLASS PIE COLORS
category_colors = [
    "#0B3C5D",  # deep navy
    "#00A6A6",  # teal
    "#2E7D32",  # elegant green
    "#E76F51",  # muted coral
    "#6A4C93",  # muted purple
    "#B08968",  # warm brown
    "#C06C84",  # rose
    "#9E9E9E",  # gray
]


# APPROXIMATE DOT DATA

bounds = {
    "Manhattan": {"lat": (40.700, 40.878), "lon": (-74.020, -73.930)},
    "Brooklyn": {"lat": (40.570, 40.730), "lon": (-74.040, -73.850)},
    "Queens": {"lat": (40.585, 40.800), "lon": (-73.960, -73.700)},
    "Bronx": {"lat": (40.815, 40.910), "lon": (-73.930, -73.780)},
    "Staten Island": {"lat": (40.500, 40.650), "lon": (-74.250, -74.050)},
}

dot_rows = []

for borough, count in zip(boroughs, counts):
    dot_count = min(count, 1200)

    lat_min, lat_max = bounds[borough]["lat"]
    lon_min, lon_max = bounds[borough]["lon"]

    for _ in range(dot_count):
        dot_rows.append({
            "borough": borough,
            "lat": random.uniform(lat_min, lat_max),
            "lon": random.uniform(lon_min, lon_max),
        })

dots = pd.DataFrame(dot_rows)

geojson_url = "https://raw.githubusercontent.com/codeforamerica/click_that_hood/master/public/data/nyc-boroughs.geojson"


# COMMON STYLE

TITLE_FONT = dict(size=22, family="Arial Black, Arial", color="black")
BODY_FONT = dict(size=13, family="Arial", color="black")
HEIGHT = 430


# 1. BAR CHART

fig1 = go.Figure()

fig1.add_trace(
    go.Bar(
        x=boroughs,
        y=counts,
        marker_color=[colors[b] for b in boroughs],
        text=[f"{x:,}" for x in counts],
        textposition="outside",
        width=0.55,
        hoverinfo="skip",
    )
)

fig1.update_layout(
    title=dict(
        text="NYC Job Postings by Borough<br><span style='font-size:17px;font-family:Arial;font-weight:400;'>Total Job Postings: 28,545</span>",
        x=0.035,
        y=0.96,
        font=TITLE_FONT,
    ),
    height=HEIGHT,
    margin=dict(l=60, r=25, t=86, b=54),
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=BODY_FONT,
    showlegend=False,
    yaxis=dict(
        title="Number of Jobs",
        range=[0, 14500],
        gridcolor="#e6e6e6",
        zeroline=False,
        tickvals=[0, 2000, 4000, 6000, 8000, 10000, 12000, 14000],
        ticktext=["0", "2K", "4K", "6K", "8K", "10K", "12K", "14K"],
    ),
    xaxis=dict(title="Borough"),
)


# 2. PIE CHART

fig2 = go.Figure()

fig2.add_trace(
    go.Pie(
        labels=category_labels,
        values=category_values,
        marker=dict(colors=category_colors, line=dict(color="white", width=1.2)),
        textinfo="percent",
        textposition="inside",
        textfont=dict(size=14, color="white"),
        hoverinfo="label+percent",
        sort=False,
        direction="clockwise",
        showlegend=True,
        domain=dict(x=[0.02, 0.60], y=[0.05, 0.85]),
    )
)

fig2.update_layout(
    title=dict(
        text="Job Postings by Category (Top 7)<br><span style='font-size:17px;font-family:Arial;font-weight:400;'>Total Job Postings: 28,545</span>",
        x=0.035,
        y=0.96,
        font=TITLE_FONT,
    ),
    height=HEIGHT,
    margin=dict(l=0, r=0, t=82, b=5),
    paper_bgcolor="white",
    plot_bgcolor="white",
    font=BODY_FONT,
    legend=dict(
        x=0.70,
        y=0.50,
        xanchor="left",
        yanchor="middle",
        font=dict(size=11),
        itemsizing="constant",
    ),
)


# 3. CHOROPLETH MAP

fig3 = go.Figure()

fig3.add_trace(
    go.Choroplethmapbox(
        geojson=geojson_url,
        locations=boroughs,
        z=counts,
        featureidkey="properties.name",
        colorscale=[
            [0.00, "#8E44AD"],
            [0.20, "#E52521"],
            [0.45, "#F28C00"],
            [0.72, "#1B8E3E"],
            [1.00, "#0057B8"],
        ],
        marker=dict(opacity=0.72, line=dict(width=1.3, color="white")),
        colorbar=dict(
            title="Job Count",
            thickness=18,
            len=0.52,
            x=0.94,
            y=0.52,
            tickvals=[571, 2478, 4211, 8467, 11802],
            ticktext=["571", "2,478", "4,211", "8,467", "11,802"],
        ),
        hoverinfo="skip",
    )
)

fig3.update_layout(
    title=dict(
        text="NYC Job Postings by Borough (Choropleth Map)",
        x=0.035,
        y=0.97,
        font=TITLE_FONT,
    ),
    height=HEIGHT,
    margin=dict(l=0, r=0, t=52, b=0),
    mapbox=dict(
        style="open-street-map",
        center=dict(lat=40.705, lon=-73.94),
        zoom=8.52,
    ),
    paper_bgcolor="white",
    font=BODY_FONT,
)


# 4. DOT MAP

fig4 = go.Figure()

for borough in boroughs:
    d = dots[dots["borough"] == borough]
    fig4.add_trace(
        go.Scattermapbox(
            lat=d["lat"],
            lon=d["lon"],
            mode="markers",
            name=borough,
            marker=dict(
                size=5,
                color=colors[borough],
                opacity=0.86,
            ),
            hoverinfo="name",
        )
    )

fig4.update_layout(
    title=dict(
        text="NYC Job Postings (Job Locations)",
        x=0.035,
        y=0.97,
        font=TITLE_FONT,
    ),
    height=HEIGHT,
    margin=dict(l=0, r=0, t=52, b=0),
    mapbox=dict(
        style="open-street-map",
        center=dict(lat=40.695, lon=-73.96),
        zoom=8.45,
    ),
    legend=dict(
        title="Borough",
        x=0.02,
        y=0.97,
        bgcolor="rgba(255,255,255,0.96)",
        bordercolor="#dddddd",
        borderwidth=1,
        font=dict(size=11),
    ),
    paper_bgcolor="white",
    font=BODY_FONT,
)

# -----------------------------
# 5. TABLE
# -----------------------------
fig5 = go.Figure()

fig5.add_trace(
    go.Table(
        columnwidth=[1.1, 1.1, 1.1],
        header=dict(
            values=["<b>Borough</b>", "<b>Job Count</b>", "<b>Percentage</b>"],
            fill_color="#003b7a",
            font=dict(color="white", size=16, family="Arial"),
            align="center",
            height=40,
            line_color="#dfe3e8",
        ),
        cells=dict(
            values=[
                ["Manhattan", "Brooklyn", "Queens", "Bronx", "Staten Island", "<b>Total</b>"],
                ["11,802", "8,467", "4,211", "2,478", "571", "<b>28,545</b>"],
                ["41.4%", "29.7%", "14.8%", "8.7%", "2.0%", "<b>100%</b>"],
            ],
            fill_color="white",
            font=dict(color="black", size=15, family="Arial"),
            align="center",
            height=48,
            line_color="#dfe3e8",
        ),
    )
)

fig5.update_layout(
    title=dict(
        text="Job Postings by Borough (Table)",
        x=0.035,
        y=0.97,
        font=TITLE_FONT,
    ),
    height=HEIGHT,
    margin=dict(l=20, r=20, t=60, b=20),
    paper_bgcolor="white",
    plot_bgcolor="white",
)


# 6. ZOOM MAP

fig6 = go.Figure()

for borough in boroughs:
    d = dots[dots["borough"] == borough]
    fig6.add_trace(
        go.Scattermapbox(
            lat=d["lat"],
            lon=d["lon"],
            mode="markers",
            name=borough,
            marker=dict(
                size=5,
                color=colors[borough],
                opacity=0.86,
            ),
            hoverinfo="name",
        )
    )

fig6.update_layout(
    title=dict(
        text="NYC Job Postings (Zoomed In)",
        x=0.035,
        y=0.97,
        font=TITLE_FONT,
    ),
    height=HEIGHT,
    margin=dict(l=0, r=0, t=52, b=0),
    mapbox=dict(
        style="open-street-map",
        center=dict(lat=40.755, lon=-73.86),
        zoom=10.18,
    ),
    legend=dict(
        title="Borough",
        x=0.02,
        y=0.97,
        bgcolor="rgba(255,255,255,0.96)",
        bordercolor="#dddddd",
        borderwidth=1,
        font=dict(size=11),
    ),
    paper_bgcolor="white",
    font=BODY_FONT,
)

# EXPORT DASHBOARD

figures = [fig1, fig2, fig3, fig4, fig5, fig6]

html_parts = [
    fig.to_html(
        full_html=False,
        include_plotlyjs="cdn",
        config={
            "displayModeBar": False,
            "responsive": True,
            "scrollZoom": True,
        },
    )
    for fig in figures
]

dashboard_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<title>NYC Job Postings Dashboard</title>
<style>
html, body {{
    margin: 0;
    padding: 0;
    width: 100%;
    height: 100%;
    background: #f3f5f8;
    font-family: Arial, Helvetica, sans-serif;
    overflow: hidden;
}}

.dashboard-grid {{
    display: grid;
    grid-template-columns: 1fr 1fr 1.2fr;
    grid-template-rows: 1fr 1fr;
    gap: 10px;
    padding: 8px;
    width: 100vw;
    height: 100vh;
    box-sizing: border-box;
}}

.card {{
    background: #ffffff;
    border: 1px solid #d9dde5;
    border-radius: 6px;
    box-shadow: 0 1px 6px rgba(0,0,0,0.14);
    overflow: hidden;
    padding: 4px;
    box-sizing: border-box;
}}

.card .plotly-graph-div {{
    width: 100% !important;
    height: 100% !important;
}}
</style>
</head>

<body>
<div class="dashboard-grid">
    <div class="card">{html_parts[0]}</div>
    <div class="card">{html_parts[1]}</div>
    <div class="card">{html_parts[2]}</div>
    <div class="card">{html_parts[3]}</div>
    <div class="card">{html_parts[4]}</div>
    <div class="card">{html_parts[5]}</div>
</div>
</body>
</html>
"""

with open("dashboard.html", "w", encoding="utf-8") as f:
    f.write(dashboard_html)

print("DONE")
print("open dashboard.html")