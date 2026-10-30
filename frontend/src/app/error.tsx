"use client";

export default function GlobalError({ reset }: { error: Error & { digest?: string }; reset: () => void }) {
  return (
    <div className="container page-section narrow-state">
      <div className="state-panel state-error" role="alert"><span className="state-icon">!</span><div><h1>Giao diện gặp sự cố</h1><p>Hãy thử tải lại phần nội dung này.</p><button className="button button-primary" type="button" onClick={reset}>Thử lại</button></div></div>
    </div>
  );
}
