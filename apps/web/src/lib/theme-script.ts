/** The script that runs before the first paint, and the keys it reads.
 *
 * Deliberately **not** a `"use client"` module: the root layout is a
 * server component and inlines this string into `<head>`. Anything the
 * server touches has to live outside the client graph, or Next refuses
 * it at runtime — which is a failure neither `tsc` nor `next build`
 * catches, only actually starting the server does.
 *
 * It also imports nothing. It blocks rendering, so every byte is paid
 * for on every page load, and a module graph would defeat the point.
 * The storage keys are therefore defined here and imported *by*
 * `theme.ts` and `sidebar.ts`, rather than the other way round.
 */

export const THEME_STORAGE_KEY = "planbench.theme";
export const SIDEBAR_STORAGE_KEY = "planbench.sidebar";

export const THEME_SCRIPT = `(function(){try{
var s=window.localStorage;
var t=s.getItem(${JSON.stringify(THEME_STORAGE_KEY)})||"system";
var d=t==="dark"||(t==="system"&&window.matchMedia("(prefers-color-scheme: dark)").matches);
var r=document.documentElement;
r.dataset.theme=d?"dark":"light";r.dataset.themePref=t;r.style.colorScheme=d?"dark":"light";
if(s.getItem(${JSON.stringify(SIDEBAR_STORAGE_KEY)})==="collapsed")r.dataset.sidebar="collapsed";
}catch(e){}})();`;
