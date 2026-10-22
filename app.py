"""Streamlit viewer for the final EV charging deployment output.

The map is intentionally read-only: every station value shown here comes
directly from the final GeoJSON produced by the research pipeline.
"""

from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Any

import folium
import pandas as pd
import streamlit as st
from folium.plugins import Fullscreen
from pyproj import Transformer
from streamlit_folium import st_folium


PROJECT_DIR = Path(__file__).resolve().parent
FINAL_GEOJSON = (
    PROJECT_DIR
    / "ev_charging_colombo"
    / "data"
    / "FINAL_Phased_EV_Plan_Colombo.geojson"
)
PHASE_METRICS_CSV = (
    PROJECT_DIR / "ev_charging_colombo" / "data" / "phase4_deployment_metrics.csv"
)
SOURCE_CRS = "EPSG:32644"
DISPLAY_CRS = "EPSG:4326"

PHASE_STYLES = {
    "Phase_1_2027": {"color": "#16803c", "label": "Phase 1 (2027)"},
    "Phase_2_2030": {"color": "#c86b00", "label": "Phase 2 (2030)"},
    "Phase_3_2035": {"color": "#b42318", "label": "Phase 3 (2035)"},
}


@st.cache_data(show_spinner=False)
def load_final_output() -> tuple[dict[str, Any], pd.DataFrame]:
    """Load and validate the pipeline's final station output without altering it."""
    if not FINAL_GEOJSON.exists():
        raise FileNotFoundError(f"Final output was not found: {FINAL_GEOJSON}")

    with FINAL_GEOJSON.open("r", encoding="utf-8") as source:
        geojson = json.load(source)

    crs_name = geojson.get("crs", {}).get("properties", {}).get("name", "")
    if "32644" not in crs_name:
        raise ValueError(
            f"Expected final output CRS EPSG:32644, but found {crs_name or 'missing CRS'}."
        )

    features = geojson.get("features")
    if not isinstance(features, list) or not features:
        raise ValueError("The final GeoJSON contains no station features.")

    rows: list[dict[str, Any]] = []
    for feature in features:
        geometry = feature.get("geometry", {})
        if geometry.get("type") != "Point":
            raise ValueError("The final output contains a non-point station geometry.")
        coordinates = geometry.get("coordinates")
        if (
            not isinstance(coordinates, list)
            or len(coordinates) != 2
            or not all(isinstance(value, (int, float)) for value in coordinates)
        ):
            raise ValueError("A station has invalid point coordinates.")

        properties = feature.get("properties")
        if not isinstance(properties, dict):
            raise ValueError("A station is missing its properties object.")

        rows.append(
            {
                **properties,
                "_x_utm": coordinates[0],
                "_y_utm": coordinates[1],
            }
        )

    stations = pd.DataFrame(rows)
    return geojson, stations


@st.cache_data(show_spinner=False)
def load_phase_metrics() -> pd.DataFrame | None:
    """Load optional pipeline metrics; return None when that output is absent."""
    if not PHASE_METRICS_CSV.exists():
        return None
    return pd.read_csv(PHASE_METRICS_CSV)


