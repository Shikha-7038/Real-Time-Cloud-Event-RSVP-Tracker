import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { apiRequest, getUser, fmtDate } from "../api";

export default function OrganizerDashboard() {
  const navigate = useNavigate();
  const user = getUser();
  const [myEvents, setMyEvents] = useState([]);
  const [analytics, setAnalytics] = useState({});
  const [createErr, setCreateErr] = useState(null);
  const [form, setForm] = useState({
    event_name: "", description: "", event_date: "", start_time: "", venue: "", maximum_capacity: "",
  });

  useEffect(() => { if (!user) navigate("/login"); }, []);

  const loadMyEvents = useCallback(async () => {
    try {
      const all = await apiRequest("/events", { auth: false });
      const mine = all.filter((ev) => ev.organizer_id === user.user_id);
      setMyEvents(mine);
      const analyticsMap = {};
      await Promise.all(mine.map(async (ev) => {
        try { analyticsMap[ev.event_id] = await apiRequest(`/events/${ev.event_id}/analytics`); }
        catch (e) { /* ignore */ }
      }));
      setAnalytics(analyticsMap);
    } catch (e) { /* ignore */ }
  }, [user]);

  useEffect(() => {
    if (!user) return;
    loadMyEvents();
    // Organizer dashboard covers MANY events at once, so a per-event
    // WebSocket for each card isn't practical here - a short poll keeps
    // the summary list fresh. The single-event page (EventDetail) is
    // pure WebSocket push with zero polling; see that file.
    const interval = setInterval(loadMyEvents, 5000);
    return () => clearInterval(interval);
  }, [loadMyEvents]);

  async function handleCreate(e) {
    e.preventDefault();
    setCreateErr(null);
    try {
      await apiRequest("/events", {
        method: "POST",
        body: { ...form, maximum_capacity: parseInt(form.maximum_capacity, 10) },
      });
      setForm({ event_name: "", description: "", event_date: "", start_time: "", venue: "", maximum_capacity: "" });
      loadMyEvents();
    } catch (err) {
      setCreateErr(err.message);
    }
  }

  async function announce(eventId) {
    const title = prompt("Announcement title (e.g. Venue Updated):");
    if (!title) return;
    const message = prompt("Message:");
    if (!message) return;
    try {
      await apiRequest(`/events/${eventId}/announcements`, { method: "POST", body: { title, message } });
      alert("Announcement sent to all RSVPed attendees.");
    } catch (err) {
      alert(err.message);
    }
  }

  async function cancelEvent(eventId) {
    if (!confirm("Cancel this event? All attendees will be notified.")) return;
    try {
      await apiRequest(`/events/${eventId}`, { method: "DELETE" });
      loadMyEvents();
    } catch (err) {
      alert(err.message);
    }
  }

  if (!user) return null;

  return (
    <div className="container">
      <h1>Organizer Dashboard</h1>

      <div className="card">
        <h2>Create Event</h2>
        {createErr && <div className="error-box">{createErr}</div>}
        <form onSubmit={handleCreate}>
          <label>Event Name</label>
          <input required value={form.event_name} onChange={(e) => setForm({ ...form, event_name: e.target.value })} />
          <label>Description</label>
          <textarea value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          <label>Date</label>
          <input type="date" required value={form.event_date} onChange={(e) => setForm({ ...form, event_date: e.target.value })} />
          <label>Start Time</label>
          <input type="time" required value={form.start_time} onChange={(e) => setForm({ ...form, start_time: e.target.value })} />
          <label>Venue / Online Link</label>
          <input value={form.venue} onChange={(e) => setForm({ ...form, venue: e.target.value })} />
          <label>Maximum Capacity</label>
          <input type="number" min="1" required value={form.maximum_capacity} onChange={(e) => setForm({ ...form, maximum_capacity: e.target.value })} />
          <button type="submit" style={{ marginTop: 14 }}>Create Event</button>
        </form>
      </div>

      <h2>Your Events</h2>
      {myEvents.length === 0 && <div className="card muted">You haven't created any events yet.</div>}
      {myEvents.map((ev) => {
        const a = analytics[ev.event_id];
        return (
          <div className="card" key={ev.event_id}>
            <div className="event-row">
              <div>
                <h2 style={{ marginBottom: 4 }}>{ev.event_name}</h2>
                <div className="muted">{fmtDate(ev.event_date)} · {ev.start_time} · {ev.venue || "TBA"}</div>
              </div>
              <span className={`badge ${ev.status.toLowerCase()}`}>{ev.status}</span>
            </div>
            {a && (
              <div className="stat-grid" style={{ marginTop: 10 }}>
                <div className="stat"><div className="num">{a.going}</div><div className="label">Going</div></div>
                <div className="stat"><div className="num">{a.maybe}</div><div className="label">Maybe</div></div>
                <div className="stat"><div className="num">{a.not_going}</div><div className="label">Not Going</div></div>
                <div className="stat"><div className="num">{a.waitlist_size}</div><div className="label">Waitlisted</div></div>
                <div className="stat"><div className="num">{a.available_seats}</div><div className="label">Seats Left</div></div>
                <div className="stat"><div className="num">{a.capacity_utilization_pct}%</div><div className="label">Utilization</div></div>
              </div>
            )}
            <div style={{ marginTop: 12 }}>
              <button className="secondary" onClick={() => announce(ev.event_id)}>Post Announcement</button>{" "}
              <button className="danger" onClick={() => cancelEvent(ev.event_id)}>Cancel Event</button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
