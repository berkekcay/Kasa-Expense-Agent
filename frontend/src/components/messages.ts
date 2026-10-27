// Labels for the shared components (ui, Toast, pickers, charts).
import { defineMessages } from "@/lib/i18n";

const lower = (v: string | number) => String(v).toLowerCase();

export const uiMessages = defineMessages({
  en: {
    "tone.info": "Note",
    "tone.success": "Done",
    "tone.warning": "Warning",
    "tone.error": "Error",
    dismissMessage: "Dismiss message",
  },
  tr: {
    "tone.info": "Bilgi",
    "tone.success": "Tamamlandı",
    "tone.warning": "Uyarı",
    "tone.error": "Hata",
    dismissMessage: "Mesajı kapat",
  },
});

export const pickerMessages = defineMessages({
  en: {
    previousMonth: "Previous month",
    nextMonth: "Next month",
    previousYear: "Previous year",
    nextYear: "Next year",
    current: "{label}: {month} {year}",
    pickMonth: ({ label }) => `Pick a ${lower(label)}`,
    pickDate: ({ label }) => `Pick ${lower(label)}`,
    clear: ({ label }) => `Clear ${lower(label)}`,
    placeholder: "Pick a date",
    // Monday first, space separated
    weekdays: "Mo Tu We Th Fr Sa Su",
  },
  tr: {
    previousMonth: "Önceki ay",
    nextMonth: "Sonraki ay",
    previousYear: "Önceki yıl",
    nextYear: "Sonraki yıl",
    current: "{label}: {month} {year}",
    pickMonth: ({ label }) => `${label} seç`,
    pickDate: ({ label }) => `${label} seç`,
    clear: ({ label }) => `${label} alanını temizle`,
    placeholder: "Tarih seç",
    weekdays: "Pzt Sal Çar Per Cum Cmt Paz",
  },
});

export const chartMessages = defineMessages({
  en: {
    spendingByCategory: "Spending by category",
    dayRunning: "Day {day}, running total",
    paceLabel: "Running total, {month} against {previous}",
    lastSixMonths: "Spending in the last six months",
    nothingSpent: "Nothing spent",
    // Sunday first, space separated (ECharts nameMap)
    weekdaysSundayFirst: "Sun Mon Tue Wed Thu Fri Sat",
    perDay: "Spending per day this month",
    moreThanLastMonth: "{category}, more than last month",
    lessThanLastMonth: "{category}, less than last month",
    sameEveryCategory: "Same as last month in every category.",
    moreLegend: "More than last month",
    lessLegend: "Less",
    changeLabel: "Change per category against last month",
    onTrack: "On track",
    closeToLimit: "Close to limit",
    overLimit: "Over limit",
    overall: "Overall",
    budgetUsed: "{name} budget used",
    usedText: "{pct}% used, {level}",
    alertAt: "Alert at {pct}%",
    of: "of",
    left: "left",
    over: "over",
  },
  tr: {
    spendingByCategory: "Kategorilere göre harcama",
    dayRunning: "{day}. gün, biriken toplam",
    paceLabel: "Biriken toplam, {month} ile {previous}",
    lastSixMonths: "Son 6 ayın harcaması",
    nothingSpent: "Harcama yok",
    weekdaysSundayFirst: "Paz Pzt Sal Çar Per Cum Cmt",
    perDay: "Bu ay günlük harcama",
    moreThanLastMonth: "{category}, geçen aydan fazla",
    lessThanLastMonth: "{category}, geçen aydan az",
    sameEveryCategory: "Her kategoride geçen ayla aynı.",
    moreLegend: "Geçen aydan fazla",
    lessLegend: "Daha az",
    changeLabel: "Geçen aya göre kategori değişimi",
    onTrack: "Yolunda",
    closeToLimit: "Sınıra yakın",
    overLimit: "Sınır aşıldı",
    overall: "Genel",
    budgetUsed: "{name} bütçesi kullanımı",
    usedText: "%{pct} kullanıldı, {level}",
    alertAt: "%{pct} olunca uyar",
    of: "/",
    left: "kaldı",
    over: "fazla",
  },
});
