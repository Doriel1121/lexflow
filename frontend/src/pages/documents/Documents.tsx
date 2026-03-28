import { useTranslation } from "react-i18next";
import { DocumentList } from "../../components/documents/DocumentList";

export default function Documents() {
  const { t } = useTranslation();
  return (
    <div className="h-full flex flex-col">
      <div className="mb-6">
        <h1 className="text-3xl font-serif font-bold text-slate-800 tracking-tight">
          {t("documents.title")}
        </h1>
        <p className="text-muted-foreground">
          Manage, search, and analyze your legal files.
        </p>
      </div>
      <DocumentList />
    </div>
  );
}
