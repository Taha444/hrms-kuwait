import { Component, type ErrorInfo, type ReactNode } from "react";

interface Props { children: ReactNode }
interface State { error: Error | null }

// شبكة أمان عامة (QA-P0-WF-02): أي خطأ غير متوقع أثناء العرض (مثل محاولة عرض كائن استجابة
// خطأ كنص) كان يُسقط التطبيق كله بشاشة بيضاء بلا أي رسالة. تلتقط React Error Boundary هذا
// الخطأ وتعرض بديًلا وديًا مع زر استعادة، بدل ترك المستخدم أمام صفحة فارغة.
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null };

  static getDerivedStateFromError(error: Error): State {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Unhandled UI error:", error, info.componentStack);
  }

  render() {
    if (this.state.error) {
      return (
        <div style={{ padding: 40, textAlign: "center" }}>
          <h2>حدث خطأ غير متوقع / Something went wrong</h2>
          <p className="muted">
            برجاء إعادة تحميل الصفحة. إن تكرر الخطأ يرجى إبلاغ الدعم الفني.
            <br />Please reload the page. If this keeps happening, contact support.
          </p>
          <button onClick={() => { this.setState({ error: null }); window.location.assign("/"); }}>
            العودة للصفحة الرئيسية / Back to Home
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
