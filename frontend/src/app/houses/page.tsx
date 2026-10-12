import type { Metadata } from "next";
import { PageHeader } from "@/components/ui";
import { HouseView } from "@/features/houses/HouseView";

export const metadata: Metadata = { title: "House" };

export default function HousesPage() {
  return (
    <>
      <PageHeader title="House" subtitle="Split shared bills your way and settle up with as few transfers as possible." />
      <HouseView />
    </>
  );
}
