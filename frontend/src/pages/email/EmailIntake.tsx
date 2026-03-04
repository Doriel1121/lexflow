import { EmailClient } from '../../components/email/EmailClient';

export default function EmailIntake() {
  return (
    <div className="h-full flex flex-col">
       <div className="mb-6">
        <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">Email Intake</h1>
        <p className="text-muted-foreground">Process incoming legal correspondence and documents.</p>
      </div>
      <EmailClient />
    </div>
  );
}
