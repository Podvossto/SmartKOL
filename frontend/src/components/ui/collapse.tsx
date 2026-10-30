/** Content that slides open and shut. Put padding on a child, not here: the clipped box has to shrink to zero. Stays in the DOM, hidden from tabbing and screen readers while closed. */
export function Collapse({ open, id, children }: { open: boolean; id?: string; children: React.ReactNode }) {
  return (
    <div id={id} className="reveal" data-open={open} aria-hidden={!open} inert={!open}>
      <div>{children}</div>
    </div>
  );
}
