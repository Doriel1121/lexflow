import { useTranslation } from 'react-i18next';

export function LanguageSwitcher() {
  const { i18n } = useTranslation();
  const isHebrew = i18n.language === 'he';

  const toggle = () => {
    const next = isHebrew ? 'en' : 'he';
    i18n.changeLanguage(next);
  };

  return (
    <button
      onClick={toggle}
      className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg border border-slate-200 hover:bg-slate-50 transition-colors text-sm font-medium text-slate-600"
      title={isHebrew ? 'Switch to English' : 'עבור לעברית'}
      aria-label="Toggle language"
    >
      <span className="text-base leading-none">{isHebrew ? '🇮🇱' : '🇺🇸'}</span>
      <span className="text-xs font-semibold tracking-wide">{isHebrew ? 'עב' : 'EN'}</span>
    </button>
  );
}
