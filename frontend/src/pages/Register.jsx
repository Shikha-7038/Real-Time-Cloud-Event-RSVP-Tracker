import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { apiRequest, saveSession } from "../api";

export default function Register() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("attendee");
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    try {
      const { token, user } = await apiRequest("/register", {
        method: "POST", auth: false, body: { name, email, password, role },
      });
      saveSession(token, user);
      navigate(user.role === "organizer" ? "/organizer" : "/attendee");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="container narrow">
      <div className="card">
        <h1>Create an Account</h1>
        {error && <div className="error-box">{error}</div>}
        <form onSubmit={handleSubmit}>
          <label>Full Name</label>
          <input type="text" required value={name} onChange={(e) => setName(e.target.value)} />
          <label>Email</label>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <label>Password (min 6 chars)</label>
          <input type="password" required minLength={6} value={password} onChange={(e) => setPassword(e.target.value)} />
          <label>I am registering as</label>
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="attendee">Attendee</option>
            <option value="organizer">Organizer</option>
          </select>
          <button type="submit" style={{ width: "100%", marginTop: 16 }}>Register</button>
        </form>
        <p className="muted" style={{ marginTop: 14 }}>Already have an account? <Link to="/login">Log in</Link></p>
      </div>
    </div>
  );
}
