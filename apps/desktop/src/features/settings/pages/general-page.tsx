import { Form, FormInput, Button, z } from "@desk/ui";
import { SectionEmpty } from "@components/product-shell";
import { SettingsLayoutPage } from "../settings-layout";

const schema = z.object({
  displayName: z.string().optional(),
});

export function SettingsGeneralPage() {
  return (
    <SettingsLayoutPage>
      <div className="mx-auto w-full max-w-md space-y-4">
        <Form
          schema={schema}
          defaultValues={{ displayName: "" }}
          onSubmit={() => {
            /* 骨架 */
          }}
        >
          <FormInput name="displayName" label="显示名称" placeholder="可选" />
          <div className="pt-2">
            <Button type="submit" size="sm" disabled>
              保存（骨架）
            </Button>
          </div>
        </Form>
        <SectionEmpty title="功能骨架" description="语言 / 主题 / 数据目录等后置。" />
      </div>
    </SettingsLayoutPage>
  );
}
