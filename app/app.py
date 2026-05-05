import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import requests
import pandas as pd
import json
from dash import callback_context 

API_BASE_URL = "http://127.0.0.1:8000"  
BOROUGH_GEOJSON_FILE = 'data/London Boroughs.geojson'

try:
    with open(BOROUGH_GEOJSON_FILE, 'r') as f:
        borough_geojson = json.load(f)
    print("Successfully loaded Borough GeoJSON.")
except FileNotFoundError:
    print(f"CRITICAL ERROR: '{BOROUGH_GEOJSON_FILE}' not found. Choropleth map will not work.")
    borough_geojson = None
except json.JSONDecodeError:
    print(f"CRITICAL ERROR: Failed to parse '{BOROUGH_GEOJSON_FILE}'.")
    borough_geojson = None

app = dash.Dash(__name__, external_stylesheets=[dbc.themes.LUX])
server = app.server

# Add a Store component to cache the fetched data
def create_filter_card():
    """Create card containing all filters."""
    return dbc.Card(
        dbc.CardBody([
            html.H4("Crime filters", className="card-title"),
            
            # Date Range Filter
            html.P("Pick a month range:", className="card-text"),
            dcc.DatePickerRange(
                id='date-picker-range',
                min_date_allowed='2020-01',
                max_date_allowed='2025-12', 
                start_date='2025-01',
                end_date='2025-03',
                display_format='YYYY-MM',
                start_date_placeholder_text='Start (YYYY-MM)',
                end_date_placeholder_text='End (YYYY-MM)',
                className="mb-3 w-100"
            ),
            
            # Borough Filter
            html.P("Pick borough(s):", className="card-text"),
            dcc.Dropdown(
                id='borough-dropdown',
                placeholder="Any borough",
                className="mb-3",
                multi=True
            ),
            
            # Crime Type Filter
            html.P("Pick crime type(s):", className="card-text"),
            dcc.Dropdown(
                id='crime-type-dropdown',
                placeholder="Any crime type",
                className="mb-3",
                multi=True
            ),
            
            # Update Button
            dbc.Button("Apply Filters", id="apply-filters-button", color="primary", className="w-100"),

            # Placeholders for custom legend
            html.Hr(className="my-4"),
            html.H5("Map key", id="legend-title", className="card-title"),
            html.Div(
                id='legend-container',
                style={
                    'max-height': '200px',
                    'overflow-y': 'auto',
                    'border': '1px solid #ddd',
                    'border-radius': '5px',
                    'padding': '10px'
                }
            )
        ]),
        className="shadow-sm border-0 rounded-3 bg-white"
    )


def create_map_card():
    """Creates the card for the main map."""
    return dbc.Card(
        dbc.CardBody([
            dbc.RadioItems(
                            id="map-type-selector",
                            options=[
                                {"label": "Dot map", "value": "dot"},
                                {"label": "Choropleth Map", "value": "choropleth"},
                                {"label": "Proximity", "value": "proximity"},
                            ],
                            value="dot",
                            inline=True,
                            className="mb-3",
                        ),
            html.Div(
                dbc.RadioItems(
                    id="proximity-target-selector",
                    options=[
                        {"label": "Stations", "value": "station"},
                        {"label": "Parks", "value": "park"},
                    ],
                    value="station",
                    inline=True,
                    className="mb-2",
                ),
                id="proximity-target-wrapper",
                style={"display": "none"}
            ),
            dcc.Loading(
                id="loading-map",
                type="default",
                children=dcc.Graph(
                    id='crime-map',
                    figure={}, 
                    style={'height': '65vh'}
                )
            )
        ]),
        className="shadow-sm border-0 rounded-3 bg-white"
    )

def create_analysis_card():
    """Creates the card for the analysis charts (pie, trend, borough, deprivation)"""
    return dbc.Card(
        dbc.CardBody([
            html.H4("Crime analysis", className="card-title mb-3"),
            dbc.RadioItems(
                id="analysis-view-selector",
                options=[
                    {"label": "Crime split", "value": "pie"},
                    {"label": "Borough comparison", "value": "borough"},
                ],
                value="pie",
                inline=True,
                className="mb-3",
            ),
            dcc.Loading(
                id="loading-analysis",
                type="default",
                children=dcc.Graph(
                    id='analysis-chart',
                    figure={},
                    style={'height': '50vh'}
                )
            )
        ]),
        className="shadow-sm border-0 rounded-3 bg-white"
    )
