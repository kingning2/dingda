/**
 * 利润分析 Feature。
 */

import { CircleDollarSign } from "@desk/ui/icons";

export { ProfitCalculatorPage } from "./calculator-page";
export { ProfitTemplatesPage } from "./templates-page";

export const PROFIT_PATH = "/profit" as const;

export const profitFeature = {
  id: "profit",
  path: PROFIT_PATH,
  navItem: {
    id: "profit",
    path: PROFIT_PATH,
    label: "利润分析",
    icon: CircleDollarSign,
  },
};
