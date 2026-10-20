import { CheckCircle2, Clock3, CircleDashed, RotateCcw } from 'lucide-react';
import { statusLabels, type ReportStatus } from '../types';
const icons = { approved: CheckCircle2, submitted: Clock3, draft: CircleDashed, returned: RotateCcw };
export default function Status({ status }: { status: ReportStatus }) {
  const Icon = icons[status];
  return <span className={`status status-${status}`}><Icon size={12}/>{statusLabels[status]}</span>;
}
