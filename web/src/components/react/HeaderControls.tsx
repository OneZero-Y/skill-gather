import { LocaleToggle } from './LocaleProvider';
import { ThemeToggle } from './ThemeToggle';

export function HeaderControls() {
  return (
    <div className="flex items-center gap-2">
      <LocaleToggle />
      <ThemeToggle />
    </div>
  );
}
