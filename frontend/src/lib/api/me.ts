// The signed-in user's profile: the display name flatmates see.
import { patch, request } from "./client";

export type Me = { user_id: string; display_name: string; email: string | null };

export const meApi = {
  get: () => request<Me>("/me"),
  setDisplayName: (displayName: string) => request<Me>("/me", patch({ display_name: displayName })),
};