def create_insights_section():
    cards = [
        {
            "rq": "RQ1",
            "color": "#6f42c1",
            "question": "Does deprivation drive local crime rates?",
            "finding": "Anti-social behaviour and drug offences are most closely linked to IMD rank.",
            "detail": "Using 10,225 non-outlier LSOAs, I found a consistent negative correlation between IMD rank and crime. As deprivation increases (lower rank), crime rates per 1,000 residents go up. Anti-social behaviour (r=-0.44) and drugs (r=-0.44) showed the strongest links, suggesting deprivation is a major background driver for these specific categories in London.",
            "chart_id": "insight-chart-rq1",
            "modal_id": "modal-rq1",
            "btn_id": "btn-rq1",
        },
        {
            "rq": "RQ2",
            "color": "#d73027",
            "question": "How do TfL stations affect spatial crime patterns?",
            "finding": "Crime is 22% higher near stations, driven by opportunistic theft.",
            "detail": "My analysis of 4,441 London LSOAs shows crime rates are 106.94 per 1,000 residents within 500m of a station, compared to 87.69 elsewhere. This 22% elevation is dominated by 'crimes of opportunity': theft from the person (+141%) and bike theft (+78%). This supports Routine Activity Theory, as transport hubs aggregate commuters in busy, unmonitored spaces.",
            "chart_id": "insight-chart-rq2",
            "modal_id": "modal-rq2",
            "btn_id": "btn-rq2",
        },
        {
            "rq": "RQ3",
            "color": "#e6841a",
            "question": "Is there a clear seasonal cycle for crime?",
            "finding": "Summer peaks for bike theft; winter peaks for burglary.",
            "detail": "Looking at the full three-year dataset, distinct seasonal trends emerged. Bike theft spikes in summer (67.3% higher than winter), likely due to increased outdoor activity. Burglary is the opposite, peaking in winter, probably due to longer nights and homes being left empty over the Christmas period.",
            "chart_id": "insight-chart-rq3",
            "modal_id": "modal-rq3",
            "btn_id": "btn-rq3",
        },
        {
            "rq": "RQ4",
            "color": "#2b8a3e",
            "question": "Do parks act as 'crime attractors'?",
            "finding": "Proximity to parks correlates with an 11% increase in crime.",
            "detail": "After correcting for non-London LSOA contamination, the data shows an 11% crime elevation within 500m of a park. Similar to stations, the effect is strongest for pedestrian-oriented crimes like bike theft (+70%) and theft from the person (+58%). Parks function as 'spatial convergence nodes' where high volumes of targets gather with minimal formal guardianship.",
            "chart_id": "insight-chart-rq4",
            "modal_id": "modal-rq4",
            "btn_id": "btn-rq4",
        },
    ]
    card_cols = []
    modals = []

    for c in cards:
        # Summary card
        card_cols.append(
            dbc.Col(
                dbc.Card([
                    dbc.CardBody([
                        html.Div([
                            dbc.Badge(c['rq'], pill=True, style={
                                "background": "rgba(0,0,0,0.06)",
                                "color": c['color'],
                                "fontSize": "11px",
                                "fontWeight": "700",
                                "letterSpacing": "0.08em",
                                "padding": "0.35rem 0.75rem",
                                "borderRadius": "999px",
                                "marginBottom": "14px"
                            }),
                            html.H5(c['question'], style={
                                "fontSize": "20px",
                                "fontWeight": "800",
                                "marginBottom": "10px",
                                "lineHeight": "1.2",
                                "color": c['color'],
                                "letterSpacing": "0.01em"
                            }),
                            html.P(c['finding'], style={
                                "fontSize": "15px",
                                "fontWeight": "600",
                                "marginBottom": "16px",
                                "color": "#111827",
                                "lineHeight": "1.55"
                            }),
                            html.P("Tap for the full breakdown.", className="text-muted", style={
                                "fontSize": "13px",
                                "marginBottom": "0",
                                "lineHeight": "1.4"
                            })
                        ]),
                        html.Div(
                            dbc.Button(
                                "Open details",
                                id=c['btn_id'],
                                color="link",
                                size="sm",
                                className="p-0 text-decoration-none",
                                style={"color": c['color'], "fontSize": "14px", "fontWeight": "700"}
                            ),
                            className="mt-auto pt-3 border-top"
                        )
                    ], className="d-flex flex-column justify-content-between h-100 p-4")
                ], className="shadow-sm border border-1 border-light rounded-5 bg-white h-100"),
                md=3
            )
        )

        # Modal for RQ
        modals.append(
            dbc.Modal([
                dbc.ModalHeader(
                    dbc.ModalTitle([
                        dbc.Badge(c['rq'], pill=True, style={
                            "background": c['color'], "fontSize": "13px", "marginRight": "10px"
                        }),
                        html.Span(c['question'], style={"fontSize": "18px", "fontWeight": "700"})
                    ])
                ),
                dbc.ModalBody([
                    html.P(c['finding'], style={
                        "fontSize": "18px", "fontWeight": "700",
                        "color": c['color'], "marginBottom": "14px"
                    }),
                    html.P(c['detail'], style={
                        "fontSize": "15px",
                        "lineHeight": "1.8",
                        "color": "#444",
                        "marginBottom": "24px"
                    }),
                    dcc.Loading(
                        type="default",
                        children=dcc.Graph(
                            id=c['chart_id'],
                            figure={},
                            style={'height': '720px'},
                            config={'displayModeBar': False}
                        )
                    )                ]),
                dbc.ModalFooter(
                    dbc.Button("Close", id=f"close-{c['modal_id']}", color="secondary", size="sm")
                )
            ],
            id=c['modal_id'],
            size="xl",
            is_open=False,
            )
        )

    return html.Div([
        html.Hr(className="my-3"),
        html.H5("Research insights", className="mb-3 fw-semibold"),
        dbc.Row(card_cols, className="g-4"),
        *modals
    ], className="mt-2")

navbar = dbc.NavbarSimple(
    brand="London Street Crime Explorer",
    color="dark",
    dark=True,
    className="mb-3 shadow-sm rounded-3"
)

