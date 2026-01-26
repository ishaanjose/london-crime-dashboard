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
        className="shadow-sm border-0"
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
                    style={'height': '70vh'}
                )
            )
        ]),
        className="shadow-sm border-0"
    )

def create_pie_chart_card():
    """Creates the card for the crime type pie chart."""
    return dbc.Card(
        dbc.CardBody([
            dcc.Loading(
                id="loading-pie-chart",
                type="default",
                children=dcc.Graph(
                    id='crime-pie-chart',
                    figure={},
                    style={'height': '40vh'}
                )
            )
        ]),
        className="shadow-sm border-0"
    )

app.layout = dbc.Container([
    dcc.Store(id='cached-crime-data'),  # Add this to cache raw crime data
    dcc.Store(id='cached-borough-data'),  # Add this to cache borough summary
    dbc.Row([
        dbc.Col(create_filter_card(), md=4),
        dbc.Col(create_map_card(), md=8),
    ]),
    dbc.Row([
        dbc.Col(create_pie_chart_card(), md=12, className="mt-4"), 
    ], className="mb-4"),
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
    
    # Determine what triggered this callback
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
        # Triggered by map-type-selector, use cached data
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
    Output('crime-pie-chart', 'figure'),
    Input('apply-filters-button', 'n_clicks'),
    [State('date-picker-range', 'start_date'),
     State('date-picker-range', 'end_date'),
     State('borough-dropdown', 'value'),
     State('crime-type-dropdown', 'value')],
    prevent_initial_call=True 
)
def update_pie_chart(n_clicks, start_date, end_date, boroughs, crime_types):
    """Fetches aggregated data from the /summary endpoint to build the pie chart."""
    
    empty_layout = {
        "layout": {
            "paper_bgcolor": "rgba(0,0,0,0)",
            "plot_bgcolor": "rgba(0,0,0,0)",
            "annotations": [{
                "text": "Apply filters to see analysis",
                "xref": "paper", "yref": "paper",
                "showarrow": False, "font": {"size": 16}
            }]
        }
    }
    
    if not start_date or not end_date:
        return empty_layout

    params = {'start_date': start_date, 'end_date': end_date}
    if boroughs:
        params['borough'] = boroughs
    if crime_types:
        params['crime_type'] = crime_types

    try:
        response = requests.get(f"{API_BASE_URL}/summary", params=params)
        response.raise_for_status()
        data = response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error fetching /summary data: {e}")
        return empty_layout

    if not data or not data.get('crime_counts_by_type'):
        empty_layout["layout"]["annotations"][0]["text"] = "No data found for this selection"
        return empty_layout

    # Convert the summary dictionary to a DataFrame
    crime_counts = data['crime_counts_by_type']
    df = pd.DataFrame(list(crime_counts.items()), columns=['crime_type', 'count'])
    df = df.sort_values(by='count', ascending=False) # Sort by count
    
    if df.empty:
        empty_layout["layout"]["annotations"][0]["text"] = "No data found for this selection"
        return empty_layout

    labels = df['crime_type']
    values = df['count']
    
    # Use the same color map as the main map for consistency
    all_crime_types = sorted(pd.Series(list(crime_counts.keys())).unique())
    color_scale = px.colors.qualitative.Plotly
    
    # Create a mapping from crime_type to its color
    color_map = {crime: color_scale[i % len(color_scale)] for i, crime in enumerate(all_crime_types)}
    
    df_colors = [color_map.get(crime, '#808080') for crime in df['crime_type']] # .get for safety


    fig_pie = go.Figure(data=[go.Pie(
        labels=labels, 
        values=values, 
        hole=.4, # Use .4 for a donut chart
        pull=[0.01] * len(labels), # Adds a small separation
        sort=False # Use the order from the dataframe
    )])
    
    fig_pie.update_traces(
        textinfo='none', 
        hoverinfo='label+percent+value',
        marker=dict(colors=df_colors, line=dict(color='#FFFFFF', width=1)) # Use mapped colors
    )
    
    fig_pie.update_layout(
        title_text=f"Crime Breakdown (Total: {data['total_crimes']})",
        margin={"r":20,"t":40,"l":20,"b":20},
        showlegend=True, 
        legend_title_text='Crime Types',
        legend=dict(
            orientation="v",
            yanchor="top",
            y=1.0
        )
    )
    
    return fig_pie

if __name__ == '__main__':
    app.run(debug=True, port=8050)