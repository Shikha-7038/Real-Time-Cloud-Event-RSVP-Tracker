import React, { useEffect, useState, useCallback } from "react";
import { useParams, Link } from "react-router-dom";
import { apiRequest, getUser, fmtDate } from "../api";
import { useEventSocket } from "../hooks/useEventSocket";

export default function EventDetail() {
  const { eventId } = useParams();
  const user = getUser();
  const [event, setEvent] = useState(null);
  const [myStatus, setMyStatus] = useState(null);
  const [announcements, setAnnouncements] = useState([]);
  const [error, setError] = useState(null);
  const [confirmed, setConfirmed] = useState(false);

  // Real-time: this ONE hook opens a WebSocket and keeps `counts` in sync
  // the instant the backend broadcasts a change - no polling interval.
  const handleNewAnnouncement = useCallback((msg) => {
    setAnnouncements((prev) => [{ title: msg.title, message: msg.message, created_at: new Date().toISOString() }, ...prev]);
  }, []);
  const { counts, connected } = useEventSocket(eventId, handleNewAnnouncement);

  useEffect(() => {
    apiRequest(`/events/${eventId}`, { auth: false }).then(setEvent).catch((e) => setError(e.message));
    apiRequest(`/events/${eventId}/announcements`, { auth: false }).then(setAnnouncements).catch(() => {});
    if (user) {
      apiRequest("/rsvps/me").then((rsvps) => {
        const found = rsvps.find((r) => r.event_id === eventId);
        setMyStatus(found ? found.status : null);
      }).catch(() => {});
    }
    // Seed initial counts via REST (WebSocket only pushes on CHANGE, so we
    // need one initial read before the first change happens).
    apiRequest(`/events/${eventId}/counts`, { auth: false }).then((c) => {
      setInitialCounts(c);
    }).catch(() => {});
  }, [eventId, user]);

  const [initialCounts, setInitialCounts] = useState(null);
  const liveCounts = counts || initialCounts;

  async function rsvp(status) {
    setError(null);
    if (!user) { window.location.href = "/login"; return; }
    try {
      const result = await apiRequest(`/events/${eventId}/rsvp`, { method: "POST", body: { status } });
      setMyStatus(result.status);
      setConfirmed(true);
      // No manual refresh needed for counts - the WebSocket push updates
      // `counts` for every viewer (including this tab) automatically.
    } catch (err) {
      setError(err.message);
    }
  }

  if (!event) return <div className="container"><div className="card muted">{error || "Loading..."}</div></div>;

  return (
    <div className="container">
      <div className="card">
        <h1>{event.event_name}</h1>
        <p className="muted">{fmtDate(event.event_date)} · {event.start_time}{event.end_time ? ` - ${event.end_time}` : ""} · {event.venue || event.online_link || "TBA"}</p>
        <p>{event.description}</p>
        <span className={`badge ${event.status.toLowerCase()}`}>{event.status}</span>{" "}
        <span className="muted">Capacity: {event.maximum_capacity}</span>
      </div>

      {user && (
        <div className="card">
          <h2>Your RSVP</h2>
          {error && <div className="error-box">{error}</div>}
          <p className="muted">{myStatus ? `Current status: ${myStatus.replace("_", " ")}` : "You haven't responded yet."}</p>
          <button onClick={() => rsvp("GOING")}>Going</button>{" "}
          <button className="secondary" onClick={() => rsvp("MAYBE")}>Maybe</button>{" "}
          <button className="secondary" onClick={() => rsvp("NOT_GOING")}>Not Going</button>
          {confirmed && <p style={{ color: "var(--success)", fontWeight: 600, marginTop: 10 }}>Your RSVP has been recorded.</p>}
        </div>
      )}
      {!user && (
        <div className="card muted">
          <Link to="/login">Log in</Link> to RSVP to this event.
        </div>
      )}

      <div className="card">
        <h2>
          <span className={`live-dot ${connected ? "connected" : "disconnected"}`} />
          Live RSVP Counts {connected ? "(live)" : "(connecting...)"}
        </h2>
        {liveCounts ? (
          <div className="stat-grid">
            <div className="stat"><div className="num">{liveCounts.going}</div><div className="label">Going</div></div>
            <div className="stat"><div className="num">{liveCounts.maybe}</div><div className="label">Maybe</div></div>
            <div className="stat"><div className="num">{liveCounts.not_going}</div><div className="label">Not Going</div></div>
            <div className="stat"><div className="num">{liveCounts.available_seats}</div><div className="label">Seats Left</div></div>
          </div>
        ) : <div className="muted">Loading counts...</div>}
      </div>

      <div className="card">
        <h2>Announcements</h2>
        {announcements.length === 0 && <div className="muted">No announcements yet.</div>}
        {announcements.map((a, i) => (
          <div key={i} style={{ padding: "8px 0", borderBottom: "1px solid var(--border)" }}>
            <strong>{a.title}</strong><br /><span className="muted">{a.message}</span>
          </div>
        ))}
      </div>
    </div>
  );
}