app.layout = dbc.Container([
    navbar,
    dcc.Store(id='cached-crime-data'),  # cache raw crime data
    dcc.Store(id='cached-borough-data'),  # cache borough summary
    dbc.Row([
        dbc.Col(create_filter_card(), md=3, lg=3, xl=3, className="mb-3"),
        dbc.Col(
            dbc.Tabs(
                [
                    dbc.Tab(create_map_card(), label="Map", tab_id="tab-map"),
                    dbc.Tab(create_analysis_card(), label="Analysis", tab_id="tab-analysis"),
                ],
                id="main-tabs",
                active_tab="tab-map",
                className="flex-column flex-sm-row"
            ),
            md=9, lg=9, xl=9, className="mb-3"
        ),
    ], className="g-3"),
    create_insights_section()
], fluid=True, className="bg-light p-4")

@app.callback(
    Output('borough-dropdown', 'options'),
    Input('borough-dropdown', 'id') # Trigger on page load
)
def populate_boroughs(_):
    """Fetches the list of boroughs from the API to populate the dropdown"""
    try:
        response = requests.get(f"{API_BASE_URL}/boroughs")
        response.raise_for_status() 
        data = response.json()
        return [{"label": b, "value": b} for b in data.get('boroughs', [])]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching boroughs: {e}")
        return []

@app.callback(
    Output('crime-type-dropdown', 'options'),
    Input('crime-type-dropdown', 'id') # Trigger on page load
)
def populate_crime_types(_):
    """Fetches the list of crime types from the API to populate the dropdown"""
    try:
        response = requests.get(f"{API_BASE_URL}/crime_types")
        response.raise_for_status()
        data = response.json()
        return [{"label": c, "value": c} for c in data.get('crime_types', [])]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching crime types: {e}")
        return []

@app.callback(
    Output("modal-rq1", "is_open"),
    [Input("btn-rq1", "n_clicks"), Input("close-modal-rq1", "n_clicks")],
    State("modal-rq1", "is_open"),
    prevent_initial_call=True
)
def toggle_modal_rq1(open_click, close_click, is_open): return not is_open

@app.callback(
    Output("modal-rq2", "is_open"),
    [Input("btn-rq2", "n_clicks"), Input("close-modal-rq2", "n_clicks")],
    State("modal-rq2", "is_open"),
    prevent_initial_call=True
)
def toggle_modal_rq2(open_click, close_click, is_open): return not is_open

@app.callback(
    Output("modal-rq3", "is_open"),
    [Input("btn-rq3", "n_clicks"), Input("close-modal-rq3", "n_clicks")],
    State("modal-rq3", "is_open"),
    prevent_initial_call=True
)
def toggle_modal_rq3(open_click, close_click, is_open): return not is_open

@app.callback(
    Output("modal-rq4", "is_open"),
    [Input("btn-rq4", "n_clicks"), Input("close-modal-rq4", "n_clicks")],
    State("modal-rq4", "is_open"),
    prevent_initial_call=True
)
def toggle_modal_rq4(open_click, close_click, is_open): return not is_open

@app.callback(
    Output("proximity-target-wrapper", "style"),
    Input("map-type-selector", "value"),
)
def toggle_proximity_target(map_type):
    if map_type == "proximity":
        return {"display": "block"}
    return {"display": "none"}

