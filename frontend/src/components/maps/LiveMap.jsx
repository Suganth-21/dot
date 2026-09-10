import React, { useEffect } from "react";
import { MapContainer, TileLayer, Marker, Popup, Polyline, CircleMarker, useMap } from "react-leaflet";
import L from "leaflet";

// Fix default marker icons (CRA/webpack asset issue)
delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png",
  iconUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png",
  shadowUrl: "https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png",
});

function vehicleIcon(color = "#5b6cff") {
  return L.divIcon({
    className: "",
    html: `<div style="transform:translate(-50%,-50%);position:relative">
      <div style="width:34px;height:34px;border-radius:50%;background:${color};box-shadow:0 6px 16px rgba(28,27,25,.28);display:flex;align-items:center;justify-content:center;border:3px solid #fff">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#fff" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round"><path d="M10 17h4V5H2v12h3"/><path d="M20 17h2v-3.34a4 4 0 0 0-1.17-2.83L19 9h-5v8h1"/><circle cx="7.5" cy="17.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/></svg>
      </div>
      <div style="width:34px;height:34px;border-radius:50%;background:${color};opacity:.25;position:absolute;top:0;left:0;animation:ping 1.4s ease-out infinite"></div>
    </div>
    <style>@keyframes ping{0%{transform:scale(1);opacity:.4}100%{transform:scale(2.4);opacity:0}}</style>`,
    iconSize: [34, 34],
    iconAnchor: [0, 0],
  });
}

function dotIcon(color) {
  return L.divIcon({
    className: "",
    html: `<div style="transform:translate(-50%,-50%);width:14px;height:14px;border-radius:50%;background:${color};border:2.5px solid #fff;box-shadow:0 2px 6px rgba(0,0,0,.25)"></div>`,
    iconSize: [14, 14],
    iconAnchor: [0, 0],
  });
}

function Recenter({ center, zoom }) {
  const map = useMap();
  useEffect(() => {
    if (center) map.setView(center, zoom ?? map.getZoom(), { animate: true });
  }, [center, zoom, map]);
  return null;
}

export default function LiveMap({
  center = [13.0827, 80.2707],
  zoom = 11,
  height = 420,
  vehicles = [],
  stops = [],
  markers = [],
  routePath = null,
  bubbles = [],
  follow = false,
  className = "",
}) {
  return (
    <div className={className} style={{ height, borderRadius: "1.5rem", overflow: "hidden" }}>
      <MapContainer center={center} zoom={zoom} style={{ height: "100%", width: "100%" }} scrollWheelZoom={false}>
        <TileLayer
          attribution='&copy; OpenStreetMap'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />
        {follow && vehicles[0]?.pos && <Recenter center={[vehicles[0].pos.lat, vehicles[0].pos.lng]} />}
        {routePath && routePath.length > 1 && (
          <Polyline positions={routePath.map((p) => [p.lat, p.lng])} pathOptions={{ color: "#5b6cff", weight: 3, opacity: 0.5, dashArray: "6 8" }} />
        )}
        {stops.map((s, i) => (
          <Marker key={i} position={[s.lat, s.lng]} icon={dotIcon(s.status === "DONE" ? "#3fbf9a" : s.status === "CURRENT" || s.status === "ARRIVED" ? "#e0a53d" : "#8a8681")}>
            <Popup>
              <b>Stop {s.order}</b> — {s.pharmacyName}
              <br />{s.status}
            </Popup>
          </Marker>
        ))}
        {markers.map((m, i) => (
          <Marker key={"m" + i} position={[m.lat, m.lng]} icon={dotIcon(m.color || "#5b6cff")}>
            <Popup>{m.label}</Popup>
          </Marker>
        ))}
        {bubbles.map((b, i) => (
          <CircleMarker key={"b" + i} center={[b.lat, b.lng]} radius={Math.max(6, b.value / 3)} pathOptions={{ color: "#5b6cff", fillColor: "#5b6cff", fillOpacity: 0.35, weight: 1 }}>
            <Popup>{b.city || b.label}: {b.value}</Popup>
          </CircleMarker>
        ))}
        {vehicles.map((v, i) => (
          v.pos && (
            <Marker key={"v" + i} position={[v.pos.lat, v.pos.lng]} icon={vehicleIcon(v.color || "#5b6cff")}>
              <Popup>
                <b>{v.reg || "Vehicle"}</b><br />
                {v.agent && <>Agent: {v.agent}<br /></>}
                {v.eta != null && <>ETA: {v.eta} min</>}
              </Popup>
            </Marker>
          )
        ))}
      </MapContainer>
    </div>
  );
}
