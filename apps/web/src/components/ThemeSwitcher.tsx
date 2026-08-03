"use client";

/** Light / Dark / System.
 *
 * The icon shows what you would *get* — sun, moon, or a monitor for
 * "whatever the OS says" — while the checkmark shows what you *chose*.
 * Those differ whenever the preference is System, and conflating them
 * makes the menu look like it forgot your choice.
 */

import { Menu } from "./Menu";
import { useTranslation } from "@/lib/i18n";
import { themeStore, useThemePreference, type ThemePreference } from "@/lib/theme";
import type { IconName } from "./Icon";

const ICONS: Record<ThemePreference, IconName> = {
  light: "sun",
  dark: "moon",
  system: "monitor",
};

export function ThemeSwitcher() {
  const { t } = useTranslation();
  const preference = useThemePreference();

  return (
    <Menu<ThemePreference>
      label={t("theme.label")}
      tooltip={t("theme.switch", { current: t(`theme.${preference}`) })}
      icon={ICONS[preference]}
      value={preference}
      onSelect={(value) => themeStore.set(value)}
      choices={[
        { value: "light", label: t("theme.light"), icon: "sun" },
        { value: "dark", label: t("theme.dark"), icon: "moon" },
        { value: "system", label: t("theme.system"), icon: "monitor" },
      ]}
    />
  );
}
