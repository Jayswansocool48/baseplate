#!/usr/bin/env python3
"""Write the install files next to the Flatpak repo for GitHub Pages.

    python3 packaging/make-site.py <site-dir> <base64-gpg-public-key>
"""
import html
import os
import sys
from pathlib import Path

APP_ID = "io.github.jayswansocool48.Baseplate"
TITLE = "Baseplate"


def main():
    site, gpg = Path(sys.argv[1]), sys.argv[2].strip()
    owner, repo = os.environ.get("GITHUB_REPOSITORY",
                                 "Jayswansocool48/baseplate").split("/")
    base = f"https://{owner.lower()}.github.io/{repo}"
    home = f"https://github.com/{owner}/{repo}"
    flathub = "https://dl.flathub.org/repo/flathub.flatpakrepo"

    (site / "baseplate.flatpakrepo").write_text(f"""[Flatpak Repo]
Title={TITLE}
Url={base}/repo/
Homepage={home}
Comment=Updates for {TITLE}
Description=The {TITLE} app for Pop!_OS, built from {home}
GPGKey={gpg}
""")
    (site / "baseplate.flatpakref").write_text(f"""[Flatpak Ref]
Name={APP_ID}
Branch=stable
Title={TITLE}
Url={base}/repo/
SuggestRemoteName=baseplate
Homepage={home}
IsRuntime=false
GPGKey={gpg}
RuntimeRepo={flathub}
""")
    cmd = f"flatpak install --user {base}/baseplate.flatpakref"
    (site / "index.html").write_text(f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title>
<style>
 body{{font:16px/1.5 system-ui,sans-serif;max-width:44rem;margin:2rem auto;padding:0 1rem;
      color:#1b1f24;background:#fff}}
 code,pre{{background:#eef1f5;border-radius:6px;padding:.15rem .35rem}}
 pre{{padding:.8rem;overflow-x:auto}}
 a{{color:#1d4ed8}}
 @media (prefers-color-scheme:dark){{body{{color:#e8eaee;background:#15171a}}
  code,pre{{background:#262a30}} a{{color:#8ab4ff}}}}
</style></head><body>
<h1><img src="icon.svg" alt="" width="48" height="48" style="vertical-align:middle"> {TITLE}</h1>
<p>Store, design, preview and sync your Roblox systems on Pop!_OS.</p>
<h2>Install</h2>
<p>Open a terminal and run:</p>
<pre>{html.escape(cmd)}</pre>
<p>Updates then arrive in the COSMIC Store with your other apps.
To uninstall, use the app's menu → <b>Uninstall Baseplate…</b>, or the COSMIC Store.</p>
<p>Other files: <a href="baseplate.flatpakrepo">repository file</a> ·
<a href="Baseplate.flatpak">offline installer</a> · <a href="{home}">source code</a></p>
<p><small>Not affiliated with or endorsed by Roblox Corporation or Figma, Inc.</small></p>
</body></html>
""")
    print("Wrote install files for", base)


if __name__ == "__main__":
    main()
