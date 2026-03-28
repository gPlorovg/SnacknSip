import EventLogin from "@/components/event-login";

export default async function Page({
  params,
}: {
  params: Promise<{ event_code: string }>;
}) {
  const { event_code } = await params;

  return <EventLogin initialEventCode={event_code} />;
}
