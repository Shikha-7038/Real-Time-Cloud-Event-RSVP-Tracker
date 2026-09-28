import React, { useState } from "react";
import { Routes, Route, Link, useNavigate } from "react-router-dom";
import { getUser, clearSession } from "./api";

import Home from "./pages/Home.jsx";
import Login from "./pages/Login.jsx";
import Register from "./pages/Register.jsx";
import OrganizerDashboard from "./pages/OrganizerDashboard.jsx";
import AttendeeDashboard from "./pages/AttendeeDashboard.jsx";
import EventDetail from "./pages/EventDetail.jsx";

function Navbar() {
  const [user, setUser] = useState(getUser());
  const navigate = useNavigate();

  function logout() {
    clearSession();
    setUser(null);
    navigate("/");
  }

  return (
    <nav className="navbar">
      <Link className="brand" to="/">Cloud Event & RSVP Tracker</Link>
      <div className="links">
        {user ? (
          <>
            <Link to={user.role === "organizer" ? "/organizer" : "/attendee"}>Dashboard</Link>
            <a href="#" onClick={(e) => { e.preventDefault(); logout(); }}>Logout ({user.name})</a>
          </>
        ) : (
          <>
            <Link to="/login">Login</Link>
            <Link to="/register">Register</Link>
          </>
        )}
      </div>
    </nav>
  );
}

export default function App() {
  return (
    <>
      <Navbar />
      <Routes>
        <Route path="/" element={<Home />} />
        <Route path="/login" element={<Login />} />
        <Route path="/register" element={<Register />} />
        <Route path="/organizer" element={<OrganizerDashboard />} />
        <Route path="/attendee" element={<AttendeeDashboard />} />
        <Route path="/events/:eventId" element={<EventDetail />} />
      </Routes>
    </>
  );
}
