# Release checklist

Every item is checked against the app as it ships. Legal text lives in
`baseplate/legal/` and is shown in the app (Menu → Legal & privacy).

## Legal pages
- [x] 1. Privacy policy: `legal/privacy.md`, shown on first launch and in the menu.
- [x] 2. Terms of service: `legal/terms.md`.
- [x] 3. Refund policy: `legal/refund.md`. The app is free, so there is nothing to refund.
- [x] 4. Cookie policy: `legal/cookies.md`. The app sets none; it explains the cookies Figma sets in the Figma tab and how they're deleted.
- [x] 5. Cookie consent banner: the Figma tab shows a notice and loads nothing until you press "Open Figma". Inside, Figma shows its own banner with a reject option.
- [x] 6. Checkbox consents: three separate unticked boxes on first launch (Terms, Privacy, age), Continue disabled until ticked, Quit beside it; versioned and re-asked when the legal text changes. Before the first message to Claude or ChatGPT, a separate prompt says exactly what is sent and who bills it, with Cancel as the default.

## Data
- [x] 7. No unnecessary data: no account, analytics or crash reports. Cloud AI gets only the message, the chat so far and what you tick under Share; chats aren't saved. Ollama keeps everything local. Figma gets only the token and frame ID. The clipboard is read only during Figma Connect, only for `figd_` tokens.
- [x] 8. Third-party audit: `legal/third_party.md` lists Rojo (bundled), the GNOME runtime, Ollama, the Anthropic and OpenAI APIs (no SDKs), figma.com and the Figma API, GitHub Pages for updates, and every Flatpak permission with its reason.
- [x] 17. Kids' data: an age/parent checkbox at first launch, and no personal data is collected. The privacy policy and Terms point younger users to Ollama, since Claude and ChatGPT have their own age rules.
- [x] 18. Unsubscribe link in emails: n/a, the app sends no emails. Any future newsletter needs a one-click unsubscribe in every email.
- [x] 20. Data deletion: "Delete all my data…" wipes projects, settings, API keys, the Figma token and cookies. "Uninstall Baseplate…" also removes the app, Roblox Vault and the zip version. The policy explains how to ask Anthropic or OpenAI about messages already sent.

## Honest design
- [x] 9. No dark patterns: no pre-ticked boxes, Cancel is the default in every delete or uninstall dialog, declining is as easy as accepting, nothing nags, and uninstalling is one menu item.
- [x] 10. No hidden fees: the app and its updates are free. The only possible cost (Claude or ChatGPT API use, billed by Anthropic or OpenAI to your own account) is stated in settings, in the first-send prompt, in the Terms (§8) and in the Refund policy. Ollama is free.
- [x] 11. No fake reviews: the app and its store listing show no reviews or ratings.
- [x] 12. No unsupported claims: only factual feature claims. The Terms say the assistant can be wrong and its code must be checked. The preview is described as an approximation. A not-affiliated line for Roblox, Figma, Anthropic and OpenAI appears in About, the Terms and the store listing.

## Accessibility
- [x] 13. Alt text: every icon button, list, chat bubble and code-block button has an accessible name and tooltip. Decorative icons are marked as presentation. The GUI preview has a text Layers list.
- [x] 14. Color contrast: the dark theme is tested in `tests/test_theme.py`. Text is at least 6:1 on every surface (body text at least 12:1) and the accent is 9.7:1 against its label text. High-contrast mode switches back to system colours. Nothing relies on colour alone.
- [x] 15. Keyboard navigation: shortcuts for every action. Ctrl+J opens the assistant and focuses the message box; Enter sends. F9 toggles the sidebar, Ctrl+L the log, Alt+1/2/3 the tabs, F10 the menu.

## Business and licensing
- [x] 16. Business details: `baseplate/business.json`. Owner Jayswansocool48, with the website and contact via GitHub Issues; it appears in About, the legal pages and the store listing. Add `country` if you want it shown.
- [x] 19. Fonts and images: no fonts shipped. The Baseplate icon and sounds are original (MIT). Rojo is MPL-2.0 with a source link. Ollama models carry their own licenses (noted in Terms §3). The app is MIT.
