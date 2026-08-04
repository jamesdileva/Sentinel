interface PlaceholderProps {
  title: string;
}

export default function Placeholder({ title }: PlaceholderProps) {
  return (
    <section aria-label={title}>
      <div className="rounded-xl border border-dashed border-slate-300 p-8 text-center dark:border-slate-700">
        <p className="text-sm font-medium text-slate-600 dark:text-slate-300">{title}</p>
        <p className="mt-1 text-xs text-slate-400 dark:text-slate-500">
          This module is not implemented yet — see the sprint plan.
        </p>
      </div>
    </section>
  );
}
