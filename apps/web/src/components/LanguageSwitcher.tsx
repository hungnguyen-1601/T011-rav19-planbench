"use client";

/** English ↔ Tiếng Việt.
 *
 * Each language is named *in itself* — "Tiếng Việt", not "Vietnamese".
 * Someone who cannot read the current language still has to be able to
 * find their own, which is the one case a language switcher exists for.
 *
 * Changing it reloads the route. The locale is a cookie the server reads
 * while rendering, so a refresh is what makes the server agree; without
 * it the shell would switch and any server-rendered text would not.
 */

import { useRouter } from "next/navigation";

import { Menu } from "./Menu";
import { LOCALES, localeStore, useTranslation, type Locale } from "@/lib/i18n";

export function LanguageSwitcher() {
  const { t, locale } = useTranslation();
  const router = useRouter();

  return (
    <Menu<Locale>
      label={t("language.label")}
      tooltip={t("language.switch", { current: t(`language.${locale}`) })}
      icon="globe"
      buttonLabel={locale.toUpperCase()}
      value={locale}
      onSelect={(next) => {
        if (next === locale) return;
        localeStore.set(next);
        router.refresh();
      }}
      choices={LOCALES.map((value) => ({ value, label: t(`language.${value}`) }))}
    />
  );
}