@app.callback(
    [Output("insight-chart-rq1", "figure"),
     Output("insight-chart-rq2", "figure"),
     Output("insight-chart-rq3", "figure"),
     Output("insight-chart-rq4", "figure")],
    [Input("modal-rq1", "is_open"),
     Input("modal-rq2", "is_open"),
     Input("modal-rq3", "is_open"),
     Input("modal-rq4", "is_open")]
)
def load_insight_charts(rq1_open, rq2_open, rq3_open, rq4_open):
    empty = go.Figure()
    empty.update_layout(paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                        margin=dict(l=10,r=10,t=10,b=10))

    # RQ1 — Correlation heatmap per crime type
    fig1 = empty
    if rq1_open:
        try:
            data = requests.get(f"{API_BASE_URL}/imd_scatter").json()
            if data:
                df = pd.DataFrame(data).dropna(subset=['imd_rank', 'annual_rate_per_1000'])
                p99 = df['annual_rate_per_1000'].quantile(0.99)
                df = df[df['annual_rate_per_1000'] <= p99]
                sample = df.sort_values('imd_rank').iloc[::max(1, len(df)//2000)]


                fig1 = px.scatter(
                    sample,
                    x = 'imd_rank',
                    y = 'annual_rate_per_1000',
                    trendline='ols',
                    opacity=0.6,
                    color_discrete_sequence=['#6f42c1'],
                    trendline_color_override='#d73027',
                    title='RQ1: IMD rank vs annual crime rate per 1,000 residents',
                    labels={
                        'imd_rank': 'IMD Rank (1=most deprived)',
                        'annual_rate_per_1000': 'Annual crime rate per 1,000 residents'
                    }
                )
                fig1.update_layout(margin=dict(l=10,r=10,t=40,b=10))
        except Exception as e:
            print(f"RQ1 scatter chart error: {e}")

    # RQ2 — distance decay line chart
    fig2 = empty
    if rq2_open:
        try:
            data = requests.get(f"{API_BASE_URL}/station_analysis").json()
            df = pd.DataFrame(data['decay'])
            band_order = ['0-250m','250-500m','500-750m','750-1000m','1000-1500m','1500-2000m','+2km']
            df['band'] = pd.Categorical(df['band'], categories=band_order, ordered=True)
            df = df.sort_values('band')
            fig2 = px.line(df, x='band', y='avg_rate', markers=True,
                           title='Crime rate drop-off with distance from station',
                           labels={'band':'Distance','avg_rate':'Rate per 1,000'})
            fig2.update_traces(line=dict(color='#d73027', width=2), marker=dict(size=6, color='#d73027'))
            fig2.update_layout(margin=dict(l=10,r=10,t=40,b=10))
        except Exception as e:
            print(f"RQ2 insight chart error: {e}")


# RQ3: one mini-chart per crime type, coloured by peak season
    fig3 = empty
    if rq3_open:
        try:
            data = requests.get(f"{API_BASE_URL}/seasonal").json()
            df = pd.DataFrame(data)
            season_order = ['Spring','Summer','Autumn','Winter']
            df['season'] = pd.Categorical(df['season'], categories=season_order, ordered=True)
            df = df.sort_values(['crime_type', 'season'])

            # Order by total volume (biggest first)
            volume_order = (df.groupby('crime_type')['avg_monthly_count']
                              .sum().sort_values(ascending=False).index.tolist())

            # Per crime type peak season + % change min to max
            stats = df.groupby('crime_type')['avg_monthly_count'].agg(['min', 'max', 'idxmax'])
            stats['peak_season'] = df.loc[stats['idxmax']].set_index('crime_type')['season']
            stats['pct_change'] = ((stats['max'] - stats['min']) / stats['min'] * 100).round(0).astype(int)

            peak_season = stats['peak_season'].to_dict()
            pct_change  = stats['pct_change'].to_dict()

            # Map each crime to a label including the % change for the title
            facet_label = {ct: f"{ct} (+{pct_change[ct]}%)" for ct in volume_order}

            season_colors = {
                'Spring': '#76b852',
                'Summer': '#f39c12',
                'Autumn': '#c0392b',
                'Winter': '#2980b9',
            }

            fig3 = px.line(
                df,
                x='season',
                y='avg_monthly_count',
                color='crime_type',
                facet_col='crime_type',
                facet_col_wrap=4,
                facet_col_spacing=0.04,
                facet_row_spacing=0.12,
                category_orders={
                    'crime_type': volume_order,
                    'season': season_order,
                },
                markers=True,
                title='Seasonal pattern by crime type — coloured by peak season',
                labels={'season': '', 'avg_monthly_count': ''},
            )

            # Recolour each line by its peak season; hide legend per crime
            for trace in fig3.data:
                pk = peak_season.get(trace.name)
                colour = season_colors.get(pk, '#555')
                trace.update(
                    line=dict(color=colour, width=2.2),
                    marker=dict(size=6, color=colour),
                    showlegend=False,
                )

            # Replace facet titles with "<crime> (+X%)"
            fig3.for_each_annotation(lambda a: a.update(
                text=facet_label.get(a.text.split('=')[-1], a.text.split('=')[-1]),
                font=dict(size=11),
            ))

            # Show x-axis tick labels on all facets 
            fig3.update_xaxes(showticklabels=True, tickangle=-30, tickfont=dict(size=9))
            fig3.update_yaxes(matches=None, showticklabels=True, tickfont=dict(size=9))

            for season, colour in season_colors.items():
                fig3.add_trace(go.Scatter(
                    x=[None], y=[None],
                    mode='markers',
                    marker=dict(size=11, color=colour),
                    name=season,                  
                    showlegend=True,
                    hoverinfo='skip',
                ))

            fig3.update_layout(
                margin=dict(l=10, r=160, t=50, b=20),
                height=760,
                legend=dict(
                    orientation='v',
                    yanchor='top', y=1.0,
                    xanchor='left', x=1.02,
                    title=dict(text='<b>Peak season</b>', font=dict(size=11)),
                    font=dict(size=10),
                    bgcolor='rgba(255,255,255,0.85)',
                    bordercolor='#ddd',
                    borderwidth=1,
                ),
            )
        except Exception as e:
            print(f"RQ3 insight chart error: {e}")
# RQ4 — three-panel: distance decay (top-left), density bands (top-right), per-crime-type near vs far (bottom, full width)
    fig4 = empty
    if rq4_open:
        try:
            data = requests.get(f"{API_BASE_URL}/park_analysis").json()

            fig4 = make_subplots(
                rows=2, cols=2,
                specs=[
                    [{"type": "xy"}, {"type": "xy"}],
                    [{"colspan": 2}, None],
                ],
                subplot_titles=(
                    "Crime rate falls with distance from nearest park",
                    "Crime rate rises with park density",
                    "Per crime type: near (≤500m) vs far (>500m) from a park"
                ),
                vertical_spacing=0.28,
                horizontal_spacing=0.12,
                row_heights=[0.4, 0.6]
            )

            # Panel 1 — distance decay line
            df_decay = pd.DataFrame(data['decay'])
            band_order = ['0-250m','250-500m','500-750m','750-1000m','1000-1500m','+1500m']
            df_decay['band'] = pd.Categorical(df_decay['band'], categories=band_order, ordered=True)
            df_decay = df_decay.sort_values('band')
            fig4.add_trace(
                go.Scatter(
                    x=df_decay['band'], y=df_decay['avg_rate'],
                    mode='lines+markers',
                    line=dict(color='#2b8a3e', width=2.5),
                    marker=dict(size=8, color='#2b8a3e'),
                    showlegend=False,
                    hovertemplate='%{x}<br>%{y:.1f}/1k<extra></extra>'
                ),
                row=1, col=1
            )

            # Panel 2 — density bands bar
            df_dens = pd.DataFrame(data['density_bands'])
            band_order_dens = ['0','1-3','4-7','8+']
            df_dens['band'] = pd.Categorical(df_dens['band'], categories=band_order_dens, ordered=True)
            df_dens = df_dens.sort_values('band')
            fig4.add_trace(
                go.Bar(
                    x=df_dens['band'], y=df_dens['avg_rate'],
                    marker_color='#2b8a3e',
                    showlegend=False,
                    text=df_dens['avg_rate'].round(1),
                    textposition='outside',
                    hovertemplate='%{x} parks<br>%{y:.1f}/1k<extra></extra>'
                ),
                row=1, col=2
            )

            # Panel 3 — per-crime-type grouped bar
            df_ct = pd.DataFrame(data['by_crime_type'])
            df_ct['proximity'] = df_ct['near_park'].map({1: 'Near (≤500m)', 0: 'Far (>500m)'})
            pivot = df_ct.pivot(index='crime_type', columns='proximity', values='avg_rate').fillna(0)
            pivot['diff'] = pivot.get('Near (≤500m)', 0) - pivot.get('Far (>500m)', 0)
            sorted_types = pivot.sort_values('diff', ascending=False).index.tolist()

            for prox, color in [('Near (≤500m)', '#2b8a3e'), ('Far (>500m)', '#9aa0a6')]:
                sub = df_ct[df_ct['proximity'] == prox]
                sub = sub.set_index('crime_type').reindex(sorted_types).reset_index()
                fig4.add_trace(
                    go.Bar(
                        x=sub['crime_type'], y=sub['avg_rate'],
                        name=prox,
                        marker_color=color,
                        hovertemplate='%{x}<br>'+prox+': %{y:.2f}/1k<extra></extra>'
                    ),
                    row=2, col=1
                )

            fig4.update_xaxes(title_text="Distance from nearest park", row=1, col=1)
            fig4.update_yaxes(title_text="Rate per 1,000", row=1, col=1)
            fig4.update_xaxes(title_text="Parks within 1km", row=1, col=2)
            fig4.update_yaxes(title_text="Rate per 1,000", row=1, col=2)
            fig4.update_xaxes(tickangle=-40, row=2, col=1)
            fig4.update_yaxes(title_text="Avg annual rate per 1,000 residents", row=2, col=1)

            fig4.update_layout(
                barmode='group',
                margin=dict(l=10, r=10, t=60, b=10),
                legend=dict(orientation='h', yanchor='bottom', y=-0.22, xanchor='center', x=0.5),
                height=850
            )
        except Exception as e:
            print(f"RQ4 insight chart error: {e}")

    return fig1, fig2, fig3, fig4
@app.callback(
    [Output('crime-map', 'figure'),
     Output('legend-title', 'children'),
     Output('legend-container', 'children'),
     Output('cached-crime-data', 'data'),
     Output('cached-borough-data', 'data')],
    [Input('apply-filters-button', 'n_clicks'),
     Input('map-type-selector', 'value'),
     Input('proximity-target-selector', 'value')],
    [State('date-picker-range', 'start_date'),
     State('date-picker-range', 'end_date'),
     State('borough-dropdown', 'value'),
     State('crime-type-dropdown', 'value'),
     State('cached-crime-data', 'data'),
     State('cached-borough-data', 'data')],
    prevent_initial_call=True
)

def update_map_and_cache(n_clicks, map_type, proximity_target, start_date, end_date, boroughs, crime_types, cached_crime_data, cached_borough_data):
    """Fetch data on filter click or use cache on view switch"""
    
    empty_map_fig = go.Figure(go.Scattermapbox())
    empty_map_fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_center={"lat": 51.5074, "lon": -0.1278},
        mapbox_zoom=9,
        title="Choose filters to load the map",
        margin={"r":0,"t":40,"l":0,"b":0}
    )
    
    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None

    if triggered_id == 'apply-filters-button':
        if not start_date or not end_date:
            return (empty_map_fig, "Map key", [], None, None)
        
        params = {'start_date': start_date, 'end_date': end_date}
        if boroughs:
            params['borough'] = boroughs
        if crime_types:
            params['crime_type'] = crime_types
        
        # Fetch crime data for dot map
        crime_data = None
        try:
            params_crime = params.copy()
            params_crime['limit'] = 20000
            response = requests.get(f"{API_BASE_URL}/crimes", params=params_crime)
            response.raise_for_status()
            crime_data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching crimes: {e}")
        
        # Fetch borough summary for choropleth
        borough_data = None
        try:
            response = requests.get(f"{API_BASE_URL}/summary_by_borough", params=params)
            response.raise_for_status()
            borough_data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching borough summary: {e}")
    else:
        crime_data = cached_crime_data
        borough_data = cached_borough_data
    
    if map_type == 'choropleth':
        if borough_geojson is None:
            empty_map_fig.update_layout(title="Borough boundaries not loaded.")
            return (empty_map_fig, "Map key", [], cached_crime_data, cached_borough_data)
        
        if not borough_data:
            empty_map_fig.update_layout(title="No data yet — click Update")
            return (empty_map_fig, "Map key", [], cached_crime_data, cached_borough_data)
        
        df = pd.DataFrame(borough_data)
        
        fig_map = px.choropleth_mapbox(
            df,
            geojson=borough_geojson,
            locations='borough',
            featureidkey='properties.BOROUGH',
            color='count',
            color_continuous_scale=[[0, "green"], [0.5, "yellow"], [1, "red"]],
            range_color=[df['count'].min(), df['count'].quantile(0.95)],
            mapbox_style="carto-positron",
            zoom=8.5,
            center={"lat": 51.5074, "lon": -0.1278},
            opacity=0.7,
            title='Crime count by borough'
        )
        fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
        legend_title = "Choropleth Map key"
        legend_content = html.P("Green = lower crime, red = higher crime", className="text-muted small")

    elif map_type == 'proximity':
        # Fetch per-LSOA proximity data 
        try:
            response = requests.get(f"{API_BASE_URL}/proximity_dots")
            response.raise_for_status()
            prox_data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching proximity dots: {e}")
            empty_map_fig.update_layout(title="Couldn't load proximity data")
            return (empty_map_fig, "Map key", [], crime_data, borough_data)

        df_p = pd.DataFrame(prox_data)
        df_p = df_p[df_p['lat'].notna() & df_p['lon'].notna() & df_p['annual_crime_rate_per_1000'].notna()].copy()

        target = proximity_target or "station"
        target_label = "TfL station" if target == "station" else "park"
        dist_col = "distance_to_station_m" if target == "station" else "distance_to_park_m"

        rate_p95 = float(df_p['annual_crime_rate_per_1000'].quantile(0.95))

        # Create hover text
        df_p['hover'] = df_p.apply(
            lambda r: (
                f"<b>LSOA {r['lsoa_code']}</b><br>"
                f"Crime rate: <b>{r['annual_crime_rate_per_1000']:.1f}/1k</b><br>"
                f"Distance to nearest {target_label}: "
                f"<b>{int(r[dist_col])}m</b>" if pd.notna(r[dist_col]) else "out of range"
            ),
            axis=1
        )

        fig_map = go.Figure()

        # Layer 1: LSOA crime rate dots
        fig_map.add_trace(go.Scattermapbox(
            lat=df_p['lat'],
            lon=df_p['lon'],
            mode='markers',
            marker=dict(
                size=(df_p['annual_crime_rate_per_1000'] / rate_p95 * 14 + 4).clip(upper=20),
                color=df_p['annual_crime_rate_per_1000'],
                colorscale=[
                    [0.0,  '#abd9e9'],
                    [0.25, '#fee090'],
                    [0.5,  '#fdae61'],
                    [0.75, '#f46d43'],
                    [1.0,  '#a50026'],
                ],
                cmin=0,
                cmax=rate_p95,
                colorbar=dict(
                    title=dict(text='Crime rate<br>per 1,000', font=dict(size=11)),
                    thickness=12,
                    len=0.5,
                    x=1.0,
                ),
                opacity=0.78,
            ),
            text=df_p['hover'],
            hoverinfo='text',
            showlegend=False,
        ))

        # Layer 2: stations or parks overlay
        try:
            if target == "station":
                overlay_resp = requests.get(f"{API_BASE_URL}/station_map_data")
                overlay_resp.raise_for_status()
                overlay_df = pd.DataFrame(overlay_resp.json())
                overlay_marker = dict(size=11, color='#1a4d8f', opacity=0.5)
                overlay_name = 'TfL stations'
            else:
                overlay_resp = requests.get(f"{API_BASE_URL}/parks")
                overlay_resp.raise_for_status()
                overlay_df = pd.DataFrame(overlay_resp.json())
                overlay_marker = dict(size=11, color='#1d6e1d', opacity=0.2)
                overlay_name = 'London parks'

            if not overlay_df.empty:
                fig_map.add_trace(go.Scattermapbox(
                    lat=overlay_df['lat'],
                    lon=overlay_df['lon'],
                    mode='markers',
                    marker=overlay_marker,
                    text=overlay_df.get('name', overlay_name),
                    hoverinfo='text',
                    name=overlay_name,
                    showlegend=False,
                ))
        except requests.exceptions.RequestException as e:
            print(f"Couldn't fetch overlay {target}: {e}")

        fig_map.update_layout(
            mapbox_style='carto-positron',
            mapbox_center={'lat': 51.5074, 'lon': -0.1278},
            mapbox_zoom=9.3,
            margin={'r': 0, 't': 40, 'l': 0, 'b': 0},
            title=f'Crime rate by LSOA · {target_label}s overlaid',
        )

        legend_title = f"{target_label.capitalize()} proximity"
        legend_content = html.Div([
            html.P("Each dot is a London LSOA.", className="small text-muted mb-1"),
            html.P("Larger and redder dots = higher crime rate per 1,000 residents.", className="small text-muted mb-1"),
            html.P(
                "Dark blue squares are TfL stations." if target == "station"
                else "Small green dots are London parks (3,893 of them).",
                className="small text-muted mb-1"
            ),
            html.P(f"Hover any dot for distance to nearest {target_label}.",
                   className="small text-muted mb-0"),
        ])
        return (fig_map, legend_title, legend_content, crime_data, borough_data)
    else:  # dot map
        if not crime_data:
            empty_map_fig.update_layout(title="No data yet — click Update")
            return (empty_map_fig, "Map key", [], cached_crime_data, cached_borough_data)
        
        df = pd.DataFrame(crime_data)
        unique_crime_types = sorted(df['crime_type'].unique())
        color_scale = px.colors.qualitative.Plotly
        
        legend_items = []
        for i, crime_type in enumerate(unique_crime_types):
            color = color_scale[i % len(color_scale)]
            legend_item = dbc.Row([
                dbc.Col(html.Div(style={'width': '15px', 'height': '15px', 'backgroundColor': color, 'border-radius': '3px'}), width="auto", className="pe-0"),
                dbc.Col(html.Span(crime_type, style={'font-size': '0.9rem'}), width="auto")
            ], className="mb-1 align-items-center")
            legend_items.append(legend_item)
        
        legend_title = f"Map key ({len(unique_crime_types)} types)"
        legend_content = legend_items
        
        fig_map = px.scatter_mapbox(
            df,
            lat="latitude",
            lon="longitude",
            color="crime_type",
            color_discrete_sequence=color_scale,
            category_orders={"crime_type": unique_crime_types},
            hover_data=["month", "crime_type"],
            mapbox_style="carto-positron",
            zoom=9.5,
            center={"lat": df['latitude'].mean(), "lon": df['longitude'].mean()},
            title=f"Showing {len(df)} crime incidents"
        )
        fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0}, showlegend=False)
    
    return (fig_map, legend_title, legend_content, crime_data, borough_data)

