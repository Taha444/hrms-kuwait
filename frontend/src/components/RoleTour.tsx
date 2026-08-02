import { useEffect, useState } from "react";
import api from "../api";
import { useAuth } from "../auth";
import { useI18n } from "../i18n";
import TourDriver from "./TourDriver";
import { getTourForRole, tourKeyForRole } from "./tourScripts";

/**
 * R5 §3 — الغلاف الحيّ للجولة التعليمية:
 *  - بعد أول دخول: يستعلم /me/tours عن قائمة الجولات المكتملة
 *  - لو ما في سجل للـtourKey للدور الحالي → يشغّل TourDriver تلقائيًا
 *  - يستمع لحدث window `hrms:replay-tour` عشان زر "أعد جولة التعريف" في Topbar
 *  - عند Finish/Skip: POST /me/tours/{key}/complete (skipped flag يحفظ التمييز)
 */
export default function RoleTour() {
  const { user } = useAuth();
  const { lang } = useI18n();
  const [open, setOpen] = useState(false);
  const [checked, setChecked] = useState(false);

  const tourKey = user?.role ? tourKeyForRole(user.role) : "";
  const steps = user?.role ? getTourForRole(user.role, lang) : [];

  useEffect(() => {
    if (!user || !tourKey || steps.length === 0) return;
    // نتحقق من backend مرة واحدة عند التحميل
    api.get("/me/tours").then((r) => {
      const done = (r.data as any[]).some((t) => t.tour_key === tourKey);
      if (!done) setOpen(true);
      setChecked(true);
    }).catch(() => setChecked(true));
  }, [user?.id, tourKey]);

  // زر "أعد جولة التعريف" في Topbar يطلق هذا الحدث
  useEffect(() => {
    if (!user || !tourKey) return;
    const replay = () => {
      // نمسح السجل ثم نفتح الجولة من الخطوة الأولى
      api.delete(`/me/tours/${encodeURIComponent(tourKey)}`)
        .finally(() => setOpen(true));
    };
    window.addEventListener("hrms:replay-tour", replay);
    return () => window.removeEventListener("hrms:replay-tour", replay);
  }, [user?.id, tourKey]);

  const markComplete = (skipped: boolean, stepReached?: number) => {
    const body = new URLSearchParams();
    body.set("skipped", String(skipped));
    if (stepReached !== undefined) body.set("step_reached", String(stepReached));
    api.post(`/me/tours/${encodeURIComponent(tourKey)}/complete?${body.toString()}`)
      .catch(() => {});
    setOpen(false);
  };

  if (!checked || !user || steps.length === 0) return null;

  return (
    <TourDriver
      steps={steps}
      open={open}
      onComplete={() => markComplete(false)}
      onSkip={(stepReached) => markComplete(true, stepReached)}
    />
  );
}
