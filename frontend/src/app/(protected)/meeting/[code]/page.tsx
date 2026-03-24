'use client';

import { use } from 'react';
import MeetingPage from './MeetingPage';

export default function MeetingRoute({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = use(params);
  return <MeetingPage code={code} />;
}