@app.callback(
    Output('analysis-chart', 'figure'),
    [Input('analysis-view-selector', 'value'),
     Input('cached-crime-data', 'data')]
)
def update_analysis_chart(view, cached_crime_data):
    """Update the analysis chart based on selected view and cached data"""

    empty_fig = go.Figure()
    empty_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[{
            "text": "Apply filters to see the charts",
            "xref": "paper", "yref": "paper",
            "x": 0.5, "y": 0.5,
            "showarrow": False, "font": {"size": 16}
        }]
    )

    # Deprivation view: show mean annual crime rate per 1000 in three IMD bands
    if view == 'deprivation':
        try:
            response = requests.get(f"{API_BASE_URL}/imd_scatter")
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching /imd_scatter data: {e}")
            return empty_fig

        if not data:
            empty_fig.layout.annotations[0]['text'] = "No IMD/crime data available"
            return empty_fig

        df_dec = pd.DataFrame(data)
        df_dec = df_dec.dropna(subset=['imd_decile', 'annual_rate_per_1000'])
        if df_dec.empty:
            empty_fig.layout.annotations[0]['text'] = "No IMD/crime data available"
            return empty_fig

        def band_for_decile(d):
            try:
                d_int = int(d)
            except (TypeError, ValueError):
                return None
            if 1 <= d_int <= 3:
                return "1-3 (More deprived)"
            if 4 <= d_int <= 7:
                return "4-7 (Middle)"
            if 8 <= d_int <= 10:
                return "8-10 (Less deprived)"
            return None

        df_dec['imd_band'] = df_dec['imd_decile'].apply(band_for_decile)
        df_band = df_dec.dropna(subset=['imd_band'])
        if df_band.empty:
            empty_fig.layout.annotations[0]['text'] = "No IMD/crime data available"
            return empty_fig

        band_summary = (
            df_band
            .groupby('imd_band', as_index=False)['annual_rate_per_1000']
            .mean()
            .rename(columns={'annual_rate_per_1000': 'avg_rate'})
        )

        band_order = ["1-3 (More deprived)", "4-7 (Middle)", "8-10 (Less deprived)"]
        band_summary['imd_band'] = pd.Categorical(band_summary['imd_band'], categories=band_order, ordered=True)
        band_summary = band_summary.sort_values('imd_band')

        fig = px.bar(
            band_summary,
            x='imd_band',
            y='avg_rate',
            labels={
                'imd_band': 'IMD Bands',
                'avg_rate': 'Mean annual crime rate per 1,000 residents'
            },
            title='Crime rate by IMD band'
        )
        fig.update_layout(margin={"r":20,"t":40,"l":20,"b":20})
        return fig
    

    
    if view == 'seasonal':
        try:
            response = requests.get(f"{API_BASE_URL}/seasonal")
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching /seasonal data: {e}")
            return empty_fig
        
        if not data:
            empty_fig.layout.annotations[0]['text'] = "No seasonal data available"
            return empty_fig
        
        df_sea = pd.DataFrame(data)

        season_order = ['Spring', 'Summer', 'Autumn', 'Winter']
        df_sea['season'] = pd.Categorical(df_sea['season'], categories=season_order, ordered=True)
        df_sea = df_sea.sort_values('season')

        fig = px.line(
            df_sea,
            x='season',
            y='avg_monthly_count',
            markers=True,
            title='Seasonal crime trends',
            color='crime_type',
            labels={'season': 'Season', 'avg_monthly_count': 'Average monthly crime count', 'crime_type': 'Crime Type'}
        )
        fig.update_layout(margin={"r":20,"t":40,"l":20,"b":20})
        return fig


    # IMD Correlation view: Display as table
    if view == 'correlation':
        try:
            response = requests.get(f"{API_BASE_URL}/correlation_results")
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching /correlation_results: {e}")
            empty_fig.layout.annotations[0]['text'] = f"Error: {str(e)}"
            return empty_fig

        if not data:
            empty_fig.layout.annotations[0]['text'] = "No correlation data available"
            return empty_fig

        df_corr = pd.DataFrame(data)
        df_corr = df_corr.sort_values('pearson_r', ascending=False)

        # Create a table figure using Plotly
        fig = go.Figure(data=[go.Table(
            header=dict(
                values=['<b>Crime Type</b>', '<b>Pearson r</b>', '<b>P-Value</b>', '<b>Strength</b>', '<b>N LSOAs</b>'],
                fill_color='#2c3e50',
                align='left',
                font=dict(color='white', size=12)
            ),
            cells=dict(
                values=[
                    df_corr['crime_type'],
                    df_corr['pearson_r'].round(4),
                    df_corr['p_value'].apply(lambda x: f"{x:.2e}"),
                    df_corr['strength'],
                    df_corr['n_lsoas']
                ],
                fill_color=[
                    'rgba(240, 240, 240, 0.5)',
                    'rgba(220, 220, 220, 0.5)',
                    'rgba(240, 240, 240, 0.5)',
                    'rgba(220, 220, 220, 0.5)',
                    'rgba(240, 240, 240, 0.5)'
                ],
                align='left',
                font=dict(size=11),
                height=25
            )
        )])

        fig.update_layout(
            title_text="<b>IMD rank vs crime rate per 1,000 residents</b><br><sub>All results: p < 0.05</sub>",
            margin={"r":20,"t":80,"l":20,"b":20},
            height=400 + len(df_corr) * 25
        )
        return fig
    

    if view in ('station_near_far', 'station_decay'):
        try:
            response = requests.get(f"{API_BASE_URL}/station_analysis")
            response.raise_for_status()
            data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching /station_analysis: {e}")
            return empty_fig
        

            ## view 1
        if view == 'station_near_far':
                df_sp = pd.DataFrame(data['by_crime_type'])
                df_sp['proximity'] = df_sp['near_station'].map({
                    1: 'Near (≤500m)',
                    0: 'Far (>500m)'
                })


                pivot = df_sp.pivot(index='crime_type', columns='proximity', values='avg_rate').fillna(0)
                pivot['diff'] = pivot.get('Near (≤500m)', 0) - pivot.get('Far (>500m)', 0)
                sorted_types = pivot.sort_values('diff', ascending=False).index.tolist()
                df_sp['crime_type'] = pd.Categorical(df_sp['crime_type'], categories=sorted_types, ordered=True)
                df_sp = df_sp.sort_values('crime_type')

                fig = px.bar(
                    df_sp,
                    x='crime_type',
                    y='avg_rate',
                    color='proximity',
                    barmode='group',
                    color_discrete_map={
                        'Near (≤500m)': '#d73027',
                        'Far (>500m)': '#4575b4'
                    },
                    title='RQ2 — Crime rate near vs far from TFL stations by crime type',
                    labels={
                        'crime_type': 'Crime Type',
                        'avg_rate': 'Avg annual rate per 1,000 residents',
                        'proximity': 'Proximity'
                    }
                )
                fig.update_layout(
                    margin={"r": 20, "t": 50, "l": 20, "b": 120},
                    xaxis_tickangle=-40
                )
                return fig

        # View 2
        if view == 'station_decay':
            df_decay = pd.DataFrame(data['decay'])
            band_order = ['0-250m','250-500m','500-750m','750-1000m','1000-1500m','1500-2000m','+2km']
            df_decay['band'] = pd.Categorical(
                df_decay['band'], categories=band_order, ordered=True
            )
            df_decay = df_decay.sort_values('band')

            fig = px.line(
                df_decay,
                x='band',
                y='avg_rate',
                markers=True,
                title='RQ2 — Crime rate decay with distance from nearest TFL station',
                labels={
                    'band': 'Distance from nearest station',
                    'avg_rate': 'Avg annual crime rate per 1,000 residents'
                }
            )
            fig.update_traces(
                line=dict(color='#d73027', width=2.5),
                marker=dict(size=8, color='#d73027')
            )
            fig.update_layout(margin={"r": 20, "t": 50, "l": 20, "b": 40})
            return fig

    if not cached_crime_data:
        return empty_fig

    df = pd.DataFrame(cached_crime_data)
    if df.empty:
        empty_fig.layout.annotations[0]['text'] = "No data for that selection"
        return empty_fig

    color_scale = px.colors.qualitative.Plotly

    if view == 'pie':
        crime_counts = df['crime_type'].value_counts().reset_index()
        crime_counts.columns = ['crime_type', 'count']

        labels = crime_counts['crime_type']
        values = crime_counts['count']

        all_crime_types = sorted(df['crime_type'].unique())
        color_map = {crime: color_scale[i % len(color_scale)] for i, crime in enumerate(all_crime_types)}
        df_colors = [color_map.get(crime, '#808080') for crime in crime_counts['crime_type']]

        fig = go.Figure(data=[go.Pie(
            labels=labels,
            values=values,
            hole=.4,
            pull=[0.01] * len(labels),
            sort=False
        )])

        fig.update_traces(
            textinfo='none',
            hoverinfo='label+percent+value',
            marker=dict(colors=df_colors, line=dict(color='#FFFFFF', width=1))
        )

        fig.update_layout(
            title_text=f"Crime split (Total: {len(df)})",
            margin={"r":20,"t":40,"l":20,"b":20},
            showlegend=True,
            legend_title_text='Crime Types',
            legend=dict(
                orientation="v",
                yanchor="top",
                y=1.0
            )
        )
        return fig



    if view == 'borough':
        if 'borough' not in df.columns:
            empty_fig.layout.annotations[0]['text'] = "No borough info available"
            return empty_fig

        borough_counts = df['borough'].value_counts().reset_index()
        borough_counts.columns = ['borough', 'count']
        borough_counts = borough_counts.sort_values('count', ascending=False)

        fig = px.bar(
            borough_counts,
            x='borough',
            y='count',
            title='Crimes by borough',
        )
        fig.update_layout(margin={"r":20,"t":40,"l":20,"b":20}, xaxis_title='Borough', yaxis_title='Number of crimes')
        return fig


    return empty_fig

if __name__ == '__main__':
    app.run(debug=True, port=8050)