# Release checklist

Every item is checked against the app as it ships. Legal text lives in
`roblox_vault/legal/` and is shown in the app (Menu → Legal & privacy).

## Legal pages
- [x] 1. Privacy policy: `legal/privacy.md`, shown on first launch and in the menu.
- [x] 2. Terms of service: `legal/terms.md`.
- [x] 3. Refund policy: `legal/refund.md`. The app is free, so there is nothing to refund.
- [x] 4. Cookie policy: `legal/cookies.md`. The app sets none; it explains the cookies Figma sets in the Figma tab and how they're deleted.
- [x] 5. Cookie consent banner: the Figma tab shows a notice and loads nothing until you press "Open Figma". Inside, Figma shows its own banner with a reject option.
- [x] 6. Checkbox consents: three separate boxes on first launch, all unticked, each matching its label. Continue stays disabled until they're ticked, and Quit sits beside it. Consent is versioned and asked again when the legal text changes (`LEGAL_VERSION` in `core.py`).

## Data
- [x] 7. No unnecessary data: no account, analytics or crash reports. The only network use is the opt-in Figma tab/imports (token and frame ID, nothing uploaded). The clipboard is read only during Connect, only for `figd_` tokens, then wiped.
- [x] 8. Third-party audit: `legal/third_party.md` lists Rojo (bundled), the GNOME runtime, figma.com and the Figma API (no SDK), GitHub Pages for updates, and every Flatpak permission with its reason.
- [x] 17. Kids' data: an age/parent checkbox at first launch, and no personal data is collected from anyone.
- [x] 18. Unsubscribe link in emails: n/a, the app sends no emails. Any future newsletter needs a one-click unsubscribe in every email.
- [x] 20. Data deletion: Menu → "Delete all my data…" wipes everything. Menu → "Uninstall Roblox Vault…" also removes the app, its icon and the older zip version's files. Figma → Sign out removes just the token and cookies.

## Honest design
- [x] 9. No dark patterns: no pre-ticked boxes, Cancel is the default in every delete or uninstall dialog, declining is as easy as accepting, nothing nags, and uninstalling is one menu item.
- [x] 10. No hidden fees: the app and its updates are free (Terms §7).
- [x] 11. No fake reviews: the app and its store listing show no reviews or ratings.
- [x] 12. No unsupported claims: only factual feature claims. The "Not affiliated with Roblox Corporation or Figma, Inc." line appears in About, the Terms and the store listing. The preview is described as an approximation.

## Accessibility
- [x] 13. Alt text: every icon button, list and text area has an accessible name and a tooltip. The GUI preview has a text Layers list. The app icon is decorative and always shown next to the app's name.
- [x] 14. Color contrast: the app adds no custom colours (system theme, including high contrast). The install page uses #1b1f24 on #fff (16:1). Unsaved state is shown with "•", not colour.
- [x] 15. Keyboard navigation: shortcuts for every action, F10 for the menu, Alt+1/2/3 for the tabs, and Tab/arrow keys elsewhere.

## Business and licensing
- [x] 16. Business details: `roblox_vault/business.json`. Owner Jayswansocool48, with the website and contact via GitHub Issues; it appears in About, the legal pages and the store listing. Add `country` if you want it shown.
- [x] 19. Fonts and images: no fonts shipped. The icon and sounds are original (MIT). Rojo is under MPL-2.0 with a source link. The app is MIT (`LICENSE`).
