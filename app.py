import dash
import dash_bootstrap_components as dbc
from dash import dcc, html, Input, Output, State
import plotly.express as px
import plotly.graph_objects as go
import requests
import pandas as pd
import json
from dash import callback_context 

# --- Configuration ---
API_BASE_URL = "http://127.0.0.1:8000"  
BOROUGH_GEOJSON_FILE = 'London Boroughs.geojson'

# --- Pre-load GeoJSON ---
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
    """Creates the card containing all filters."""
    return dbc.Card(
        dbc.CardBody([
            html.H4("Crime Filters", className="card-title"),
            
            # Date Range Filter
            html.P("Select Date Range (Month):", className="card-text"),
            dcc.DatePickerRange(
                id='date-picker-range',
                min_date_allowed='2020-01',
                max_date_allowed='2025-12', 
                start_date='2025-01',
                end_date='2025-03',
                display_format='YYYY-MM',
                start_date_placeholder_text='Start YYYY-MM',
                end_date_placeholder_text='End YYYY-MM',
                className="mb-3 w-100"
            ),
            
            # Borough Filter
            html.P("Select Borough:", className="card-text"),
            dcc.Dropdown(
                id='borough-dropdown',
                placeholder="All Boroughs",
                className="mb-3",
                multi=True
            ),
            
            # Crime Type Filter
            html.P("Select Crime Type:", className="card-text"),
            dcc.Dropdown(
                id='crime-type-dropdown',
                placeholder="All Crime Types",
                className="mb-3",
                multi=True
            ),
            
            # Update Button
            dbc.Button("Apply Filters", id="apply-filters-button", color="primary", className="w-100"),

            # Placeholders for the custom legend
            html.Hr(className="my-4"),
            html.H5("Legend", id="legend-title", className="card-title"),
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
                    {"label": "Dot Map", "value": "dot"},
                    {"label": "Choropleth Map", "value": "choropleth"},
                    {"label": "Station Proximity (RQ2)", "value": "station_proximity"},
                ],
                value="dot", 
                inline=True,
                className="mb-3",
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
    """Creates the card for the analysis charts (pie, trend, borough, deprivation)."""
    return dbc.Card(
        dbc.CardBody([
            html.H4("Crime Analysis", className="card-title mb-3"),
            dbc.RadioItems(
                id="analysis-view-selector",
                options=[
                    {"label": "Crime Breakdown", "value": "pie"},
                    {"label": "Time Trend", "value": "time_trend"},
                    {"label": "Borough Comparison", "value": "borough"},
                    {"label": "Deprivation Link", "value": "deprivation"},
                    {"label": "IMD Correlation", "value": "correlation"},
                    {"label": "Seasonal Trends", "value": "seasonal"},
                    {"label": "Station: Near vs Far (RQ2)", "value": "station_near_far"},
                    {"label": "Station: Distance Decay (RQ2)", "value": "station_decay"},
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
], fluid=True, className="bg-light p-4")

@app.callback(
    Output('borough-dropdown', 'options'),
    Input('borough-dropdown', 'id') # Trigger on page load
)
def populate_boroughs(_):
    """Fetches the list of boroughs from the API to populate the dropdown."""
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
    """Fetches the list of crime types from the API to populate the dropdown."""
    try:
        response = requests.get(f"{API_BASE_URL}/crime_types")
        response.raise_for_status()
        data = response.json()
        return [{"label": c, "value": c} for c in data.get('crime_types', [])]
    except requests.exceptions.RequestException as e:
        print(f"Error fetching crime types: {e}")
        return []

# Combined callback: fetch data, render map, and cache in one step
@app.callback(
    [Output('crime-map', 'figure'),
     Output('legend-title', 'children'),
     Output('legend-container', 'children'),
     Output('cached-crime-data', 'data'),
     Output('cached-borough-data', 'data')],
    [Input('apply-filters-button', 'n_clicks'),
     Input('map-type-selector', 'value')],
    [State('date-picker-range', 'start_date'),
     State('date-picker-range', 'end_date'),
     State('borough-dropdown', 'value'),
     State('crime-type-dropdown', 'value'),
     State('cached-crime-data', 'data'),
     State('cached-borough-data', 'data')],
    prevent_initial_call=True
)
def update_map_and_cache(n_clicks, map_type, start_date, end_date, boroughs, crime_types, cached_crime_data, cached_borough_data):
    """Fetch data on filter click OR use cache on view switch - render immediately!"""
    
    empty_map_fig = go.Figure(go.Scattermapbox())
    empty_map_fig.update_layout(
        mapbox_style="carto-positron",
        mapbox_center={"lat": 51.5074, "lon": -0.1278},
        mapbox_zoom=9,
        title="Please apply filters to load data",
        margin={"r":0,"t":40,"l":0,"b":0}
    )
    
    ctx = callback_context
    triggered_id = ctx.triggered[0]['prop_id'].split('.')[0] if ctx.triggered else None
    
    # If triggered by apply-filters-button, fetch fresh data
    if triggered_id == 'apply-filters-button':
        if not start_date or not end_date:
            return (empty_map_fig, "Legend", [], None, None)
        
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
            empty_map_fig.update_layout(title="Error: Borough GeoJSON file not loaded.")
            return (empty_map_fig, "Legend", [], cached_crime_data, cached_borough_data)
        
        if not borough_data:
            empty_map_fig.update_layout(title="No data - click Apply Filters")
            return (empty_map_fig, "Legend", [], cached_crime_data, cached_borough_data)
        
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
            title=f"Crime Count by Borough"
        )
        fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0})
        legend_title = "Choropleth Legend"
        legend_content = html.P("Green = Low crime, Red = High crime", className="text-muted small")
    elif map_type == 'station_proximity':
        try:
            response = requests.get(f"{API_BASE_URL}/station_map_data")
            response.raise_for_status()
            st_data = response.json()
        except requests.exceptions.RequestException as e:
            print(f"Error fetching station map data: {e}")
            empty_map_fig.update_layout(title="Error loading station data")
            return (empty_map_fig, "Legend", [], cached_crime_data, cached_borough_data)

        df_st = pd.DataFrame(st_data)
        df_st = df_st[df_st.avg_rate_500 > 0]

        # Normalise rate to 0-1 for colour scale
        p95 = df_st.avg_rate_500.quantile(0.95)
        df_st['norm'] = (df_st.avg_rate_500 / p95).clip(upper=1)
        df_st['size'] = (df_st.norm * 18 + 6).round(1)
        london_avg = round(float(df_st.avg_rate_500.mean()), 1)
        df_st['diff'] = (df_st.avg_rate_500 - london_avg).round(1)
        df_st['label'] = df_st.apply(
            lambda r: (
                f"<b>{r['name']}</b><br>"
                f"Crime rate within 500m: <b>{r['avg_rate_500']}/1k</b><br>"
                f"{'▲' if r['diff'] > 0 else '▼'} {abs(r['diff'])} vs London avg ({london_avg}/1k)"
            ),
            axis=1
        )
        fig_map = go.Figure()

        # Station circles — coloured by avg crime rate
        fig_map.add_trace(go.Scattermapbox(
            lat=df_st['lat'],
            lon=df_st['lon'],
            mode='markers',
            marker=dict(
                size=df_st['size'],
                color=df_st['avg_rate_500'],
                colorscale=[
                    [0.0,  '#4575b4'],
                    [0.25, '#74add1'],
                    [0.5,  '#fee090'],
                    [0.75, '#f46d43'],
                    [1.0,  '#a50026'],
                ],
                cmin=0,
                cmax=float(p95),
                colorbar=dict(
                    title='Avg crime rate<br>per 1,000',
                    thickness=12,
                    len=0.6,
                ),
                opacity=0.85,
            ),
            text=df_st['label'],
            hoverinfo='text',
            name='TFL Stations'
        ))

        fig_map.update_layout(
            mapbox_style='carto-positron',
            mapbox_center={'lat': 51.5074, 'lon': -0.1278},
            mapbox_zoom=9.5,
            margin={'r': 0, 't': 40, 'l': 0, 'b': 0},
            title='RQ2 — Avg crime rate within 500m of each TFL station',
            showlegend=False
        )

        legend_title = "Station Proximity"
        legend_content = html.Div([
            html.P("Each dot = one TFL station", className="small text-muted"),
            html.P("Colour + size = avg crime rate within 500m", className="small text-muted"),
            html.P("Blue = low crime  →  Red = high crime", className="small text-muted"),
        ])
        return (fig_map, legend_title, legend_content, cached_crime_data, cached_borough_data)




    else:  # dot map
        if not crime_data:
            empty_map_fig.update_layout(title="No data - click Apply Filters")
            return (empty_map_fig, "Legend", [], cached_crime_data, cached_borough_data)
        
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
        
        legend_title = f"Legend ({len(unique_crime_types)} types)"
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
            title=f"Displaying {len(df)} Crime Incidents"
        )
        fig_map.update_layout(margin={"r":0,"t":40,"l":0,"b":0}, showlegend=False)
    
    return (fig_map, legend_title, legend_content, crime_data, borough_data)

@app.callback(
    Output('analysis-chart', 'figure'),
    [Input('analysis-view-selector', 'value'),
     Input('cached-crime-data', 'data')]
)
def update_analysis_chart(view, cached_crime_data):
    """Update the analysis chart based on selected view and cached data."""

    empty_fig = go.Figure()
    empty_fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        annotations=[{
            "text": "Apply filters to see analysis",
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
            empty_fig.layout.annotations[0]['text'] = "No IMD / crime-rate data available"
            return empty_fig

        df_dec = pd.DataFrame(data)
        df_dec = df_dec.dropna(subset=['imd_decile', 'annual_rate_per_1000'])
        if df_dec.empty:
            empty_fig.layout.annotations[0]['text'] = "No IMD / crime-rate data available"
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
            empty_fig.layout.annotations[0]['text'] = "No IMD / crime-rate data available"
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
            title='Deprivation vs Crime Rate (IMD bands 1–3, 4–7, 8–10)'
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
            title='Seasonal Crime Trends (average number of crimes per month)',
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
            title_text="<b>Pearson Correlation: IMD Rank vs Annual Crime Rate per 1,000 Residents</b><br><sub>All results: p < 0.05</sub>",
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
                    title='RQ2 — Crime Rate Near vs Far from TFL Stations by Crime Type',
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
                    title='RQ2 — Crime Rate Decay with Distance from Nearest TFL Station',
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
        empty_fig.layout.annotations[0]['text'] = "No data found for this selection"
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
            title_text=f"Crime Breakdown (Total: {len(df)})",
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

    if view == 'time_trend':
        trend = df.groupby('month').size().reset_index(name='count').sort_values('month')
        fig = px.line(
            trend,
            x='month',
            y='count',
            markers=True,
            title='Crime Trend Over Time'
        )
        fig.update_layout(margin={"r":20,"t":40,"l":20,"b":20}, xaxis_title='Month', yaxis_title='Number of crimes')
        return fig

    if view == 'borough':
        if 'borough' not in df.columns:
            empty_fig.layout.annotations[0]['text'] = "Borough information not available"
            return empty_fig

        borough_counts = df['borough'].value_counts().reset_index()
        borough_counts.columns = ['borough', 'count']
        borough_counts = borough_counts.sort_values('count', ascending=False)

        fig = px.bar(
            borough_counts,
            x='borough',
            y='count',
            title='Crimes by Borough (selected period)',
        )
        fig.update_layout(margin={"r":20,"t":40,"l":20,"b":20}, xaxis_title='Borough', yaxis_title='Number of crimes')
        return fig


    return empty_fig

if __name__ == '__main__':
    app.run(debug=True, port=8050)