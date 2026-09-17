import { Component, type ErrorInfo, type ReactNode } from "react";
import { tr } from "../i18n";

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
          <h2>{tr("err_boundary_title")}</h2>
          <p className="muted">
            {tr("err_boundary_body")}
          </p>
          <button onClick={() => { this.setState({ error: null }); window.location.assign("/"); }}>
            {tr("err_boundary_home")}
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}
