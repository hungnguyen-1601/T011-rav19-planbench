/** The member's picture, or their initial.
 *
 * `<img>` rather than `next/image`: avatars come from whatever host the
 * provider uses (googleusercontent, avatars.githubusercontent, and
 * whatever they move to next), and `next/image` requires every one of
 * those to be allow-listed in `next.config.ts`. A missing entry there
 * fails the whole page rather than one picture.
 *
 * Always `alt=""`. The nickname is written next to it in every place
 * this is used, so describing the picture would just say it twice.
 */

import type { SessionUser } from "@/lib/auth";

export function Avatar({ user, size = 28 }: { user: SessionUser; size?: number }) {
  const label = user.nickname || user.display_name || user.email || "?";

  if (user.avatar_url) {
    return (
      // eslint-disable-next-line @next/next/no-img-element
      <img
        className="avatar"
        src={user.avatar_url}
        alt=""
        width={size}
        height={size}
        style={{ width: size, height: size }}
      />
    );
  }
  return (
    <span
      className="avatar avatar-placeholder"
      aria-hidden="true"
      style={{ width: size, height: size, fontSize: Math.round(size * 0.46) }}
    >
      {label.slice(0, 1).toUpperCase()}
    </span>
  );
}
