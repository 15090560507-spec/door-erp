import { redirect } from "next/navigation";

export default function ProductionRedirectPage() {
  redirect(process.env.NEXT_PUBLIC_ERPNEXT_URL || "https://124.223.87.161:8443");
}
