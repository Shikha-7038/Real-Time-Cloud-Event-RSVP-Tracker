import React, { useState } from "react";
import { useNavigate, Link } from "react-router-dom";
import { apiRequest, saveSession } from "../api";

export default function Login() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState(null);
  const navigate = useNavigate();

  async function handleSubmit(e) {
    e.preventDefault();
    setError(null);
    try {
      const { token, user } = await apiRequest("/login", { method: "POST", auth: false, body: { email, password } });
      saveSession(token, user);
      navigate(user.role === "organizer" ? "/organizer" : "/attendee");
    } catch (err) {
      setError(err.message);
    }
  }

  return (
    <div className="container narrow">
      <div className="card">
        <h1>Log In</h1>
        {error && <div className="error-box">{error}</div>}
        <form onSubmit={handleSubmit}>
          <label>Email</label>
          <input type="email" required value={email} onChange={(e) => setEmail(e.target.value)} />
          <label>Password</label>
          <input type="password" required value={password} onChange={(e) => setPassword(e.target.value)} />
          <button type="submit" style={{ width: "100%", marginTop: 16 }}>Log In</button>
        </form>
        <p className="muted" style={{ marginTop: 14 }}>No account? <Link to="/register">Register</Link></p>
      </div>
    </div>
  );
}
