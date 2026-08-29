import { Card, CardContent, CardHeader, CardTitle } from "@/components/tailgrids/core/card";
import {
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRoot,
  TableRow,
} from "@/components/tailgrids/core/table";
import { DiscoveryTabs, PageHeader, SkeletonNote } from "./shell";

export type BusinessColumn<T> = {
  key: keyof T & string;
  header: string;
  className?: string;
};

export function BusinessTablePage<T extends Record<string, string>>({
  title,
  subtitle,
  columns,
  rows,
  discoveryTab,
  note,
}: {
  title: string;
  subtitle: string;
  columns: BusinessColumn<T>[];
  rows: T[];
  discoveryTab?: string;
  note?: string;
}) {
  return (
    <div className="mt-6 space-y-5">
      <PageHeader title={title} subtitle={subtitle} />
      <div className="space-y-4 px-2 lg:px-5">
        {discoveryTab ? <DiscoveryTabs activePath={discoveryTab} /> : null}
        {note ? <SkeletonNote>{note}</SkeletonNote> : null}
        <Card>
          <CardHeader>
            <CardTitle>{title}</CardTitle>
          </CardHeader>
          <CardContent className="px-0 pb-0">
            <TableRoot className="w-full min-w-200 rounded-none border-none">
              <TableHeader>
                <TableRow>
                  {columns.map((column) => (
                    <TableHead key={column.key} className={column.className}>
                      {column.header}
                    </TableHead>
                  ))}
                </TableRow>
              </TableHeader>
              <TableBody>
                {rows.map((row, index) => (
                  <TableRow key={index}>
                    {columns.map((column) => (
                      <TableCell key={column.key} className={column.className}>
                        {row[column.key]}
                      </TableCell>
                    ))}
                  </TableRow>
                ))}
              </TableBody>
            </TableRoot>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
