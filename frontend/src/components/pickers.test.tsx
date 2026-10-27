import { fireEvent, render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";
import { DatePicker, MonthPicker } from "./pickers";

it("moves between months and never past the max", () => {
  const onChange = vi.fn();
  render(<MonthPicker value="2026-10" max="2026-10" onChange={onChange} />);
  expect(screen.getByRole("button", { name: "Next month" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Previous month" }));
  expect(onChange).toHaveBeenCalledWith("2026-09");

  fireEvent.click(screen.getByRole("button", { name: "Month: October 2026" }));
  expect(screen.getByRole("button", { name: "Nov" })).toBeDisabled();
  fireEvent.click(screen.getByRole("button", { name: "Mar" }));
  expect(onChange).toHaveBeenLastCalledWith("2026-03");
});

it("wraps the year at January", () => {
  const onChange = vi.fn();
  render(<MonthPicker value="2026-01" onChange={onChange} />);
  fireEvent.click(screen.getByRole("button", { name: "Previous month" }));
  expect(onChange).toHaveBeenCalledWith("2025-12");
});

it("puts the picked day in a hidden form field", () => {
  const { container } = render(
    <form>
      <DatePicker label="Date" name="expense_date" defaultValue="2026-10-12" />
    </form>,
  );
  const hidden = container.querySelector<HTMLInputElement>('input[name="expense_date"]');
  expect(hidden?.value).toBe("2026-10-12");

  fireEvent.click(screen.getByRole("button", { name: /Date 12 Oct 2026/ }));
  fireEvent.click(screen.getByRole("button", { name: "20 Oct 2026" }));
  expect(hidden?.value).toBe("2026-10-20");

  fireEvent.click(screen.getByRole("button", { name: "Clear date" }));
  expect(hidden?.value).toBe("");
});
