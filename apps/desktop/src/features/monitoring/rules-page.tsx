import {
  Button,
  Form,
  FormInput,
  z,
} from "@desk/ui";
import { SectionEmpty } from "@components/product-shell";
import { MonitoringShell } from "./monitoring-shell";

const rulesSchema = z.object({
  marginBelow: z.string().optional(),
  supplyDropPct: z.string().optional(),
  demandRisePct: z.string().optional(),
  competitionRisePct: z.string().optional(),
});

export function MonitoringRulesPage() {
  return (
    <MonitoringShell title="监控规则" subtitle="告警阈值阈值（骨架）">
      <div className="mx-auto w-full max-w-md">
        <Form
          schema={rulesSchema}
          defaultValues={{
            marginBelow: "",
            supplyDropPct: "",
            demandRisePct: "",
            competitionRisePct: "",
          }}
          onSubmit={() => {
            /* 骨架 */
          }}
        >
          <div className="flex flex-col gap-3">
            <FormInput name="marginBelow" label="利润率低于 %" placeholder="15" />
            <FormInput name="supplyDropPct" label="采购价下降 %" placeholder="10" />
            <FormInput name="demandRisePct" label="闲鱼价上涨 %" placeholder="10" />
            <FormInput name="competitionRisePct" label="竞品增加 %" placeholder="20" />
            <Button type="submit" size="sm" disabled>
              保存（骨架）
            </Button>
          </div>
        </Form>
        <SectionEmpty title="功能骨架" description="规则保存与调度后置。" />
      </div>
    </MonitoringShell>
  );
}
