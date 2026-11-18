# workaround-watcher

Every "temporary fix" (a patched stylesheet, a pinned package, an env var in a
launcher) is meant to be reverted once upstream fixes the real problem. In
practice nobody remembers. This simple python script reads a yaml file (aka
"config") which lists the hacks you made, check the condition under which each
hack can go, and sends a desktop notification once that condition is true.

It nags on every run until you delete the entry. Deleting the entry is your
"done".

Vibecoded from start to finish, intended to work on arch linux, tested on
Omarchy.

## Config

`~/.config/workarounds.yaml` (or `$XDG_CONFIG_HOME/workarounds.yaml`, or `-c PATH`):

```yaml
- name: FreeCAD OVP invisible text
  when: { pkg: qt6-base, ge: 6.12.1 }
  desc: >
    Remove ~/.local/share/FreeCAD/v1-1/Gui/Stylesheets/FreeCAD.qss
    and check that text in the sketcher dimension box is visible.
  see:
    - https://github.com/FreeCAD/FreeCAD/issues/33676
```

| key    | required | meaning                                     |
| ------ | -------- | ------------------------------------------- |
| `name` | no       | notification title                          |
| `when` | yes      | condition; the entry fires when it holds    |
| `desc` | no       | what to do                                  |
| `see`  | no       | list of links, appended to the notification |

### Conditions

`pkg` compares the installed pacman package version using pacman's own
`vercmp`, so epochs and pkgrel (`1:2.0-3`) behave the way pacman does.
Operators are `ge`, `gt`, `le`, `lt` and `eq`. If you give more than one, all
must hold (`{ pkg: foo, ge: 2.0, lt: 3.0 }`). If the package isn't installed,
the condition is false.

Every YAML value is read as a string, so you don't need to quote versions like
`6.10`.

A malformed entry also produces a notification, because a silently broken
entry is a lost reminder.

## Install

Needs Python 3.10+, PyYAML (`pacman -S python-yaml`), `pacman`/`vercmp`, and
`notify-send` for desktop notifications.

```sh
ln -s "$PWD/workaround_watcher.py" ~/.local/bin/workaround-watcher
cp examples/workarounds.yaml ~/.config/workarounds.yaml   # then edit
ln -s "$PWD"/systemd/workaround-watcher.{service,timer,path} ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now workaround-watcher.timer workaround-watcher.path
```

Run it by hand with `workaround-watcher --no-notify` to print to stdout only.
Logs from unit runs go to `journalctl --user -u workaround-watcher`.

## Triggers

- **`workaround-watcher.timer`** runs once a day. `Persistent=true` catches up
  after the machine was off.
- **`workaround-watcher.path`** fires when `/var/lib/pacman/local` changes,
  which means after any pacman/yay/omarchy-update transaction. It can fire
  mid-transaction, so the script first waits (up to 30 min) for
  `/var/lib/pacman/db.lck` to disappear.

Both are user units, so nothing needs root. Notifications need the user
manager to have `DBUS_SESSION_BUS_ADDRESS`, which is normally the case in a
graphical session (uwsm/Hyprland import it).

On Omarchy, `~/.config/omarchy/hooks/post-update.d/` would also work as a
trigger, but the `.path` unit covers manual `pacman -Syu` too.

## Tests

```sh
python -m unittest discover tests
```

## TODO

- More condition kinds: command exit code, file existence, date.
