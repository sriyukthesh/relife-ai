export default function Timeline() {
  return (
    <section className="overflow-hidden rounded-xl border border-stone-200 bg-white">
      <iframe
        title="Project planning timeline"
        src="/timeline-ui/"
        className="h-[min(82vh,1100px)] min-h-[720px] w-full border-0"
      />
    </section>
  );
}
