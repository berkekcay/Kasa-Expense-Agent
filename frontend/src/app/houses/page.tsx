import type { Metadata } from "next";
import { HouseView } from "@/features/houses/HouseView";

export const metadata: Metadata = { title: "House" };

// The header lives in HouseView: its title is the selected house and its actions need client state.
export default function HousesPage() {
  return <HouseView />;
}
