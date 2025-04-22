import streamlit as st
import pandas as pd
import plotly.express as px

# Load data
shipments_df = pd.read_csv("shipments.csv", parse_dates=["pickup_time", "delivery_time"])
drivers_df = pd.read_csv("drivers.csv")
vehicles_df = pd.read_csv("vehicles.csv")
routes_df = pd.read_csv("routes.csv")

# Add delivery_date if not already present
if "delivery_date" not in shipments_df.columns:
    shipments_df["delivery_date"] = shipments_df["delivery_time"].dt.date

# Add destination coordinates
city_coords = {
    "New York": {"lat": 40.7128, "lon": -74.0060},
    "Los Angeles": {"lat": 34.0522, "lon": -118.2437},
    "Houston": {"lat": 29.7604, "lon": -95.3698},
    "Phoenix": {"lat": 33.4484, "lon": -112.0740},
    "Chicago": {"lat": 41.8781, "lon": -87.6298}
}
shipments_df["dest_lat"] = shipments_df["destination"].map(lambda x: city_coords.get(x, {}).get("lat"))
shipments_df["dest_lon"] = shipments_df["destination"].map(lambda x: city_coords.get(x, {}).get("lon"))

# Warn if any destination is missing coordinates
missing_coords = shipments_df[shipments_df["dest_lat"].isna()]["destination"].unique()
if len(missing_coords) > 0:
    st.warning(f"Missing coordinates for: {', '.join(missing_coords)}")

# Sidebar filters
st.sidebar.header("Filter Options")
selected_driver = st.sidebar.selectbox("Filter by Driver", options=["All"] + list(shipments_df["driver_id"].unique()))
breakdown_type = st.sidebar.selectbox("Compare Missing/Damaged By", ["driver_id", "vehicle_id", "route_id"])
map_status_type = st.sidebar.radio("Map Incident Type", ["Missing", "Damaged"])

# Filter by driver
filtered = shipments_df.copy()
if selected_driver != "All":
    filtered = filtered[filtered["driver_id"] == selected_driver]

# KPI Metrics
total_missing = filtered[filtered["status"] == "Missing"].shape[0]
damaged_count = filtered[filtered["status"] == "Damaged"].shape[0]

missing_shipments = filtered[filtered["status"] == "Missing"]
if not missing_shipments.empty and missing_shipments["pickup_time"].notnull().all() and missing_shipments["delivery_time"].notnull().all():
    transit_times = (missing_shipments["delivery_time"] - missing_shipments["pickup_time"])
    avg_transit_days = transit_times.dt.total_seconds().mean() / 86400
    avg_transit_text = f"{avg_transit_days:.1f} days"
else:
    avg_transit_text = "N/A"

# KPI Display
st.title("Shipping Errors Dashboard")
col1, col2, col3 = st.columns(3)
col1.metric("📦 Total Missing", total_missing)
col2.metric("🚚 Avg Transit Time (Missing)", avg_transit_text)
col3.metric("📦 Total Damaged", damaged_count)

# Pie Chart: Shipment Status
status_fig = px.pie(filtered, names="status", title="📊 Shipment Status Distribution", hole=0.4)
st.plotly_chart(status_fig, use_container_width=True)

# Bar Chart: % Missing/Damaged by Group
total_by_group = filtered.groupby(breakdown_type).size().reset_index(name="total")
incident_by_group = (
    filtered[filtered["status"].isin(["Missing", "Damaged"])]
    .groupby([breakdown_type, "status"])
    .size().reset_index(name="count")
)
merged = pd.merge(incident_by_group, total_by_group, on=breakdown_type)
merged["percent"] = (merged["count"] / merged["total"] * 100).round(2)

comparison_fig = px.bar(
    merged, x=breakdown_type, y="percent", color="status", barmode="group",
    title=f"% of Missing and Damaged by {breakdown_type.replace('_id', '').capitalize()}",
    labels={"percent": "% of Shipments"}
)
st.plotly_chart(comparison_fig, use_container_width=True)

# Time Trend: Missing Over Time
trend_data = filtered[filtered["status"] == "Missing"].groupby("delivery_date").size().reset_index(name="count")
trend_fig = px.line(trend_data, x="delivery_date", y="count", title="📅 Missing Shipments Over Time")
st.plotly_chart(trend_fig, use_container_width=True)

# Map: % Incident by Destination
def generate_percentage_map(filtered_df, status_type):
    total_shipments = (
        filtered_df.groupby("destination")
        .agg(total=("status", "size"), lat=("dest_lat", "first"), lon=("dest_lon", "first"))
        .reset_index()
    )
    status_shipments = (
        filtered_df[filtered_df["status"] == status_type]
        .groupby("destination")
        .agg(incident=("status", "size"))
        .reset_index()
    )
    merged = pd.merge(total_shipments, status_shipments, on="destination", how="left")
    merged["incident"] = merged["incident"].fillna(0)
    merged["percent_incident"] = (merged["incident"] / merged["total"] * 100).round(2)

    map_fig = px.scatter_mapbox(
        merged,
        lat="lat", lon="lon",
        size="percent_incident", size_max=30,
        hover_name="destination",
        hover_data={"percent_incident": True, "total": True, "incident": True},
        color_discrete_sequence=["red"],
        zoom=3, height=400,
        title=f"🌍 % of {status_type} Shipments by Destination"
    )
    map_fig.update_layout(mapbox_style="open-street-map")
    return map_fig

# Display Map
map_fig = generate_percentage_map(filtered, map_status_type)
st.plotly_chart(map_fig, use_container_width=True)