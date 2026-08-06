import { redirect } from "next/navigation";

export default function ProductionRedirectPage() {
  redirect(process.env.NEXT_PUBLIC_ERPNEXT_URL || "https://erp.124.223.87.161.nip.io");
}