def format_value(value: Any) -> str:
    """Format a stored value for display without inventing a replacement value."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return "Not available in final output"
    if isinstance(value, float):
        return f"{value:.6f}".rstrip("0").rstrip(".")
    return str(value)


def popup_html(properties: dict[str, Any], latitude: float, longitude: float) -> str:
    """Create a popup containing every property stored for one station."""
    rows = [
        (
            html.escape(str(key)),
            html.escape(format_value(value)),
        )
        for key, value in properties.items()
    ]
    rows.extend(
        [
            ("latitude_wgs84", f"{latitude:.8f}"),
            ("longitude_wgs84", f"{longitude:.8f}"),
        ]
    )
    table = "".join(
        f"<tr><th style='text-align:left;padding:3px 8px 3px 0'>{key}</th>"
        f"<td style='padding:3px 0'>{value}</td></tr>"
        for key, value in rows
    )
    return (
        "<div style='min-width:300px;max-height:420px;overflow:auto'>"
        "<strong>Final thesis evaluation station</strong>"
        f"<table>{table}</table></div>"
    )


def build_map(features: list[dict[str, Any]], transformer: Transformer) -> folium.Map:
    """Build a map from the selected final-output features only."""
    points: list[tuple[float, float]] = []
    for feature in features:
        x, y = feature["geometry"]["coordinates"]
        longitude, latitude = transformer.transform(x, y)
        points.append((latitude, longitude))

    map_view = folium.Map(
        location=[
            sum(point[0] for point in points) / len(points),
            sum(point[1] for point in points) / len(points),
        ],
        zoom_start=13,
        control_scale=True,
        tiles="OpenStreetMap",
    )
    Fullscreen(position="topright").add_to(map_view)

    for feature, (latitude, longitude) in zip(features, points):
        properties = feature["properties"]
        phase = properties.get("Deployment_Phase")
        style = PHASE_STYLES.get(
            phase,
            {"color": "#444444", "label": "Phase not defined in final output"},
        )
        station_id = format_value(properties.get("station_id"))
        folium.CircleMarker(
            location=[latitude, longitude],
            radius=8,
            color="#111111",
            weight=1,
            fill=True,
            fill_color=style["color"],
            fill_opacity=0.9,
            tooltip=f"{station_id} | {style['label']}",
            popup=folium.Popup(
                popup_html(properties, latitude, longitude),
                max_width=500,
            ),
        ).add_to(map_view)

    if len(points) > 1:
        map_view.fit_bounds(points, padding=(25, 25))
    return map_view


def main() -> None:
    st.set_page_config(
        page_title="Final EV Charging Deployment Map",
        page_icon="⚡",
        layout="wide",
    )
    st.title("Final EV Charging Deployment Map")
    st.caption(
        "Read-only view of the final thesis evaluation output. "
        "No synthetic station records or calculated replacement values are added."
    )

    try:
        geojson, stations = load_final_output()
    except (FileNotFoundError, ValueError, json.JSONDecodeError) as error:
        st.error(f"Final output cannot be displayed: {error}")
        st.stop()

    transformer = Transformer.from_crs(SOURCE_CRS, DISPLAY_CRS, always_xy=True)
    stations["latitude_wgs84"], stations["longitude_wgs84"] = zip(
        *[
            transformer.transform(x, y)
            for x, y in zip(stations["_x_utm"], stations["_y_utm"])
        ]
    )

    phase_options = [
        phase for phase in PHASE_STYLES if phase in stations["Deployment_Phase"].unique()
    ]
    with st.sidebar:
        st.header("Map filters")
        selected_phases = st.multiselect(
            "Deployment phase",
            options=phase_options,
            default=phase_options,
            format_func=lambda phase: PHASE_STYLES[phase]["label"],
        )
        station_search = st.text_input("Station ID", placeholder="Example: S01").strip()
        st.divider()
        st.write(f"**Source:** `{FINAL_GEOJSON.name}`")
        st.write(f"**Source CRS:** `{SOURCE_CRS}`")
        st.write(f"**Records in final output:** `{len(stations)}`")

    filtered = stations[stations["Deployment_Phase"].isin(selected_phases)].copy()
    if station_search:
        filtered = filtered[
            filtered["station_id"].astype(str).str.contains(
                station_search, case=False, na=False
            )
        ]

    metric_columns = st.columns(4)
    metric_columns[0].metric("Final stations", len(filtered))
    for metric_column, phase in zip(metric_columns[1:], phase_options[:3]):
        metric_column.metric(
            PHASE_STYLES[phase]["label"],
            int((filtered["Deployment_Phase"] == phase).sum()),
        )

    if filtered.empty:
        st.warning("No final-output stations match the selected filters.")
        st.stop()

    selected_features = [
        feature
        for feature in geojson["features"]
        if feature["properties"].get("station_id")
        in set(filtered["station_id"].astype(str))
        and feature["properties"].get("Deployment_Phase") in selected_phases
    ]
    st.subheader("Station locations")
    st_folium(build_map(selected_features, transformer), height=680, width=None)

    tab_details, tab_metrics, tab_raw = st.tabs(
        ["Station details", "Pipeline metrics", "Raw final output"]
    )
    with tab_details:
        display_columns = [
            column
            for column in stations.columns
            if not column.startswith("_")
        ]
        st.dataframe(
            filtered[display_columns],
            use_container_width=True,
            hide_index=True,
        )
    with tab_metrics:
        metrics = load_phase_metrics()
        if metrics is None:
            st.info("The pipeline metrics CSV is not available.")
        else:
            st.dataframe(metrics, use_container_width=True, hide_index=True)
    with tab_raw:
        st.json({"type": "FeatureCollection", "features": selected_features})


if __name__ == "__main__":
    main()
