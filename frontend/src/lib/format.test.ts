import { describe, expect, it } from "vitest";
import { formatMoney } from "./format";

describe("formatMoney", () => {
  it.each([
    ["1234.5", "TRY", "₺1.234,50"],
    ["0", "TRY", "₺0,00"],
    ["-12.50", "try", "-₺12,50"],
    ["12.50", "USD", "$12,50"],
    ["12.50", "", "₺12,50"],
    ["9007199254740993.25", "TRY", "₺9.007.199.254.740.993,25"],
  ])("formats %s in %s", (amount, currency, expected) => {
    expect(formatMoney(amount, currency)).toBe(expected);
  });

  it.each([null, undefined, ""])("renders missing amount %s as empty", (amount) => {
    expect(formatMoney(amount, "TRY")).toBe("");
  });

  it("keeps the amount and currency when the currency code is invalid", () => {
    expect(formatMoney("12.50", "invalid")).toBe("12.50 invalid");
  });
});
