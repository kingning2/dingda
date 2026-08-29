import { Form, FormInput, Button, z } from "@desk/ui";
import { SectionEmpty } from "@components/product-shell";
import { SettingsLayoutPage } from "../settings-layout";

const schema = z.object({
  shipping: z.string().optional(),
  packaging: z.string().optional(),
  afterSale: z.string().optional(),
  other: z.string().optional(),
});

export function SettingsProfitPage() {
  return (
    <SettingsLayoutPage>
      <div className="mx-auto w-full max-w-md space-y-4">
        <Form
          schema={schema}
          defaultValues={{
            shipping: "",
            packaging: "",
            afterSale: "",
            other: "",
          }}
          onSubmit={() => {
            /* 骨架 */
          }}
        >
          <div className="flex flex-col gap-3">
            <FormInput name="shipping" label="默认运费" />
            <FormInput name="packaging" label="包装成本" />
            <FormInput name="afterSale" label="售后损耗" />
            <FormInput name="other" label="其他成本" />
            <Button type="submit" size="sm" disabled>
              保存（骨架）
            </Button>
          </div>
        </Form>
        <SectionEmpty title="功能骨架" description="将同步为默认 CostProfile。" />
      </div>
    </SettingsLayoutPage>
  );
}
