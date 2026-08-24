/** The script that stamps `<html lang>` before the first paint.
 *
 * The root layout used to read the locale cookie on the server, which is
 * what kept `lang` correct on the very first byte. A static export has
 * no server at render time — every page is a file written at build time,
 * under the default locale — so that read has to happen in the browser
 * instead, and it has to happen *before* anything paints.
 *
 * Same shape as `theme-script.ts`, and for the same reason: this string
 * is inlined into `<head>` by a *server* component, so this module must
 * stay out of the client graph. It imports only from `i18n/shared.ts`,
 * which is not a client module either and which the layout already
 * imports — the cookie name and the locale list are defined once, there,
 * so the script and the store can never disagree about them.
 *
 * What this does **not** do is translate anything. Text comes from
 * React, and the export prerendered it in the default locale; the
 * provider swaps it on hydration. Only `lang` — which screen readers,
 * spell-checkers and `:lang()` rules read — is correct from the first
 * frame.
 */

import { DEFAULT_LOCALE, LOCALES, LOCALE_COOKIE } from "./i18n/shared";

export const LOCALE_SCRIPT = `(function(){try{
var k=${JSON.stringify(LOCALE_COOKIE)},a=${JSON.stringify(LOCALES)},v=${JSON.stringify(DEFAULT_LOCALE)};
var p=document.cookie.split(";");
for(var i=0;i<p.length;i++){var c=p[i].trim(),e=c.indexOf("=");
if(e>0&&c.slice(0,e)===k){var r=decodeURIComponent(c.slice(e+1));if(a.indexOf(r)>=0)v=r;break;}}
document.documentElement.lang=v;
}catch(e){}})();`;
