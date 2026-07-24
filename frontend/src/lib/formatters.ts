import i18n from "./i18n";

export const getDateLocale = () => (i18n.language === "he" ? "he-IL" : "en-US");

export const formatDate = (
  value: string | Date | null | undefined,
  options: Intl.DateTimeFormatOptions = { year: "numeric", month: "short", day: "numeric" },
) => {
  if (!value) return "—";
  const date = value instanceof Date ? value : new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return date.toLocaleDateString(getDateLocale(), options);
};
