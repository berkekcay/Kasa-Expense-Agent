// Typed client for the Kasa backend, one module per feature. `import { api } from "@/lib/api"`
// keeps working; new features are namespaced (api.budgets.list(), api.inbox.approve(...)).
// Tracks edit only their own module and never need to touch this file.

import { budgetsApi } from "./budgets";
import { chatApi } from "./chat";
import { health } from "./client";
import { dashboardApi } from "./dashboard";
import { expensesApi } from "./expenses";
import { fxApi } from "./fx";
import { housesApi } from "./houses";
import { importsApi } from "./imports";
import { inboxApi } from "./inbox";
import { integrationsApi } from "./integrations";
import { meApi } from "./me";
import { receiptsApi } from "./receipts";
import { subscriptionsApi } from "./subscriptions";

export * from "./budgets";
export * from "./chat";
export * from "./client";
export * from "./dashboard";
export * from "./expenses";
export * from "./fx";
export * from "./houses";
export * from "./imports";
export * from "./inbox";
export * from "./integrations";
export * from "./me";
export * from "./receipts";
export * from "./subscriptions";

export const api = {
  health,
  ...expensesApi,
  ...receiptsApi,
  ...housesApi,
  ...chatApi,
  budgets: budgetsApi,
  subscriptions: subscriptionsApi,
  dashboard: dashboardApi,
  fx: fxApi,
  inbox: inboxApi,
  imports: importsApi,
  integrations: integrationsApi,
  me: meApi,
};
