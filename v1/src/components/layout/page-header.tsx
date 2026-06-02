export function PageHeader({
  title,
  description,
  meta,
}: {
  title: string;
  description: string;
  meta?: string;
}) {
  return (
    <div className="mb-4 flex flex-col justify-between gap-2 border-b pb-4 lg:flex-row lg:items-end">
      <div>
        <h1 className="text-xl font-semibold tracking-tight text-foreground">
          {title}
        </h1>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>
      </div>
      {meta ? (
        <div className="text-xs font-medium uppercase tracking-[0.08em] text-muted-foreground">
          {meta}
        </div>
      ) : null}
    </div>
  );
}
