// Exchange rates (owner: track MONEY).
import { query, request } from "./client";

export type FxRate = { currency: string; rate_date: string; try_per_unit: string };

export type FxConversion = {
  from_currency: string;
  to_currency: string;
  on: string;
  rate: string;
  amount: string;
  amount_minor: number;
  converted: string;
  converted_minor: number;
};

export const fxApi = {
  rate: (currency: string, on?: string) => request<FxRate>(`/fx/rates/${currency}${query({ on })}`),
  convert: (amount: string, from: string, to = "TRY", on?: string) =>
    request<FxConversion>(`/fx/convert${query({ amount, from, to, on })}`),
};
