export function scrollBelowAppHeader(target: HTMLElement, behavior: ScrollBehavior): void {
  const header = document.querySelector<HTMLElement>("[data-app-header]");
  const headerHeight = header?.getBoundingClientRect().height ?? 0;
  const targetTop = window.scrollY + target.getBoundingClientRect().top - headerHeight - 12;
  window.scrollTo({ top: Math.max(0, targetTop), behavior });
}
