import React, { useState } from "react";
import { Link, useNavigate, Navigate } from "react-router-dom";
import { useAuth } from "@/lib/auth";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Mail, Eye, EyeOff } from "lucide-react";
import { ThemeToggle } from "@/lib/theme";

export default function AuthPage({ mode = "login" }) {
  const isLogin = mode === "login";
  const { user, login, register } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [name, setName] = useState("");
  const [showPassword, setShowPassword] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");

  if (user && typeof user === "object") return <Navigate to="/dashboard" replace />;

  const submit = async (e) => {
    e.preventDefault();
    setError("");
    setLoading(true);
    const res = isLogin
      ? await login(email, password)
      : await register(email, password, name);
    setLoading(false);
    if (res.ok) navigate("/dashboard");
    else setError(res.error);
  };

  const bgLight = "https://images.unsplash.com/photo-1595411425732-e69c1abe2763?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600";
  const bgDark = "https://images.unsplash.com/photo-1454117096348-e4abbeba002c?crop=entropy&cs=srgb&fm=jpg&q=85&w=1600";

  return (
    <div className="min-h-screen flex">
      {/* Left form */}
      <div className="flex-1 flex flex-col">
        <div className="h-14 px-6 flex items-center justify-between border-b border-border">
          <Link to="/" className="flex items-center gap-2">
            <div className="h-7 w-7 rounded-sm bg-foreground text-background grid place-items-center">
              <Mail className="h-4 w-4" />
            </div>
            <span className="text-sm font-semibold tracking-tight">Relayd</span>
          </Link>
          <ThemeToggle />
        </div>
        <div className="flex-1 grid place-items-center px-6 py-10">
          <form onSubmit={submit} className="w-full max-w-sm space-y-6" data-testid={isLogin ? "login-form" : "register-form"}>
            <div>
              <div className="text-xs uppercase tracking-[0.2em] font-semibold text-muted-foreground mb-2">
                {isLogin ? "Sign in" : "Create account"}
              </div>
              <h1 className="text-3xl font-semibold tracking-tight">
                {isLogin ? "Welcome back" : "Get started"}
              </h1>
              <p className="mt-2 text-sm text-muted-foreground">
                {isLogin
                  ? "Sign in to your email orchestration control panel."
                  : "Spin up your self-hostable email infrastructure in minutes."}
              </p>
            </div>

            {!isLogin && (
              <div className="space-y-2">
                <Label htmlFor="name">Name</Label>
                <Input
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Jane Operator"
                  data-testid="register-name-input"
                />
              </div>
            )}
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input
                id="email"
                type="email"
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@domain.com"
                required
                data-testid={isLogin ? "login-email-input" : "register-email-input"}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="••••••••"
                  required
                  minLength={6}
                  className="pr-10"
                  data-testid={isLogin ? "login-password-input" : "register-password-input"}
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(v => !v)}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground transition-colors"
                  tabIndex={-1}
                  aria-label={showPassword ? "Hide password" : "Show password"}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {error && (
              <div className="text-sm text-destructive border border-destructive/30 bg-destructive/5 px-3 py-2 rounded-sm" data-testid="auth-error">
                {error}
              </div>
            )}

            <Button
              type="submit"
              disabled={loading}
              className="w-full"
              data-testid={isLogin ? "login-submit-button" : "register-submit-button"}
            >
              {loading ? "Please wait…" : isLogin ? "Sign in" : "Create account"}
            </Button>

            <div className="text-sm text-muted-foreground text-center">
              {isLogin && (
                <>Signups are currently disabled by the administrator.</>
              )}
            </div>
          </form>
        </div>
      </div>

      {/* Right pane */}
      <div className="hidden lg:block w-[42%] relative border-l border-border overflow-hidden">
        <img
          src={bgDark}
          alt=""
          className="absolute inset-0 h-full w-full object-cover opacity-[0.18] hidden dark:block"
        />
        <img
          src={bgLight}
          alt=""
          className="absolute inset-0 h-full w-full object-cover opacity-[0.2] dark:hidden"
        />
        <div className="absolute inset-0 bg-background/40" />
        <div className="relative h-full p-10 flex flex-col justify-between">
          <div className="text-[11px] uppercase tracking-[0.22em] text-muted-foreground">
            v0.1 — self-hostable
          </div>
          <div className="space-y-5 max-w-md">
            <div className="text-xs uppercase tracking-[0.22em] text-muted-foreground">A modern control plane for email</div>
            <h2 className="text-3xl font-semibold tracking-tight leading-snug">
              Domains. DKIM. Relays. Deliverability — all in one terminal-grade dashboard.
            </h2>
            <ul className="space-y-2 text-sm text-muted-foreground">
              <li>• Multi-domain SPF / DKIM / DMARC / MX generation</li>
              <li>• Live DNS verification with deliverability scoring</li>
              <li>• Pluggable outbound relays (Resend, SMTP, SES…)</li>
              <li>• Queue-based send with retries and failover</li>
            </ul>
          </div>
          <div className="text-[11px] tracking-wider text-muted-foreground font-mono">
            built for developers, indie hackers & agencies.
          </div>
        </div>
      </div>
    </div>
  );
}
