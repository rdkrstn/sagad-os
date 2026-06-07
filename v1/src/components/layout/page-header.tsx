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
    <div className="mb-3 flex flex-col justify-between gap-2 border-b border-border pb-3 lg:flex-row lg:items-end">
      <div>
        <h2 className="text-base font-semibold text-foreground">
          {title}
        </h2>
        <p className="mt-1 max-w-3xl text-sm text-muted-foreground">{description}</p>
      </div>
      {meta ? (
        <div className="font-mono text-[10px] font-medium uppercase text-muted-foreground">
          {meta}
        </div>
      ) : null}
    </div>
  );
}
