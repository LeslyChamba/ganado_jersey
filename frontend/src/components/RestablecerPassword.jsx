import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Lock, Eye, EyeOff, CheckCircle, AlertCircle } from "lucide-react";

export default function RestablecerPassword() {
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const navigate = useNavigate();

  const [password, setPassword]           = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [showPwd,  setShowPwd]            = useState(false);
  const [showConf, setShowConf]           = useState(false);
  const [error,    setError]              = useState("");
  const [cargando, setCargando]           = useState(false);
  const [exito,    setExito]              = useState(false);

  /* ── Fortaleza ── */
  function calcStrength(p) {
    let s = 0;
    if (p.length >= 8)          s++;
    if (/[A-Z]/.test(p))        s++;
    if (/[0-9]/.test(p))        s++;
    if (/[^A-Za-z0-9]/.test(p)) s++;
    return s;
  }
  const strength = calcStrength(password);
  const strengthLabels = ["", "Débil", "Regular", "Buena", "Fuerte"];
  const strengthColors = ["", "#e74c3c", "#f39c12", "#27ae60", "#1B4332"];

  /* ── Submit ── */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");

    if (password.length < 8) {
      setError("La contraseña debe tener al menos 8 caracteres.");
      return;
    }
    if (password !== confirmPassword) {
      setError("Las contraseñas no coinciden.");
      return;
    }

    setCargando(true);
    try {
      const res = await fetch("http://localhost:8000/api/v1/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, nueva_password: password }),
      });

      const datos = await res.json();

      if (res.ok) {
        setExito(true);
        setTimeout(() => navigate("/login"), 3000);
      } else {
        setError(datos.detail || "El enlace es inválido o ya expiró.");
      }
    } catch {
      setError("Error de conexión con el servidor.");
    } finally {
      setCargando(false);
    }
  };

  /* ── Token ausente ── */
  if (!token) {
    return (
      <div style={s.page}>
        <div style={{ ...s.card, textAlign: "center", padding: "40px" }}>
          <AlertCircle size={48} color="#e74c3c" style={{ marginBottom: 12 }} />
          <h2 style={s.title}>Enlace inválido</h2>
          <p style={s.sub}>No se encontró el token de seguridad en la URL.</p>
          <button style={s.btn} onClick={() => navigate("/login")}>
            Volver al inicio de sesión
          </button>
        </div>
      </div>
    );
  }

  /* ── Éxito ── */
  if (exito) {
    return (
      <div style={s.page}>
        <div style={{ ...s.card, textAlign: "center", padding: "48px 40px" }}>
          <CheckCircle size={56} color="#27ae60" style={{ marginBottom: 14 }} />
          <h2 style={s.title}>¡Contraseña actualizada!</h2>
          <p style={s.sub}>Redirigiendo al inicio de sesión…</p>
          <div style={s.progressBar}>
            <div style={s.progressFill} />
          </div>
        </div>
      </div>
    );
  }

  /* ── Formulario ── */
  return (
    <div style={s.page}>
      <div style={s.card}>

        {/* Encabezado */}
        <div style={{ textAlign: "center", marginBottom: 28 }}>
          <h2 style={s.title}>Nueva Contraseña</h2>
          <p style={s.sub}>INGRESA TUS NUEVAS CREDENCIALES</p>
        </div>

        <form onSubmit={handleSubmit}>

          {/* Campo contraseña */}
          <div style={s.field}>
            <label style={s.label}>Nueva Contraseña</label>
            <div style={s.inputWrap}>
              <Lock size={16} style={s.icon} />
              <input
                type={showPwd ? "text" : "password"}
                required
                style={s.input}
                value={password}
                placeholder="Mínimo 8 caracteres"
                onChange={e => setPassword(e.target.value)}
                autoComplete="new-password"
              />
              <button
                type="button"
                style={s.eyeBtn}
                onClick={() => setShowPwd(v => !v)}
                aria-label="Mostrar/ocultar"
              >
                {showPwd ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>

            {/* Barra de fortaleza */}
            {password && (
              <div style={{ marginTop: 8 }}>
                <div style={{ display: "flex", gap: 4, marginBottom: 4 }}>
                  {[1,2,3,4].map(i => (
                    <div key={i} style={{
                      flex: 1, height: 4, borderRadius: 4,
                      background: strength >= i ? strengthColors[strength] : "#e5e7eb",
                      transition: "background .3s"
                    }} />
                  ))}
                </div>
                <span style={{ fontSize: 11, color: "#6b7280" }}>
                  Fortaleza:{" "}
                  <strong style={{ color: strengthColors[strength] }}>
                    {strengthLabels[strength]}
                  </strong>
                </span>
              </div>
            )}
          </div>

          {/* Campo confirmar */}
          <div style={s.field}>
            <label style={s.label}>Confirmar Contraseña</label>
            <div style={s.inputWrap}>
              <Lock size={16} style={s.icon} />
              <input
                type={showConf ? "text" : "password"}
                required
                style={{
                  ...s.input,
                  borderColor: confirmPassword && password !== confirmPassword
                    ? "#e74c3c" : undefined
                }}
                value={confirmPassword}
                placeholder="Repite la contraseña"
                onChange={e => setConfirmPassword(e.target.value)}
                autoComplete="new-password"
              />
              <button
                type="button"
                style={s.eyeBtn}
                onClick={() => setShowConf(v => !v)}
                aria-label="Mostrar/ocultar"
              >
                {showConf ? <EyeOff size={16} /> : <Eye size={16} />}
              </button>
            </div>
            {confirmPassword && password !== confirmPassword && (
              <p style={{ fontSize: 12, color: "#e74c3c", marginTop: 4 }}>
                Las contraseñas no coinciden.
              </p>
            )}
          </div>

          {/* Error de API */}
          {error && (
            <div style={s.errorBox}>
              <AlertCircle size={14} style={{ flexShrink: 0 }} />
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={cargando}
            style={{
              ...s.btn,
              opacity: cargando ? .6 : 1,
              cursor: cargando ? "not-allowed" : "pointer"
            }}
          >
            {cargando ? "GUARDANDO…" : "GUARDAR CONTRASEÑA"}
          </button>
        </form>

        <button
          style={s.backBtn}
          onClick={() => navigate("/login")}
        >
          ← Volver al inicio de sesión
        </button>
      </div>
    </div>
  );
}

/* ── Estilos en objeto (sin dependencia de F ni Tailwind obligatorio) ──────── */
const s = {
  page: {
    minHeight: "100vh",
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "#F0FBF6",
    padding: "24px",
    fontFamily: "'DM Sans', sans-serif",
  },
  card: {
    background: "#ffffff",
    borderRadius: "2rem",
    boxShadow: "0 20px 50px rgba(8,28,17,.07)",
    border: "1px solid #d1fae5",
    width: "100%",
    maxWidth: 420,
    padding: "40px",
  },
  logoWrap: {
    display: "inline-flex",
    alignItems: "center",
    justifyContent: "center",
    width: 56, height: 56,
    background: "linear-gradient(135deg,#52b788,#1B4332)",
    borderRadius: 16,
    fontSize: 28,
    marginBottom: 16,
  },
  title: {
    fontSize: 26,
    fontWeight: 800,
    color: "#081C11",
    marginBottom: 4,
    fontFamily: "inherit",
  },
  sub: {
    fontSize: 11,
    color: "#2A5C3A",
    textTransform: "uppercase",
    letterSpacing: ".08em",
    fontWeight: 600,
    marginBottom: 0,
  },
  field: { marginBottom: 18 },
  label: {
    display: "block",
    fontSize: 11,
    fontWeight: 700,
    color: "#2A5C3A",
    textTransform: "uppercase",
    letterSpacing: ".06em",
    marginBottom: 6,
  },
  inputWrap: { position: "relative" },
  icon: {
    position: "absolute",
    left: 12, top: "50%",
    transform: "translateY(-50%)",
    color: "#9ca3af",
    pointerEvents: "none",
  },
  input: {
    width: "100%",
    padding: "12px 40px 12px 36px",
    borderRadius: 12,
    border: "1.5px solid #d1fae5",
    background: "#F9FDFB",
    fontSize: 14,
    fontFamily: "inherit",
    color: "#081C11",
    outline: "none",
    boxSizing: "border-box",
    transition: "border .2s",
  },
  eyeBtn: {
    position: "absolute",
    right: 12, top: "50%",
    transform: "translateY(-50%)",
    background: "none",
    border: "none",
    cursor: "pointer",
    color: "#9ca3af",
    display: "flex",
    alignItems: "center",
    padding: 2,
  },
  errorBox: {
    display: "flex",
    alignItems: "center",
    gap: 8,
    background: "#fff5f5",
    border: "1.5px solid #fca5a5",
    borderRadius: 10,
    padding: "10px 14px",
    fontSize: 13,
    color: "#c0392b",
    marginBottom: 14,
  },
  btn: {
    width: "100%",
    padding: "14px",
    borderRadius: 12,
    border: "none",
    background: "#081C11",
    color: "#fff",
    fontFamily: "monospace",
    fontSize: 13,
    fontWeight: 700,
    letterSpacing: ".18em",
    textTransform: "uppercase",
    cursor: "pointer",
    transition: "background .2s",
    marginTop: 4,
  },
  backBtn: {
    display: "block",
    width: "100%",
    marginTop: 18,
    background: "none",
    border: "none",
    color: "#2A5C3A",
    fontSize: 13,
    fontWeight: 500,
    cursor: "pointer",
    textAlign: "center",
    textDecoration: "underline",
  },
  progressBar: {
    height: 4,
    background: "#e5e7eb",
    borderRadius: 4,
    marginTop: 16,
    overflow: "hidden",
  },
  progressFill: {
    height: "100%",
    width: "100%",
    background: "linear-gradient(90deg,#52b788,#1B4332)",
    borderRadius: 4,
    animation: "progress 3s linear forwards",
  },
};