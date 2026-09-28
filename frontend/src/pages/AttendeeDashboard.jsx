import React, { useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { apiRequest, getUser, fmtDate } from "../api";

export default function AttendeeDashboard() {
  const navigate = useNavigate();
  const user = getUser();
  const [myRsvps, setMyRsvps] = useState(null);
  const [events, setEvents] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => { if (!user) navigate("/login"); }, []);

  useEffect(() => {
    if (!user) return;
    apiRequest("/rsvps/me").then(setMyRsvps).catch((e) => setError(e.message));
    apiRequest("/events?upcoming=true", { auth: false }).then(setEvents).catch(() => {});
  }, [user]);

  if (!user) return null;

  return (
    <div className="container">
      <h1>My RSVPs</h1>
      {error && <div className="error-box">{error}</div>}
      {myRsvps && myRsvps.length === 0 && <div className="card muted">You haven't RSVPed to any events yet.</div>}
      {myRsvps && myRsvps.map((r) => (
        <div className="card event-row" key={r.rsvp_id}>
          <div>
            <h2 style={{ marginBottom: 4 }}>{r.event_name}</h2>
            <div className="muted">{fmtDate(r.event_date)} · {r.venue || "TBA"}</div>
          </div>
          <span className={`badge ${r.status.toLowerCase()}`}>{r.status.replace("_", " ")}</span>
        </div>
      ))}

      <h2 style={{ marginTop: 24 }}>Discover Events</h2>
      {events && events.length === 0 && <div className="card muted">No upcoming events.</div>}
      {events && events.map((ev) => (
        <div className="card event-row" key={ev.event_id}>
          <div>
            <h2 style={{ marginBottom: 4 }}>{ev.event_name}</h2>
            <div className="muted">{fmtDate(ev.event_date)} · {ev.start_time} · {ev.venue || "TBA"}</div>
          </div>
          <Link className="btn" to={`/events/${ev.event_id}`}>View / RSVP</Link>
        </div>
      ))}
    </div>
  );
}
