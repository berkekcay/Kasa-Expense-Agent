// Words used on many pages: categories, sources, periods and everyday buttons.
import { defineMessages, translate } from "./i18n";

export const common = defineMessages({
  en: {
    save: "Save",
    saving: "Saving",
    cancel: "Cancel",
    delete: "Delete",
    edit: "Edit",
    close: "Close",
    add: "Add",
    loading: "Loading",
    tryAgain: "Try again",
    dismiss: "Dismiss",
    seeAll: "See all",
    open: "Open",
    today: "Today",
    month: "Month",
    allMonths: "All months",
    house: "house",
    total: "Total",
    other: "Other",
    uncategorised: "Uncategorised",
    // categories (backend keys)
    "cat.groceries": "Groceries",
    "cat.food": "Food",
    "cat.transport": "Transport",
    "cat.rent": "Rent",
    "cat.utilities": "Utilities",
    "cat.subscriptions": "Subscriptions",
    "cat.shopping": "Shopping",
    "cat.health": "Health",
    "cat.education": "Education",
    "cat.entertainment": "Entertainment",
    "cat.travel": "Travel",
    "cat.other": "Other",
    "cat.uncategorised": "Uncategorised",
    // expense sources
    "source.manual": "manual",
    "source.receipt": "receipt",
    "source.statement": "statement",
    "source.email": "email",
    // subscription periods
    "period.weekly": "weekly",
    "period.monthly": "monthly",
    "period.yearly": "yearly",
  },
  tr: {
    save: "Kaydet",
    saving: "Kaydediliyor",
    cancel: "Vazgeç",
    delete: "Sil",
    edit: "Düzenle",
    close: "Kapat",
    add: "Ekle",
    loading: "Yükleniyor",
    tryAgain: "Tekrar dene",
    dismiss: "Kapat",
    seeAll: "Tümü",
    open: "Aç",
    today: "Bugün",
    month: "Ay",
    allMonths: "Tüm aylar",
    house: "ev",
    total: "Toplam",
    other: "Diğer",
    uncategorised: "Kategorisiz",
    "cat.groceries": "Market",
    "cat.food": "Yemek",
    "cat.transport": "Ulaşım",
    "cat.rent": "Kira",
    "cat.utilities": "Faturalar",
    "cat.subscriptions": "Abonelikler",
    "cat.shopping": "Alışveriş",
    "cat.health": "Sağlık",
    "cat.education": "Eğitim",
    "cat.entertainment": "Eğlence",
    "cat.travel": "Seyahat",
    "cat.other": "Diğer",
    "cat.uncategorised": "Kategorisiz",
    "source.manual": "elle",
    "source.receipt": "fiş",
    "source.statement": "ekstre",
    "source.email": "e-posta",
    "period.weekly": "haftalık",
    "period.monthly": "aylık",
    "period.yearly": "yıllık",
  },
});

type Key = keyof (typeof common)["en"];

/** "groceries" -> "Groceries" / "Market". Unknown keys are capitalised as they are. */
export function categoryLabel(category: string | null | undefined): string {
  if (!category) return translate(common, "cat.uncategorised");
  const key = `cat.${category}` as Key;
  return key in common.en ? translate(common, key) : category[0].toUpperCase() + category.slice(1);
}

export function sourceLabel(source: string): string {
  const key = `source.${source}` as Key;
  return key in common.en ? translate(common, key) : source;
}

export function periodLabel(period: string): string {
  const key = `period.${period}` as Key;
  return key in common.en ? translate(common, key) : period;
}
