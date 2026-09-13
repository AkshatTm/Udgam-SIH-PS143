import { redirect } from "next/navigation";

// /case/<id> with no stage → enter the flow at the first stage.
export default function CaseIndex({ params }: { params: { id: string } }) {
  redirect(`/case/${params.id}/detect`);
}
