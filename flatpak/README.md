# Flatpak packaging

| File | What it is |
|------|------------|
| `com.dabobrotosarkar.StickyNotes.yml` | Manifest for local builds from this checkout |
| `flathub/com.dabobrotosarkar.StickyNotes.yml` | The manifest submitted to Flathub: identical, but builds from a release tag |
| `com.dabobrotosarkar.StickyNotes.desktop` | Desktop entry (the snap keeps `snap/gui/stickynotes.desktop`) |
| `icons/256.png`, `icons/512.png` | App icon at standard sizes |
| `../com.dabobrotosarkar.StickyNotes.metainfo.xml` | Store listing: description, screenshots, release notes |

Runtime: `org.kde.Platform` 6.11 with the `com.riverbankcomputing.PyQt.BaseApp` base.
The build strips the BaseApp's unused QtWebEngine/QtPdf (~340 MB → ~39 MB installed).

## Build and run locally

```bash
flatpak install -y flathub org.flatpak.Builder
flatpak run org.flatpak.Builder --user --install --install-deps-from=flathub \
    --force-clean --repo=flatpak/repo flatpak/build-dir flatpak/com.dabobrotosarkar.StickyNotes.yml
flatpak run com.dabobrotosarkar.StickyNotes
```

## Lint (what Flathub's reviewers run)

```bash
L="flatpak run --command=flatpak-builder-lint org.flatpak.Builder"
$L manifest flatpak/flathub/com.dabobrotosarkar.StickyNotes.yml
$L appstream com.dabobrotosarkar.StickyNotes.metainfo.xml
$L repo flatpak/repo
```

The screenshot checks only pass once the release tag in the screenshot URLs exists on GitHub.

## Sandbox notes

- **X11:** the app uses Qt's xcb backend (XWayland on Wayland desktops). That is what lets
  notes reopen where they were left and makes *Keep on top* and *Hide from the dock* work;
  Wayland offers clients none of the three. Hence `--socket=x11`, not `fallback-x11`.
- **Tray:** `--talk-name=org.kde.StatusNotifierWatcher`.
- **Start at login:** requested through the XDG Background portal (`stickynotes/autostart.py`).
  Works on GNOME and KDE. Desktops without a Background portal (e.g. XFCE without
  `xdg-desktop-portal-xapp`) get a clear message in Settings instead of a switch that lies.
- **Notes** live in `~/.var/app/com.dabobrotosarkar.StickyNotes/config/dstushar7/StickyNotesApp.conf`.
  Moving from the snap: copy
  `~/snap/stickynotes-dabobroto/current/.config/dstushar7/StickyNotesApp.conf` there
  (with the app closed).

## Submitting to Flathub

1. Tag the release (e.g. `v4.0.1`) and push the tag.
2. In `flathub/com.dabobrotosarkar.StickyNotes.yml`, set `commit:` to `git rev-parse v4.0.1`.
3. Fork <https://github.com/flathub/flathub>, branch off **`new-pr`**, add only that manifest,
   and open a PR against `new-pr` titled `Add com.dabobrotosarkar.StickyNotes`.
4. Comment `bot, build` to get a test build.

Suggested PR description:

> Sticky Notes: frameless sticky notes for the Linux desktop, with rich text, checklists,
> per-note opacity and a system tray icon. MIT licensed; I am the author
> (github.com/dstushar7/sticky-notes), and it has been on the Snap Store since 2025.
>
> **Permissions**
> - `--socket=x11`: notes are separate desktop windows that reopen where the user left them,
>   and the app offers *Keep on top* and *Hide from the dock*. Those need EWMH window states
>   and absolute positioning, which Wayland does not give clients, so the app uses Qt's xcb
>   backend (XWayland on Wayland sessions). It still works on Wayland desktops.
> - `--talk-name=org.kde.StatusNotifierWatcher`: the system tray icon, which is how users
>   reach their notes.
> - Start at login uses the Background portal; there is no filesystem access.
>
> The PyQt BaseApp's QtWebEngine and QtPdf are removed in `cleanup-commands`, since the app
> does not use them.

After it's merged, add `flathub.json` with `{"automerge-flathubbot-prs": true}` to the
new Flathub repo, so release tags here are picked up automatically via `x-checker-data`.
