export type NavigationGuard = () => boolean | Promise<boolean>;

let activeGuard: NavigationGuard | null = null;

export function registerNavigationGuard(guard: NavigationGuard) {
  activeGuard = guard;
  return () => {
    if (activeGuard === guard) activeGuard = null;
  };
}

export async function requestAppNavigation(): Promise<boolean> {
  if (!activeGuard) return true;
  return Boolean(await activeGuard());
}
