import { Form, FormInput, Button, z } from "@desk/ui";
import { SectionEmpty } from "@components/product-shell";
import { SettingsLayoutPage } from "../settings-layout";

const schema = z.object({
  maxItems: z.string().optional(),
  concurrency: z.string().optional(),
});

export function SettingsCollectionPage() {
  return (
    <SettingsLayoutPage>
      <div className="mx-auto w-full max-w-md space-y-4">
        <Form
          schema={schema}
          defaultValues={{ maxItems: "50", concurrency: "1" }}
          onSubmit={() => {
            /* 骨架 */
          }}
        >
          <div className="flex flex-col gap-3">
            <FormInput name="maxItems" label="默认采集数量" />
            <FormInput name="concurrency" label="并发" />
            <Button type="submit" size="sm" disabled>
              保存（骨架）
            </Button>
          </div>
        </Form>
        <SectionEmpty title="功能骨架" description="浏览器相关设置后置。" />
      </div>
    </SettingsLayoutPage>
  );
}
