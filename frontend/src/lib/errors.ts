import { ApiError } from "@/lib/api/client";
import { firebaseEnabled } from "@/lib/auth";

/** A short, readable message for anything a request can throw. */
export function errorMessage(e: unknown): string {
  if (e instanceof ApiError) {
    if (e.status === 401) {
      return firebaseEnabled ? "Please sign in to see your data." : "The API did not accept the dev user.";
    }
    if (e.status === 501) return `This part of the API is not ready yet (${e.message}).`;
  }
  return e instanceof Error ? e.message : String(e);
}
