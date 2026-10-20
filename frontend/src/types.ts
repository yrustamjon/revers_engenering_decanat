export type Role = 'employee' | 'reviewer' | 'administrator';
export type Page = 'dashboard' | 'portfolio' | 'reports' | 'plan' | 'profile' | 'templates' | 'archive' | 'review' | 'administration';
export interface User { id: number; name: string; email: string; role: Role; initials: string; is_demo?: boolean }
export interface Profile { id: number; full_name: string; email: string; phone: string; department: string; faculty: string; position: string; degree: string; bio: string; employee_id: string; initials: string; experience_years: number; employment_type: string }
export interface Attachment { id: number; name: string; url: string; size: number }
export type ActivityCategory = 'article' | 'conference' | 'certificate' | 'teaching' | 'project';
export interface Activity { id: number; title: string; category: ActivityCategory; date: string; description: string; link: string; status: 'draft' | 'verified'; attachment: Attachment | null; created_at: string; owner_name: string; owner_id: number }
export interface History { id: number; action: string; actor_name: string; comment: string; created_at: string }
export type ReportType = 'scientific' | 'annual' | 'teaching' | 'qualification';
export type ReportStatus = 'draft' | 'submitted' | 'returned' | 'approved';
export interface Report { id: number; title: string; type: ReportType; period: string; status: ReportStatus; activity_ids: number[]; comment: string; due_date: string | null; submitted_at: string | null; created_at: string; updated_at: string; owner_name: string; owner_id: number; history: History[]; template_version?: string; template_snapshot?: {id:string;title:string;version:string;fields:string[];form_schema?:FormField[]}; extra_data?:Record<string,string|number> }
export interface WorkItem { id: number; title: string; category: string; target: number; completed: number; due_date: string }
export interface Notification { id: number; title: string; message: string; read: boolean; created_at: string; report_id: number | null }
export interface FormField { key:string;label:string;type:'text'|'textarea'|'number'|'date'|'url';required:boolean }
export interface Template { id: string; title: string; description: string; type: ReportType; version: string; fields: string[]; icon: string; is_active?: boolean; form_schema?:FormField[] }
export interface Workspace { user: User; profile: Profile; activities: Activity[]; reports: Report[]; work_items: WorkItem[]; notifications: Notification[]; templates: Template[] }
export interface PageProps { workspace: Workspace; onRefresh: () => Promise<void>; toast: (message: string) => void }
export const categoryLabels: Record<ActivityCategory, string> = { article: 'Ilmiy maqola', conference: 'Konferensiya', certificate: 'Sertifikat', teaching: 'Uslubiy ish', project: 'Loyiha' };
export const reportTypeLabels: Record<ReportType, string> = { scientific: 'Ilmiy faoliyat', annual: 'Yillik hisobot', teaching: 'O‘quv-uslubiy', qualification: 'Malaka oshirish' };
export const statusLabels: Record<ReportStatus, string> = { draft: 'Qoralama', submitted: 'Tekshirilmoqda', returned: 'Tuzatish kerak', approved: 'Tasdiqlangan' };
