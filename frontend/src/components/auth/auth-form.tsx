"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useState } from "react";
import { useAuth } from "@/features/auth/auth-provider";
import { asApiError, type ApiError } from "@/lib/api/api-error";

export function AuthForm({ mode }: { mode: "login" | "register" }) {
  const router = useRouter();
  const { signIn, signUp } = useAuth();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<ApiError | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const isRegister = mode === "register";

  function fillDemoAccount() {
    setEmail("user0@gmaill.com");
    setPassword("123456789");
    setError(null);
  }

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSubmitting(true);
    try {
      if (isRegister) await signUp({ email, password });
      else await signIn({ email, password });
      router.push("/");
    } catch (caught) {
      setError(asApiError(caught));
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="auth-shell">
      <section className="auth-form-panel">
        <Link className="brand auth-brand" href="/">
          <span className="brand-mark" aria-hidden="true">LM</span>
          <span><strong>Lumi</strong><small>image market</small></span>
        </Link>
        <div className="auth-heading">
          <p className="eyebrow">{isRegister ? "Gia nhập Lumi" : "Chào mừng trở lại"}</p>
          <h1>{isRegister ? "Tạo tài khoản của bạn" : "Đăng nhập tài khoản"}</h1>
          <p>{isRegister ? "Đăng ký để lưu lại trải nghiệm mua sắm của bạn trong phiên hiện tại." : "Tiếp tục khám phá những sản phẩm hợp với phong cách của bạn."}</p>
        </div>
        <form className="auth-form" onSubmit={submit}>
          <label htmlFor="auth-email">Email</label>
          <input id="auth-email" type="email" autoComplete="email" value={email} onChange={(event) => setEmail(event.target.value)} required placeholder="ban@example.com" />
          <label htmlFor="auth-password">Mật khẩu</label>
          <input id="auth-password" type="password" autoComplete={isRegister ? "new-password" : "current-password"} value={password} onChange={(event) => setPassword(event.target.value)} required minLength={isRegister ? 8 : 1} maxLength={128} aria-describedby={isRegister ? "password-help" : undefined} />
          {!isRegister ? (
            <button className="button button-secondary button-small demo-account" type="button" onClick={fillDemoAccount} aria-label="Điền tài khoản demo user0@gmaill.com">
              user0@gmaill.com
            </button>
          ) : null}
          {isRegister ? <small id="password-help" className="field-help">Mật khẩu cần có tối thiểu 8 ký tự.</small> : null}
          {error ? (
            <div className="inline-error" role="alert">
              <strong>{error.message}</strong>
              {Object.entries(error.fieldErrors).map(([field, message]) => <span key={field}>{field}: {message}</span>)}
              {error.requestId ? <small>Mã yêu cầu: {error.requestId}</small> : null}
            </div>
          ) : null}
          <button className="button button-primary button-large button-block" type="submit" disabled={submitting}>
            {submitting ? "Đang gửi…" : isRegister ? "Đăng ký" : "Đăng nhập"}
          </button>
        </form>
        <p className="auth-switch">
          {isRegister ? "Đã có tài khoản?" : "Chưa có tài khoản?"}{" "}
          <Link href={isRegister ? "/login" : "/register"}>{isRegister ? "Đăng nhập" : "Đăng ký"}</Link>
        </p>
      </section>
      <aside className="auth-aside">
        <div className="auth-aside-content">
          <span className="auth-orbit" aria-hidden="true">⌁</span>
          <p className="eyebrow">Lumi membership</p>
          <h2>Một tài khoản, nhiều cảm hứng.</h2>
          <p>Khám phá catalog, tìm món đồ tương tự từ ảnh và quay lại hành trình mua sắm bất cứ lúc nào trong phiên.</p>
          <ul><li>Đăng nhập đơn giản</li><li>Trải nghiệm riêng tư</li><li>Chủ động đăng xuất khi cần</li></ul>
        </div>
      </aside>
    </div>
  );
}
