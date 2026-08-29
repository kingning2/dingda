/**
 * 利润计算器占位 — 成本字段表单壳。
 */

import {
  Button,
  Card,
  CardContent,
  CardHeader,
  CardTitle,
  Form,
  FormInput,
  PageScaffold,
  z,
} from "@desk/ui";
import { SectionEmpty, SubNavTabs } from "@components/product-shell";
import { useLocation } from "react-router";

const PROFIT_TABS = [
  { path: "/profit/calculator", label: "计算器" },
  { path: "/profit/templates", label: "成本模板" },
];

const profitSchema = z.object({
  salePrice: z.string().min(1, "必填"),
  purchaseCost: z.string().min(1, "必填"),
  purchaseShipping: z.string().optional(),
  shippingCost: z.string().optional(),
  packagingCost: z.string().optional(),
  afterSaleLoss: z.string().optional(),
  otherCost: z.string().optional(),
});

/** 利润计算器骨架（不接真实计算）。 */
export function ProfitCalculatorPage() {
  const { pathname } = useLocation();

  return (
    <PageScaffold
      title="利润计算器"
      subtitle="售价 − 采购 − 运费 − 发货 − 包装 − 损耗 − 其他 = 预计利润"
      ambient="none"
      containerPadding="sm"
      toolbar={<SubNavTabs tabs={PROFIT_TABS} activePath={pathname} />}
    >
      <div className="mx-auto flex w-full max-w-xl flex-col gap-4">
        <Form
          schema={profitSchema}
          defaultValues={{
            salePrice: "",
            purchaseCost: "",
            purchaseShipping: "",
            shippingCost: "",
            packagingCost: "",
            afterSaleLoss: "",
            otherCost: "",
          }}
          onSubmit={() => {
            /* 骨架 */
          }}
        >
          <div className="flex flex-col gap-3">
            <FormInput name="salePrice" label="销售价格" placeholder="0.00" />
            <FormInput name="purchaseCost" label="采购成本" placeholder="0.00" />
            <FormInput name="purchaseShipping" label="采购运费" placeholder="0.00" />
            <FormInput name="shippingCost" label="发货成本" placeholder="0.00" />
            <FormInput name="packagingCost" label="包装成本" placeholder="0.00" />
            <FormInput name="afterSaleLoss" label="售后损耗" placeholder="0.00" />
            <FormInput name="otherCost" label="其他成本" placeholder="0.00" />
            <Button type="submit" size="sm" disabled>
              计算（骨架未接通）
            </Button>
          </div>
        </Form>

        <Card>
          <CardHeader>
            <CardTitle>结果</CardTitle>
          </CardHeader>
          <CardContent>
            <SectionEmpty
              title="利润 / 利润率 / ROI"
              description="接通后展示预计利润、利润率、ROI 与价格区间。"
            />
          </CardContent>
        </Card>
      </div>
    </PageScaffold>
  );
}
