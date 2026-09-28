import React, { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { apiRequest, fmtDate } from "../api";

export default function Home() {
  const [events, setEvents] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    apiRequest("/events?upcoming=true", { auth: false })
      .then(setEvents)
      .catch((e) => setError(e.message));
  }, []);

  return (
    <div className="container">
      <h1>Upcoming Events</h1>
      {error && <div className="error-box">{error}</div>}
      {events === null && !error && <div className="card muted">Loading...</div>}
      {events && events.length === 0 && (
        <div className="card muted">No upcoming events yet. Register as an organizer to create one.</div>
      )}
      {events && events.map((ev) => (
        <div className="card" key={ev.event_id}>
          <div className="event-row">
            <div>
              <h2 style={{ marginBottom: 4 }}>{ev.event_name}</h2>
              <div className="muted">{fmtDate(ev.event_date)} · {ev.start_time} · {ev.venue || ev.online_link || "TBA"}</div>
            </div>
            <div style={{ textAlign: "right" }}>
              <span className={`badge ${ev.status.toLowerCase()}`}>{ev.status}</span><br />
              <Link className="btn" style={{ marginTop: 8, display: "inline-block" }} to={`/events/${ev.event_id}`}>
                View / RSVP
              </Link>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}
